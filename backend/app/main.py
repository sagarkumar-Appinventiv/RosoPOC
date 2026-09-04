import json
import uuid
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import POC_SECRET_KEY
from app.openrouter import fetch_openrouter_models, generate_completion
from app.database import (
    get_settings, update_settings, find_matching_test_run, create_test_run,
    save_generation, update_generation_record, save_verification_results, save_regeneration,
    get_history_runs, get_run_details, get_comparison_runs, get_used_models_for_test_run,
    get_field_definitions, get_or_create_field_configs, create_batch, create_field_job,
    get_batch_status, get_field_job, get_field_job_in_batch, update_field_job, update_batch_status,
    get_verification_results_for_field, get_test_run, get_batch, get_batch_field_jobs, get_comparison_batches
)
from app.verification import verify_all_parameters, targeted_regeneration, LENGTH_WINDOW_CHARS
from app.prompt_compiler import compile_batch_prompts
from app.batch_engine import execute_batch, process_pending_jobs, IS_SERVERLESS

app = FastAPI(title="RosoTravel AI Content Generation POC API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthVerifyRequest(BaseModel):
    api_key: str

class ContentGenerateRequest(BaseModel):
    country: str = "France"
    city: str = "Paris"
    language: str = "English"
    input_json: Dict[str, Any]
    tone: Optional[str] = ""
    audience: Optional[str] = ""
    content_length: int = 2000
    banned_keywords: List[str] = []
    style_guide: Optional[str] = ""
    final_prompt: Optional[str] = ""
    model_id: str

class ContentVerifyRequest(BaseModel):
    generation_id: str

class ContentRegenerateRequest(BaseModel):
    generation_id: str

class SettingsUpdateRequest(BaseModel):
    verifier_model_id: Optional[str] = None
    verify_tone: Optional[bool] = None
    verify_audience: Optional[bool] = None
    verify_content_length: Optional[bool] = None
    verify_banned_keywords: Optional[bool] = None
    verify_style_guide: Optional[bool] = None
    content_length_tolerance_pct: Optional[int] = None
    max_verification_retries: Optional[int] = None
    regeneration_strategy: Optional[str] = None
    field_matching_strictness: Optional[str] = None

class CompileBatchRequest(BaseModel):
    test_run_id: str
    field_keys: List[str]

class GenerateBatchField(BaseModel):
    field_key: str
    system_prompt: str
    user_prompt: str

class GenerateBatchRequest(BaseModel):
    test_run_id: str
    model_name: str
    fields: List[GenerateBatchField]

class RerunFieldRequest(BaseModel):
    pass

def verify_session_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized session token required.")
    token = authorization.split(" ")[1]
    if not token.startswith("sk-or-v1-"):
        raise HTTPException(status_code=401, detail="Invalid OpenRouter API Key in session.")
    return token

@app.post("/api/auth/verify")
def auth_verify(payload: AuthVerifyRequest):
    key = payload.api_key.strip()
    if not key.startswith("sk-or-v1-"):
        raise HTTPException(status_code=401, detail="Invalid OpenRouter API key format.")
    
    headers = {"Authorization": f"Bearer {key}"}
    try:
        import requests
        resp = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=10)
        if resp.status_code == 200:
            return {
                "success": True,
                "message": "Authentication successful.",
                "token": key
            }
    except Exception:
        pass
    raise HTTPException(status_code=401, detail="Invalid OpenRouter API key. Please check your key and try again.")

@app.get("/api/models")
def get_models(token: str = Depends(verify_session_token)):
    return fetch_openrouter_models(api_key=token)

class TestRunGetOrCreateRequest(BaseModel):
    country: str = "France"
    city: str = "Paris"
    language: str = "English"
    input_json: Dict[str, Any] = {}
    tone: Optional[str] = ""
    audience: Optional[str] = ""
    content_length: int = 2000
    banned_keywords: List[str] = []
    style_guide: Optional[str] = ""

