"""Batch execution engine — serverless-safe worker.

On Vercel (serverless) a background thread is frozen as soon as the HTTP
response returns, and per-instance memory is not shared between requests.
So instead of fire-and-forget threads we run the batch **synchronously inside
a request**: the poll/status call drives the worker, which claims and processes
a few queued jobs per tick, then returns the latest state. State lives in
Supabase so any warm instance can continue the batch on the next poll.

Local (non-Vercel) keeps the old threaded path so behaviour is unchanged there.
"""
import asyncio
import os
import threading
import time
from typing import List, Optional
from app.database import (
    get_batch_status, update_field_job, update_batch_status, update_batch_plan,
    get_verification_results_for_field, save_verification_results_scoped,
    save_regeneration_scoped, get_field_config, get_batch, get_field_job,
    requeue_stale_jobs, fail_orphan_batch, claim_next_queued_job
)
from app.openrouter import generate_completion
from app.prompt_compiler import build_planner_prompt, slice_plan_for_field
from app.verification import verify_field, targeted_regenerate_field

CONCURRENCY_CAP = 3
MAX_REGENERATION_ATTEMPTS = 1
JOBS_PER_TICK = 3  # how many queued jobs one poll tick is allowed to run

IS_SERVERLESS = os.environ.get("VERCEL", "").lower() in {"1", "true", "yes", "vercel"}

# Vercel serverless functions are killed when the request exceeds maxDuration
# (default ~10s on Hobby, up to 60s+ on Pro). On serverless the poll request IS
# the worker, so a job must never outlive the request — otherwise it is left
# 'running' forever. These bounds keep each worker tick inside the request budget:
#   * STALE_JOB_AFTER_SEC: a 'running' job older than this is requeued by the
#     next poll. Keep it well below the function timeout.
#   * JOB_DEADLINE_SEC: hard cap on one job's generate+verify+regenerate work.
#     Local (threaded) mode ignores this; serverless enforces it so the request
#     returns before Vercel kills it.
STALE_JOB_AFTER_SEC = 25 if IS_SERVERLESS else 120
JOB_DEADLINE_SEC = 40 if IS_SERVERLESS else 600

# Batch ids aborted due to a hard (non-retryable) failure such as 402.
_ABORTED_BATCHES = set()


def _is_aborted(batch_id: str) -> bool:
    return batch_id in _ABORTED_BATCHES


def _abort_batch(batch_id: str):
    _ABORTED_BATCHES.add(batch_id)
    # Mark every non-terminal job as failed so the batch reaches a terminal state fast.
    status = get_batch_status(batch_id)
    if not status:
        return
    for j in status["fields"]:
        if j["status"] not in {"passed", "regenerated_pass", "failed", "regenerated_fail"}:
            update_field_job(j["id"], {"status": "failed", "output_json_fragment": {"error": "Batch aborted: API credit limit reached (402)."}})
    update_batch_status(batch_id, "failed")


def _parse_field_output(field_key: str, parsed: dict):
    """Extract just this field's fragment from a possibly larger JSON object."""
    if not isinstance(parsed, dict):
        return parsed
    if field_key in parsed:
        return parsed[field_key]
    # Fallback: return the whole dict if the model didn't scope its output
    return parsed


