import asyncio
import threading
from typing import List, Optional
from app.database import (
    get_batch_status, update_field_job, update_batch_status,
    get_verification_results_for_field, save_verification_results_scoped,
    save_regeneration_scoped, get_field_config
)
from app.openrouter import generate_completion
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