@app.post("/api/test-runs/get-or-create")
def test_run_get_or_create(payload: TestRunGetOrCreateRequest, token: str = Depends(verify_session_token)):
    prompt_config = {
        "tone": payload.tone or "",
        "audience": payload.audience or "",
        "content_length": payload.content_length,
        "banned_keywords": payload.banned_keywords,
        "style_guide": payload.style_guide or "",
        "final_prompt": "",
        "language": payload.language or "English"
    }
    existing = find_matching_test_run(
        country=payload.country,
        city=payload.city,
        language=payload.language or "English",
        input_json=payload.input_json,
        prompt_config=prompt_config
    )
    test_run_id = existing or create_test_run(
        country=payload.country,
        city=payload.city,
        language=payload.language or "English",
        input_json=payload.input_json,
        prompt_config=prompt_config
    )
    return {"test_run_id": test_run_id}

@app.get("/api/fields/schema")
def get_field_schema(token: str = Depends(verify_session_token)):
    return get_field_definitions("city_page")

@app.post("/api/content/compile-batch")
def compile_batch_endpoint(payload: CompileBatchRequest, token: str = Depends(verify_session_token)):
    test_run = get_test_run(payload.test_run_id)
    if not test_run:
        raise HTTPException(status_code=404, detail="Test run not found.")

    input_json = test_run.get("test_run", {}).get("input_json", {})
    prompt_config = test_run.get("prompt_config", {}) or {}

    # Global defaults come from the stored prompt_config; language rides alongside.
    global_default = {
        "tone": prompt_config.get("tone", ""),
        "audience": prompt_config.get("audience", ""),
        "banned_keywords": prompt_config.get("banned_keywords", []),
        "style_guide": prompt_config.get("style_guide", ""),
        "language": (test_run.get("test_run", {}) or {}).get("language", "English"),
    }

    # Build per-field overrides from stored field_configs (all inherit by default).
    field_configs = get_or_create_field_configs(payload.test_run_id, payload.field_keys)
    overrides = {}
    for fc in field_configs:
        overrides[fc["field_key"]] = fc

    return compile_batch_prompts(input_json, payload.field_keys, global_default, overrides)

@app.get("/api/settings")
def get_app_settings_route():
    return get_settings()

@app.post("/api/settings")
def update_app_settings_route(payload: SettingsUpdateRequest):
    data = {k: v for k, v in payload.dict().items() if v is not None}
    return update_settings(data)

@app.get("/api/dashboard/stats")
def get_dashboard_stats():
    history = get_history_runs()
    total_runs = len(history)
    successful_runs = sum(1 for h in history if (h.get("status") or "").lower() in ["verified", "regenerated", "pass"])
    regenerated_runs = sum(1 for h in history if (h.get("status") or "").lower() == "regenerated")
    total_tokens = sum(h.get("total_tokens", 0) for h in history)
    total_cost = round(sum(h.get("cost", 0.0) for h in history), 4)
    avg_latency_ms = int(sum(h.get("latency_ms", 0) for h in history) / total_runs) if total_runs > 0 else 0

    return {
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "regenerated_runs": regenerated_runs,
        "avg_latency_sec": round(avg_latency_ms / 1000.0, 2),
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "recent_runs": history[:10]
    }

@app.get("/api/test-runs/{test_run_id}/models")
def get_test_run_used_models(test_run_id: str):
    return get_used_models_for_test_run(test_run_id)