def _generate_plan(batch_id: str, model_name: str, api_key: str) -> Optional[dict]:
    """Run the Semantic Consistency Planner once per batch.

    Returns the Content Plan dict on success, None on failure (fall back to unplanned).
    """
    batch = get_batch(batch_id)
    if not batch or batch.get("plan_json"):
        return (batch or {}).get("plan_json")

    from app.database import get_test_run

    test_run_id = batch.get("test_run_id")
    tr = get_test_run(test_run_id) if test_run_id else None
    if not tr:
        return None
    input_json = tr.get("test_run", {}).get("input_json", {}) or {}

    jobs = get_batch_status(batch_id)["fields"]
    field_keys = [j["field_key"] for j in jobs]

    # Build resolved configs per field for the planner prompt.
    from app.prompt_compiler import resolve_field_config
    global_default = tr.get("prompt_config", {}) or {}
    global_default["language"] = (tr.get("test_run", {}) or {}).get("language", "English")

    resolved_configs = {"__global__": global_default}
    for fk in field_keys:
        fc = get_field_config(test_run_id, fk) if test_run_id else None
        resolved_configs[fk] = resolve_field_config(global_default, fc or {})

    prompt = build_planner_prompt(input_json, field_keys, resolved_configs)

    success, result_json, *_ = generate_completion(
        model_id=model_name,
        prompt=prompt,
        api_key=api_key,
        system_prompt="You are a travel content planner. Output valid JSON only."
    )

    if success and isinstance(result_json, dict) and ("narrative_core" in result_json or "fact_allocation" in result_json):
        update_batch_plan(batch_id, result_json)
        return result_json

    # Planner failed — log a warning and continue unplanned.
    print(f"Semantic planner failed for batch {batch_id}; running unplanned.")
    update_batch_plan(batch_id, {"warning": "Planner failed or timed out; batch ran unplanned."})
    return None


def _apply_plan_to_prompt(field_key: str, plan: Optional[dict], system_prompt: str) -> str:
    """Append the field's plan slice to the System prompt as a short Shared Context block."""
    if not plan:
        return system_prompt
    plan_slice = slice_plan_for_field(plan, field_key)
    if not plan_slice.get("narrative_core") and not plan_slice.get("allocated_facts"):
        return system_prompt

    parts = [system_prompt.rstrip(), "SHARED CONTEXT (for batch coherence):"]
    if plan_slice.get("narrative_core"):
        parts.append(f"NARRATIVE CORE: {plan_slice['narrative_core']}")
    facts = plan_slice.get("allocated_facts") or []
    if facts:
        parts.append("FACTS ASSIGNED TO THIS FIELD ONLY (do not repeat facts assigned elsewhere):")
        parts.extend(f"- {f}" for f in facts)
    return "\n".join(parts) + "\n"


def _field_config_for_job(job: dict) -> dict:
    """Resolve the field's config for verification/regeneration."""
    batch = get_batch(job.get("batch_id", ""))
    test_run_id = (batch or {}).get("test_run_id")
    field_cfg = get_field_config(test_run_id, job["field_key"]) if test_run_id else None
    return field_cfg or {}


