import asyncio
import threading
from typing import List, Optional
from app.database import (
    get_batch_status, update_field_job, update_batch_status, update_batch_plan,
    get_verification_results_for_field, save_verification_results_scoped,
    save_regeneration_scoped, get_field_config, get_batch
)
from app.openrouter import generate_completion
from app.prompt_compiler import build_planner_prompt, slice_plan_for_field
from app.verification import verify_field, targeted_regenerate_field

CONCURRENCY_CAP = 3
MAX_REGENERATION_ATTEMPTS = 1

# Batch ids aborted due to a hard (non-retryable) failure such as 402.
_ABORTED_BATCHES = set()


def _is_aborted(batch_id: str) -> bool:
    return batch_id in _ABORTED_BATCHES


def _abort_batch(batch_id: str):
    _ABORTED_BATCHES.add(batch_id)
    # Mark every non-terminal job as failed so the batch reaches a terminal state fast.
    for j in _in_memory_jobs(batch_id):
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
    if not batch:
        return None

    from app.database import get_test_run, get_field_definitions

    test_run_id = batch.get("test_run_id")
    tr = get_test_run(test_run_id) if test_run_id else None
    if not tr:
        return None
    input_json = tr.get("test_run", {}).get("input_json", {}) or {}

    jobs = _in_memory_jobs(batch_id)
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


def _run_one_job(batch_id: str, model_name: str, api_key: str, field_job_id: str):
    job = next((j for j in _in_memory_jobs(batch_id) if j["id"] == field_job_id), None)
    if not job:
        return
    field_key = job["field_key"]
    system_prompt = job["compiled_system_prompt"]
    user_prompt = job["compiled_user_prompt"]

    # Resolve the field's config for verification/regeneration (inherit vs override)
    batch = get_batch_status(batch_id)
    test_run_id = (batch or {}).get("batch", {}).get("test_run_id")
    field_cfg = get_field_config(test_run_id, field_key) if test_run_id else None
    if not field_cfg:
        field_cfg = {}

    # Append the Semantic Consistency Planner's per-field slice (if a plan exists).
    plan = (batch or {}).get("batch", {}).get("plan_json")
    if isinstance(plan, dict):
        system_prompt = _apply_plan_to_prompt(field_key, plan, system_prompt)

    if _is_aborted(batch_id):
        update_field_job(field_job_id, {"status": "failed", "output_json_fragment": {"error": "Batch aborted: API credit limit reached (402)."}})
        return

    update_field_job(field_job_id, {"status": "running"})

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
    update_field_job(field_job_id, {"output_json_fragment": fragment, "status": "passed"})

    # 2. Verify (field-scoped). Use a minimal config: length check only unless overrides exist.
    field_cfg = job.get("field_config") or {}
    results = verify_field(field_key, fragment, field_cfg)
    save_verification_results_scoped(field_job_id, 1, results)

    if all(r["status"] == "PASS" for r in results):
        update_field_job(field_job_id, {"status": "passed"})
        return

    # 3. Targeted regeneration (same model, same field, max 1 attempt)
    failed = [r for r in results if r["status"] == "FAIL"]
    update_field_job(field_job_id, {"status": "regenerating"})

    regen_ok, new_fragment, r_in, r_out, r_tot, r_lat, r_cost = targeted_regenerate_field(
        model_id=model_name,
        field_key=field_key,
        current_fragment=fragment,
        failed_results=failed,
        field_config=field_cfg,
        api_key=api_key
    )

    # Accumulate cost/tokens
    cur = next((j for j in _in_memory_jobs(batch_id) if j["id"] == field_job_id), {})
    update_field_job(field_job_id, {
        "cost": round((cur.get("cost", 0.0) + r_cost), 6),
        "tokens": (cur.get("tokens", 0) + r_tot),
        "latency_ms": (cur.get("latency_ms", 0) + r_lat),
    })

    if not regen_ok:
        update_field_job(field_job_id, {"status": "regenerated_fail"})
        return

    update_field_job(field_job_id, {"output_json_fragment": new_fragment, "status": "regenerating"})
    new_results = verify_field(field_key, new_fragment, field_cfg)
    save_verification_results_scoped(field_job_id, 2, new_results)

    if all(r["status"] == "PASS" for r in new_results):
        update_field_job(field_job_id, {"status": "regenerated_pass"})
    else:
        update_field_job(field_job_id, {"status": "regenerated_fail"})


def _in_memory_jobs(batch_id: str):
    from app.database import _in_memory_db
    return [j for j in _in_memory_db["field_jobs"] if j["batch_id"] == batch_id]


def _compute_batch_status(batch_id: str):
    jobs = _in_memory_jobs(batch_id)
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
        _run_one_job(batch_id, model_name, api_key, only_field_job_id)
    else:
        jobs = _in_memory_jobs(batch_id)
        sem = asyncio.Semaphore(CONCURRENCY_CAP)

        async def run_with_sem(job_id: str):
            async with sem:
                if _is_aborted(batch_id):
                    update_field_job(job_id, {"status": "failed", "output_json_fragment": {"error": "Batch aborted: API credit limit reached (402)."}})
                    return
                _run_one_job(batch_id, model_name, api_key, job_id)

        async def runner():
            await asyncio.gather(*(run_with_sem(j["id"]) for j in jobs))

        asyncio.run(runner())

    update_batch_status(batch_id, _compute_batch_status(batch_id))


def execute_batch(batch_id: str, model_name: str, api_key: str, only_field_job_id: Optional[str] = None):
    """Runs the batch in a background thread so the API can return immediately."""
    t = threading.Thread(
        target=_run_async,
        args=(batch_id, model_name, api_key, only_field_job_id),
        daemon=True
    )
    t.start()