@app.post("/api/content/generate")
def generate_content_endpoint(payload: ContentGenerateRequest, token: str = Depends(verify_session_token)):
    if not payload.model_id:
        raise HTTPException(status_code=400, detail="Please select an OpenRouter model before generating content.")

    prompt_config = {
        "tone": payload.tone or "",
        "audience": payload.audience or "",
        "content_length": payload.content_length,
        "banned_keywords": payload.banned_keywords,
        "style_guide": payload.style_guide or "",
        "final_prompt": payload.final_prompt or "",
        "language": payload.language or "English"
    }

    # Lookup or create Test Run
    existing_tr_id = find_matching_test_run(
        country=payload.country,
        city=payload.city,
        language=payload.language or "English",
        input_json=payload.input_json,
        prompt_config=prompt_config
    )
    if existing_tr_id:
        test_run_id = existing_tr_id
    else:
        test_run_id = create_test_run(
            country=payload.country,
            city=payload.city,
            language=payload.language or "English",
            input_json=payload.input_json,
            prompt_config=prompt_config
        )

    target_lang = payload.language or "English"
    target_len = payload.content_length or 200

    # Explicit Multilingual & Character Length System Prompt Mandate
    system_prompt = f"""You are a professional travel content writer for RosoTravel.
CRITICAL LANGUAGE MANDATE:
Write ALL text string values in the JSON output strictly in {target_lang}. (If language is Hindi, use Hindi Devanagari script).

CRITICAL CHARACTER LENGTH MANDATE:
Provide detailed descriptions so the overall total character count is between {target_len - LENGTH_WINDOW_CHARS} and {target_len + LENGTH_WINDOW_CHARS} characters.

Output valid JSON only matching keys: title, introduction, attractions, activities, best_time_to_visit, travel_tips, faqs."""

    # Compile prompt if final_prompt not passed
    if not payload.final_prompt:
        prompt_parts = [
            f"Create travel guide content for {payload.city}, {payload.country} using the provided JSON data:",
            json.dumps(payload.input_json, indent=2),
            f"CRITICAL LANGUAGE MANDATE:\nYou MUST write and translate ALL output text strictly into {target_lang}. Do NOT write in English.",
            f"TARGET CHARACTER LENGTH: Provide rich details so the overall total character count is between {target_len - LENGTH_WINDOW_CHARS} and {target_len + LENGTH_WINDOW_CHARS} characters."
        ]
        if payload.tone:
            prompt_parts.append(f"Tone: {payload.tone}")
        if payload.audience:
            prompt_parts.append(f"Audience Variant: {payload.audience}")
        if payload.banned_keywords:
            prompt_parts.append("BANNED KEYWORDS (CRITICAL: DO NOT USE ANY OF THESE WORDS):\n" + "\n".join(["- " + kw for kw in payload.banned_keywords]))
        if payload.style_guide:
            prompt_parts.append(f"Style Guide:\n{payload.style_guide}")

        prompt_parts.append("""
OUTPUT REQUIREMENT:
Return strictly valid JSON matching this structure:
{
  "title": "Title in target language",
  "introduction": "Detailed intro paragraph in target language...",
  "attractions": [{"title": "Name", "description": "Details in target language..."}],
  "activities": ["Activity 1 in target language", "Activity 2..."],
  "best_time_to_visit": "Details in target language...",
  "travel_tips": ["Tip 1 in target language", "Tip 2..."],
  "faqs": [{"question": "Q in target language?", "answer": "A in target language..."}]
}
""")
        compiled_prompt = "\n\n".join(prompt_parts)
    else:
        compiled_prompt = payload.final_prompt

    models = fetch_openrouter_models(api_key=token)
    selected_model_name = next((m["name"] for m in models if m["id"] == payload.model_id), payload.model_id)

    gen_success, output_json, in_t, out_t, tot_t, lat_ms, cost = generate_completion(
        model_id=payload.model_id,
        prompt=compiled_prompt,
        api_key=token,
        system_prompt=system_prompt
    )

    if not gen_success or not output_json:
        error_msg = output_json.get("error", "Failed to generate valid content JSON.") if isinstance(output_json, dict) else "Content generation failed."
        save_generation(
            test_run_id=test_run_id,
            model_id=payload.model_id,
            model_name=selected_model_name,
            attempt_number=1,
            output_json={"error": error_msg},
            status="Failed",
            input_tokens=in_t,
            output_tokens=out_t,
            total_tokens=tot_t,
            latency_ms=lat_ms,
            cost=cost
        )
        raise HTTPException(status_code=500, detail=error_msg)

    gen_id = save_generation(
        test_run_id=test_run_id,
        model_id=payload.model_id,
        model_name=selected_model_name,
        attempt_number=1,
        output_json=output_json,
        status="Unverified",
        input_tokens=in_t,
        output_tokens=out_t,
        total_tokens=tot_t,
        latency_ms=lat_ms,
        cost=cost
    )

    return {
        "success": True,
        "generation_id": gen_id,
        "test_run_id": test_run_id,
        "status": "Unverified",
        "output_json": output_json,
        "metrics": {
            "input_tokens": in_t,
            "output_tokens": out_t,
            "total_tokens": tot_t,
            "latency_ms": lat_ms,
            "cost": cost
        }
    }