def _run_one_job(job: dict, model_name: str, api_key: str):
    """Run generate -> verify -> targeted regenerate for a single field job."""
    field_job_id = job["id"]
    batch_id = job.get("batch_id", "")
    field_key = job["field_key"]
    system_prompt = job["compiled_system_prompt"]
    user_prompt = job["compiled_user_prompt"]
    field_cfg = job.get("field_config") or _field_config_for_job(job)

    # Append the Semantic Consistency Planner's per-field slice (if a plan exists).
    batch = get_batch(batch_id)
    plan = (batch or {}).get("plan_json")
    if isinstance(plan, dict):
        system_prompt = _apply_plan_to_prompt(field_key, plan, system_prompt)

    if _is_aborted(batch_id):
        update_field_job(field_job_id, {"status": "failed", "output_json_fragment": {"error": "Batch aborted: API credit limit reached (402)."}})
        return

    # 1. Generate
    success, result_json, in_t, out_t, tot_t, lat_ms, cost = generate_completion(
        model_id=model_name,
        prompt=user_prompt,
        api_key=api_key,
        system_prompt=system_prompt
    )

    # Fail fast on hard credit/API errors: don't let the rest of the batch retry.
    if not success and isinstance(result_json, dict) and "402" in str(result_json.get("error", "")):
        _abort_batch(batch_id)
        return

    update_field_job(field_job_id, {
        "cost": cost,
        "tokens": tot_t,
        "latency_ms": lat_ms,
    })

    if not success or not isinstance(result_json, dict):
        update_field_job(field_job_id, {
            "status": "failed",
            "output_json_fragment": {"error": result_json.get("error", "Generation failed.") if isinstance(result_json, dict) else "Generation failed."}
        })
        return

    fragment = _parse_field_output(field_key, result_json)

    # 2. Verify (field-scoped)
    results = verify_field(field_key, fragment, field_cfg)
    save_verification_results_scoped(field_job_id, 1, results)

    if all(r["status"] == "PASS" for r in results):
        update_field_job(field_job_id, {"output_json_fragment": fragment, "status": "passed"})
        return

    update_field_job(field_job_id, {"output_json_fragment": fragment, "status": "regenerating"})

    # 3. Targeted regeneration (same model, same field, max 1 attempt)
    failed = [r for r in results if r["status"] == "FAIL"]
    regen_ok, new_fragment, r_in, r_out, r_tot, r_lat, r_cost = targeted_regenerate_field(
        model_id=model_name,
        field_key=field_key,
        current_fragment=fragment,
        failed_results=failed,
        field_config=field_cfg,
        api_key=api_key
    )

    # Accumulate cost/tokens
    cur = get_field_job(field_job_id) or {}
    update_field_job(field_job_id, {
        "cost": round((cur.get("cost", 0.0) + r_cost), 6),
        "tokens": (cur.get("tokens", 0) + r_tot),
        "latency_ms": (cur.get("latency_ms", 0) + r_lat),
    })

    if not regen_ok:
        update_field_job(field_job_id, {"status": "regenerated_fail"})
        return

    new_results = verify_field(field_key, new_fragment, field_cfg)
    save_verification_results_scoped(field_job_id, 2, new_results)

    if all(r["status"] == "PASS" for r in new_results):
        update_field_job(field_job_id, {"output_json_fragment": new_fragment, "status": "regenerated_pass"})
    else:
        update_field_job(field_job_id, {"output_json_fragment": new_fragment, "status": "regenerated_fail"})


def _compute_batch_status(batch_id: str):
    status = get_batch_status(batch_id)
    jobs = status["fields"] if status else []
    if not jobs:
        return "pending"
    terminal_pass = {"passed", "regenerated_pass"}
    terminal_fail = {"failed", "regenerated_fail"}
    all_done = all(j["status"] in terminal_pass | terminal_fail for j in jobs)
    if not all_done:
        return "running"
    if all(j["status"] in terminal_pass for j in jobs):
        return "completed"
    if any(j["status"] in terminal_pass for j in jobs):
        return "partial_failure"
    return "failed"


# =====================================================================
# Serverless worker
# =====================================================================