@app.post("/api/content/generate-batch")
def generate_batch_endpoint(payload: GenerateBatchRequest, token: str = Depends(verify_session_token)):
    if not payload.model_name:
        raise HTTPException(status_code=400, detail="Please select an OpenRouter model before running the batch.")
    if not payload.fields:
        raise HTTPException(status_code=400, detail="At least one field must be included in the batch.")

    # Create batch + queued field jobs (snapshot the edited prompts verbatim)
    batch_id = create_batch(payload.test_run_id, payload.model_name)
    for f in payload.fields:
        create_field_job(batch_id, f.field_key, f.system_prompt, f.user_prompt)

    if not IS_SERVERLESS:
        # Kick off async execution locally (returns immediately; UI polls /batch/{id}/status)
        execute_batch(batch_id, payload.model_name, token)
    else:
        # Serverless: no background thread. The status endpoint's worker tick
        # (process_pending_jobs) drives the batch on the next poll.
        update_batch_status(batch_id, "running")

    return {
        "success": True,
        "batch_id": batch_id,
        "test_run_id": payload.test_run_id,
        "model_name": payload.model_name,
        "field_count": len(payload.fields),
        "message": "Batch started. Poll /api/content/batch/{batch_id}/status for progress."
    }

@app.get("/api/content/batch/{batch_id}/status")
def batch_status_endpoint(batch_id: str, token: str = Depends(verify_session_token)):
    # Serverless: this poll IS the worker — make progress on queued jobs before
    # returning state, so no background thread needs to survive between requests.
    if IS_SERVERLESS:
        try:
            process_pending_jobs(batch_id, token)
        except Exception as e:
            print(f"Worker tick error for batch {batch_id}: {e}")

    status = get_batch_status(batch_id)
    if not status:
        raise HTTPException(status_code=404, detail="Batch not found.")

    fields_out = []
    for job in status["fields"]:
        fields_out.append({
            "field_job_id": job["id"],
            "field_key": job["field_key"],
            "status": job["status"],
            "output": job.get("output_json_fragment"),
            "verification": get_verification_results_for_field(job["id"]),
            "cost": job.get("cost", 0.0),
            "tokens": job.get("tokens", 0),
            "latency_ms": job.get("latency_ms", 0)
        })

    return {
        "batch_id": batch_id,
        "batch_status": status["batch"]["status"],
        "model_name": status["batch"]["model_name"],
        "fields": fields_out
    }

@app.post("/api/content/batch/{batch_id}/field/{field_key}/rerun")
def rerun_field_endpoint(batch_id: str, field_key: str, token: str = Depends(verify_session_token)):
    existing = get_field_job_in_batch(batch_id, field_key)
    if not existing:
        raise HTTPException(status_code=404, detail="Field job not found in this batch.")

    # Snapshot the original compiled prompts and re-create a single field job.
    new_job = create_field_job(batch_id, field_key, existing["compiled_system_prompt"], existing["compiled_user_prompt"])
    model_name = get_batch_status(batch_id)["batch"]["model_name"]

    if IS_SERVERLESS:
        # No background thread on serverless: reset the batch so the next status
        # poll picks up the new queued job and drives it to completion.
        update_batch_status(batch_id, "running")
    else:
        execute_batch(batch_id, model_name, token, only_field_job_id=new_job["id"])

    return {
        "success": True,
        "field_job_id": new_job["id"],
        "batch_id": batch_id,
        "field_key": field_key,
        "message": "Field re-run started."
    }

@app.post("/api/content/verify")
def verify_content_endpoint(payload: ContentVerifyRequest, token: str = Depends(verify_session_token)):
    run_detail = get_run_details(payload.generation_id)
    if not run_detail:
        raise HTTPException(status_code=404, detail="Generation run not found.")

    gen = run_detail["generation"]
    prompt_config = run_detail["prompt_config"]
    settings = get_settings()
    verifier_model_id = settings.get("verifier_model_id", "openai/gpt-4o")

    attempt_num = gen.get("attempt_number", 1)
    results = verify_all_parameters(
        content_json=gen["output_json"],
        prompt_config=prompt_config,
        api_key=token,
        verifier_model_id=verifier_model_id
    )

    save_verification_results(
        generation_id=payload.generation_id,
        verification_attempt=attempt_num,
        results=results
    )

    has_failures = any(r["status"] == "FAIL" for r in results)
    final_status = "Failed" if has_failures else ("Regenerated" if attempt_num > 1 else "Verified")

    update_generation_record(payload.generation_id, {"status": final_status})

    return {
        "success": True,
        "generation_id": payload.generation_id,
        "status": final_status,
        "verification_attempt": attempt_num,
        "verifier_model_id": verifier_model_id,
        "verification_results": results
    }

@app.post("/api/content/regenerate")
def regenerate_content_endpoint(payload: ContentRegenerateRequest, token: str = Depends(verify_session_token)):
    run_detail = get_run_details(payload.generation_id)
    if not run_detail:
        raise HTTPException(status_code=404, detail="Generation run not found.")

    gen = run_detail["generation"]
    prompt_config = run_detail["prompt_config"]
    verification_results = run_detail["verification_results"]

    if verification_results:
        max_attempt = max(r.get("verification_attempt", 1) for r in verification_results)
        latest_results = [r for r in verification_results if r.get("verification_attempt", 1) == max_attempt]
    else:
        latest_results = []

    failed_results = [r for r in latest_results if r["status"] == "FAIL"]
    if not failed_results:
        return {
            "success": True,
            "message": "No failed parameters found. Generation already meets all verification criteria.",
            "status": gen.get("status", "Verified"),
            "output_json": gen["output_json"],
            "verification_results": verification_results
        }

    try:
        new_output, p_tok, c_tok, t_tok, cost = targeted_regeneration(
            model_id=gen["model_id"],
            current_json=gen["output_json"],
            prompt_config=prompt_config,
            failed_results=failed_results,
            api_key=token
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    new_attempt = gen.get("attempt_number", 1) + 1

    save_regeneration(
        generation_id=payload.generation_id,
        parameter=failed_results[0]["parameter"],
        previous_output=gen["output_json"],
        new_output=new_output,
        reason=failed_results[0].get("reason", "Targeted parameter regeneration.")
    )

    settings = get_settings()
    verifier_model_id = settings.get("verifier_model_id", "openai/gpt-4o")

    new_ver_results = verify_all_parameters(
        content_json=new_output,
        prompt_config=prompt_config,
        api_key=token,
        verifier_model_id=verifier_model_id
    )

    save_verification_results(
        generation_id=payload.generation_id,
        verification_attempt=new_attempt,
        results=new_ver_results
    )

    has_failures = any(r["status"] == "FAIL" for r in new_ver_results)
    final_status = "Regenerated" if not has_failures else "Failed"

    update_generation_record(payload.generation_id, {
        "output_json": new_output,
        "attempt_number": new_attempt,
        "status": final_status,
        "total_tokens": gen.get("total_tokens", 0) + t_tok,
        "cost": round(gen.get("cost", 0.0) + cost, 4)
    })

    return {
        "success": True,
        "generation_id": payload.generation_id,
        "status": final_status,
        "attempts": new_attempt,
        "output_json": new_output,
        "verification_results": new_ver_results
    }

@app.get("/api/history")
def get_history():
    return get_history_runs()

@app.get("/api/history/{run_id}")
def get_history_run_details(run_id: str):
    # v2 batch runs are identified by batch id; legacy runs by generation id.
    detail = get_batch_field_jobs(run_id)
    if detail:
        batch = get_batch(run_id)
        tr = get_test_run(batch.get("test_run_id")) if batch else {}
        return {
            "batch": batch,
            "test_run": (tr or {}).get("test_run", {}),
            "prompt_config": (tr or {}).get("prompt_config", {}),
            "fields": detail
        }
    legacy = get_run_details(run_id)
    if not legacy:
        raise HTTPException(status_code=404, detail="Run not found.")
    return legacy

@app.get("/api/comparison/{test_run_id}")
def get_comparison(test_run_id: str):
    batches = get_comparison_batches(test_run_id)
    if batches:
        return batches
    return get_comparison_runs(test_run_id)