def process_pending_jobs(batch_id: str, api_key: str, max_jobs: int = JOBS_PER_TICK) -> dict:
    """Synchronous worker tick. Claims and runs up to max_jobs queued jobs.

    Call from the batch-status endpoint on serverless: every poll makes progress
    even though no background thread survives between requests. The planner runs
    once (lazily) on the first tick that finds queued jobs.

    Claimed jobs are executed concurrently (blocking network I/O), so one tick is
    bounded by the slowest job, not the sum of all jobs.
    """
    requeue_stale_jobs(batch_id, stale_after_sec=STALE_JOB_AFTER_SEC)
    fail_orphan_batch(batch_id)
    status = get_batch_status(batch_id)
    if not status:
        return {"processed": 0, "batch_status": "not_found"}
    batch = status["batch"]
    if batch.get("status") in {"completed", "failed", "partial_failure"}:
        return {"processed": 0, "batch_status": batch.get("status")}

    if batch.get("status") in {None, "pending"}:
        update_batch_status(batch_id, "running")

    if _is_aborted(batch_id):
        _abort_batch(batch_id)
        return {"processed": 0, "batch_status": "failed"}

    jobs = status["fields"]
    queued = [j for j in jobs if j["status"] == "queued"]
    if not queued:
        # Nothing left to run; recompute and settle the batch flag.
        final_status = _compute_batch_status(batch_id)
        update_batch_status(batch_id, final_status)
        return {"processed": 0, "batch_status": final_status}

    model_name = batch.get("model_name")

    # Lazily run the Semantic Consistency Planner on the first productive tick.
    if not batch.get("plan_json"):
        try:
            plan = _generate_plan(batch_id, model_name, api_key)
            if plan:
                batch = get_batch(batch_id) or batch
        except Exception as e:
            print(f"Planner exception for batch {batch_id}: {e}")

    # Claim up to max_jobs queued jobs (each claim is atomic), then run them
    # concurrently so a slow model call doesn't serialise the whole batch.
    claimed = []
    for _ in range(max_jobs):
        job = claim_next_queued_job(batch_id)
        if not job:
            break
        job = dict(job)
        job["field_config"] = _field_config_for_job(job)
        claimed.append(job)

    if claimed:
        sem = asyncio.Semaphore(CONCURRENCY_CAP)
        tick_start = time.time()

        async def run_with_sem(job: dict):
            async with sem:
                # Time-box: never let this tick outlive the request budget. If the
                # deadline is near, put the job back to 'queued' so the next poll
                # (fresh request) picks it up — never leave it stranded 'running'.
                if time.time() - tick_start > JOB_DEADLINE_SEC:
                    update_field_job(job["id"], {"status": "queued"})
                    return
                try:
                    _run_one_job(job, model_name, api_key)
                except Exception as e:
                    print(f"Field job {job['id']} crashed: {e}")
                    update_field_job(job["id"], {"status": "failed", "output_json_fragment": {"error": f"Internal error: {e}"}})

        async def runner():
            await asyncio.gather(*(run_with_sem(j) for j in claimed))

        asyncio.run(runner())

    final_status = _compute_batch_status(batch_id)
    update_batch_status(batch_id, final_status)
    return {"processed": len(claimed), "batch_status": final_status}


# =====================================================================
# Local threaded path (unchanged behaviour when not on Vercel)
# =====================================================================

def _local_in_memory_jobs(batch_id: str):
    from app.database import list_field_jobs
    return list_field_jobs(batch_id)


def _run_async(batch_id: str, model_name: str, api_key: str, only_field_job_id: Optional[str] = None):
    update_batch_status(batch_id, "running")

    # Semantic Consistency Planner runs once per batch, before any field generation.
    # For single-field rerun we skip it (the field already has its own prompt context).
    if not only_field_job_id:
        try:
            _generate_plan(batch_id, model_name, api_key)
        except Exception as e:
            print(f"Planner exception for batch {batch_id}: {e}")

    if only_field_job_id:
        job = get_field_job(only_field_job_id)
        if job:
            job = dict(job)
            job["field_config"] = _field_config_for_job(job)
            _run_one_job(job, model_name, api_key)
    else:
        jobs = _local_in_memory_jobs(batch_id)
        sem = asyncio.Semaphore(CONCURRENCY_CAP)

        async def run_with_sem(job: dict):
            async with sem:
                if _is_aborted(batch_id):
                    update_field_job(job["id"], {"status": "failed", "output_json_fragment": {"error": "Batch aborted: API credit limit reached (402)."}})
                    return
                try:
                    _run_one_job(job, model_name, api_key)
                except Exception as e:
                    print(f"Field job {job['id']} crashed: {e}")
                    update_field_job(job["id"], {"status": "failed", "output_json_fragment": {"error": f"Internal error: {e}"}})

        async def runner():
            await asyncio.gather(*(run_with_sem(j) for j in jobs))

        asyncio.run(runner())

    update_batch_status(batch_id, _compute_batch_status(batch_id))


def execute_batch(batch_id: str, model_name: str, api_key: str, only_field_job_id: Optional[str] = None):
    """Runs the batch.

    Local: spawn a background thread (non-blocking, immediate response).
    Serverless (Vercel): no-op here — the batch is driven by the status endpoint
    via process_pending_jobs(), so work survives across requests.
    """
    if IS_SERVERLESS:
        return
    t = threading.Thread(
        target=_run_async,
        args=(batch_id, model_name, api_key, only_field_job_id),
        daemon=True
    )
    t.start()
