import uuid
import datetime
from typing import Dict, Any, List, Optional

import os
from supabase import create_client, Client

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if supabase_url and supabase_key:
    try:
        supabase_client: Client = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"Failed to initialize Supabase client (Invalid API key?): {e}")
        supabase_client = None
else:
    supabase_client = None

_in_memory_db = {
    "test_runs": [],
    "prompt_configs": [],
    "generations": [],
    "verification_results": [],
    "regenerations": [],
    "field_definitions": [],
    "field_configs": [],
    "batches": [],
    "field_jobs": []
}

# Seed catalogue (Section 3.4 of rosotravel_batch_architecture_v2.md)
FIELD_DEFINITIONS_SEED = [
    {"field_key": "meta_title", "label": "Meta Title", "length_mode": "range", "length_min": 60, "length_max": 75, "unit": "characters", "default_order": 1, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "meta_description", "label": "Meta Description", "length_mode": "range", "length_min": 140, "length_max": 160, "unit": "characters", "default_order": 2, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "snippet", "label": "Snippet / Summary", "length_mode": "range", "length_min": 180, "length_max": 260, "unit": "characters", "default_order": 3, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "intro_paragraph", "label": "Intro Paragraph", "length_mode": "range", "length_min": 350, "length_max": 550, "unit": "characters", "default_order": 4, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "long_description", "label": "Long Description", "length_mode": "range", "length_min": 1600, "length_max": 2400, "unit": "characters", "default_order": 5, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "option_name", "label": "Option Name (Variant)", "length_mode": "range", "length_min": None, "length_max": 80, "unit": "characters", "default_order": 6, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "option_description", "label": "Option Description", "length_mode": "range", "length_min": None, "length_max": 255, "unit": "characters", "default_order": 7, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "highlight_bullet", "label": "Highlight bullet", "length_mode": "range", "length_min": None, "length_max": 85, "unit": "characters", "default_order": 8, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "faq_answer", "label": "FAQ Answer", "length_mode": "range", "length_min": 220, "length_max": 350, "unit": "characters", "default_order": 9, "schema_type": "city_page", "is_repeating": False, "max_instances": 1},
    {"field_key": "faq_city", "label": "FAQ (city-specific)", "length_mode": "range", "length_min": 220, "length_max": 350, "unit": "characters", "default_order": 10, "schema_type": "city_page", "is_repeating": True, "max_instances": 9},
]

def _seed_field_definitions():
    if not _in_memory_db["field_definitions"]:
        _in_memory_db["field_definitions"] = [dict(f) for f in FIELD_DEFINITIONS_SEED]
    return _in_memory_db["field_definitions"]

_seed_field_definitions()

def get_settings() -> Dict[str, Any]:
    default_settings = {
        "verifier_model_id": "openai/gpt-4o",
        "verify_tone": True,
        "verify_audience": True,
        "verify_content_length": True,
        "verify_banned_keywords": True,
        "verify_style_guide": True,
        "content_length_tolerance_pct": 50,
        "max_verification_retries": 3,
        "regeneration_strategy": "targeted",
        "field_matching_strictness": "moderate"
    }

    if supabase_client:
        try:
            res = supabase_client.table("app_settings").select("*").limit(1).execute()
            if res.data and len(res.data) > 0:
                return {**default_settings, **res.data[0]}
        except Exception as e:
            print(f"Supabase fetch settings error: {e}")

    return default_settings

def update_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    current = get_settings()
    updated = {**current, **new_settings}

    if supabase_client:
        try:
            res = supabase_client.table("app_settings").select("id").limit(1).execute()
            if res.data and len(res.data) > 0:
                settings_id = res.data[0]["id"]
                supabase_client.table("app_settings").update(updated).eq("id", settings_id).execute()
            else:
                updated["id"] = str(uuid.uuid4())
                supabase_client.table("app_settings").insert(updated).execute()
        except Exception as e:
            print(f"Supabase update settings error: {e}")

    return updated

def find_matching_test_run(country: str, city: str, language: str, input_json: Dict[str, Any], prompt_config: Dict[str, Any]) -> Optional[str]:
    """Finds an existing matching test_run_id for the given location & prompt config."""
    # Helper to check if pc matches
    def pc_matches(pc_id: str) -> bool:
        pc = next((p for p in _in_memory_db["prompt_configs"] if p.get("test_run_id") == pc_id), None)
        if not pc: return False
        return (pc.get("tone") == prompt_config.get("tone") and
                pc.get("audience") == prompt_config.get("audience") and
                pc.get("content_length") == prompt_config.get("content_length"))

    for tr in reversed(_in_memory_db["test_runs"]):
        if (tr.get("country", "").lower() == country.lower() and
            tr.get("city", "").lower() == city.lower() and
            tr.get("language", "").lower() == language.lower() and
            pc_matches(tr["id"])):
            return tr["id"]

    if supabase_client:
        try:
            res = supabase_client.table("test_runs").select("*, prompt_configs(*)").order("created_at", desc=True).limit(10).execute()
            if res.data:
                for tr in res.data:
                    if (tr.get("country", "").lower() == country.lower() and
                        tr.get("city", "").lower() == city.lower() and
                        tr.get("language", "").lower() == language.lower()):
                        
                        pcs = tr.get("prompt_configs", [])
                        if pcs and len(pcs) > 0:
                            pc = pcs[0]
                            if (pc.get("tone") == prompt_config.get("tone", "") and
                                pc.get("audience") == prompt_config.get("audience", "") and
                                pc.get("content_length") == prompt_config.get("content_length", 200)):
                                return tr["id"]
        except Exception as e:
            print(f"Supabase search test run error: {e}")

    return None

def create_test_run(country: str, city: str, language: str, input_json: Dict[str, Any], prompt_config: Dict[str, Any]) -> str:
    test_run_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    tr_record = {
        "id": test_run_id,
        "country": country,
        "city": city,
        "language": language,
        "input_json": input_json,
        "created_at": now
    }
    _in_memory_db["test_runs"].append(tr_record)

    pc_record = {
        "id": str(uuid.uuid4()),
        "test_run_id": test_run_id,
        "tone": prompt_config.get("tone", ""),
        "audience": prompt_config.get("audience", ""),
        "content_length": prompt_config.get("content_length", 200),
        "banned_keywords": prompt_config.get("banned_keywords", []),
        "style_guide": prompt_config.get("style_guide", ""),
        "final_prompt": prompt_config.get("final_prompt", ""),
        "created_at": now
    }
    _in_memory_db["prompt_configs"].append(pc_record)

    if supabase_client:
        try:
            supabase_client.table("test_runs").insert(tr_record).execute()
            supabase_client.table("prompt_configs").insert(pc_record).execute()
        except Exception as e:
            print(f"Supabase insert test run error: {e}")

    return test_run_id

def save_generation(
    test_run_id: str,
    model_id: str,
    model_name: str,
    attempt_number: int,
    output_json: Dict[str, Any],
    status: str = "Unverified",
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    cost: float = 0.0
) -> str:
    gen_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    rec = {
        "id": gen_id,
        "test_run_id": test_run_id,
        "model_id": model_id,
        "model_name": model_name,
        "attempt_number": attempt_number,
        "output_json": output_json,
        "status": status,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "latency_ms": latency_ms,
        "cost": cost,
        "created_at": now
    }
    _in_memory_db["generations"].append(rec)

    if supabase_client:
        try:
            supabase_client.table("generations").insert(rec).execute()
        except Exception as e:
            print(f"Supabase insert generation error: {e}")

    return gen_id

def update_generation_record(generation_id: str, update_data: Dict[str, Any]):
    gen = next((g for g in _in_memory_db["generations"] if g["id"] == generation_id), None)
    if gen:
        gen.update(update_data)

    if supabase_client:
        try:
            supabase_client.table("generations").update(update_data).eq("id", generation_id).execute()
        except Exception as e:
            print(f"Supabase update generation error: {e}")

def save_verification_results(generation_id: str, verification_attempt: int, results: List[Dict[str, Any]]):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    records = []
    for r in results:
        rec = {
            "id": str(uuid.uuid4()),
            "generation_id": generation_id,
            "parameter": r["parameter"],
            "status": r["status"],
            "reason": r.get("reason", ""),
            "affected_fields": r.get("affected_fields", []),
            "created_at": now
        }
        records.append(rec)
        _in_memory_db["verification_results"].append(rec)

    if supabase_client:
        try:
            supabase_client.table("verification_results").insert(records).execute()
        except Exception as e:
            print(f"Supabase verification insert error: {e}")

def save_regeneration(generation_id: str, parameter: str, previous_output: Dict[str, Any], new_output: Dict[str, Any], reason: str):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec = {
        "id": str(uuid.uuid4()),
        "generation_id": generation_id,
        "parameter": parameter,
        "previous_output": previous_output,
        "new_output": new_output,
        "reason": reason,
        "created_at": now
    }
    _in_memory_db["regenerations"].append(rec)
    if supabase_client:
        try:
            supabase_client.table("regenerations").insert(rec).execute()
        except Exception as e:
            print(f"Supabase regeneration insert error: {e}")

def get_history_runs() -> List[Dict[str, Any]]:
    """Returns past BATCH runs (post-v2) + legacy generations, deduplicated by batch_id/generation id."""
    history_map = {}

    # 1. Load batches + their field jobs (the v2 write path)
    for b in reversed(_in_memory_db["batches"]):
        tr = next((t for t in _in_memory_db["test_runs"] if t["id"] == b.get("test_run_id")), {})
        jobs = [j for j in _in_memory_db["field_jobs"] if j["batch_id"] == b["id"]]
        total = len(jobs)
        passed = sum(1 for j in jobs if j["status"] in {"passed", "regenerated_pass"})
        history_map[b["id"]] = {
            "run_id": b["id"],
            "batch_id": b["id"],
            "test_run_id": b.get("test_run_id"),
            "country": tr.get("country", "France"),
            "city": tr.get("city", "Paris"),
            "language": tr.get("language", "English"),
            "model": b.get("model_name"),
            "model_id": b.get("model_name"),
            "attempt_number": 1,
            "status": b.get("status", "pending"),
            "batch_status": b.get("status"),
            "fields_passed": passed,
            "fields_total": total,
            "latency_ms": sum(j.get("latency_ms", 0) for j in jobs),
            "total_tokens": sum(j.get("tokens", 0) for j in jobs),
            "cost": round(sum(j.get("cost", 0.0) for j in jobs), 6),
            "created_at": b.get("created_at")
        }

    # 2. Legacy generations (pre-v2) — kept so old rows still appear
    for g in reversed(_in_memory_db["generations"]):
        if g["id"] in history_map:
            continue
        tr = next((t for t in _in_memory_db["test_runs"] if t["id"] == g["test_run_id"]), {})
        history_map[g["id"]] = {
            "run_id": g["id"],
            "batch_id": None,
            "test_run_id": g["test_run_id"],
            "country": tr.get("country", "France"),
            "city": tr.get("city", "Paris"),
            "language": tr.get("language", "English"),
            "model": g.get("model_name", g["model_id"]),
            "model_id": g["model_id"],
            "attempt_number": g.get("attempt_number", 1),
            "status": g.get("status", "Verified"),
            "batch_status": None,
            "fields_passed": None,
            "fields_total": None,
            "latency_ms": g.get("latency_ms", 0),
            "total_tokens": g.get("total_tokens", 0),
            "cost": g.get("cost", 0.0),
            "created_at": g.get("created_at")
        }

    return list(history_map.values())

def get_used_models_for_test_run(test_run_id: str) -> List[str]:
    used = set()
    for g in _in_memory_db["generations"]:
        if g.get("test_run_id") == test_run_id:
            used.add(g.get("model_id"))
    return list(used)

def get_run_details(run_id: str) -> Optional[Dict[str, Any]]:
    if supabase_client:
        try:
            res = supabase_client.table("generations").select("*, test_runs(*, prompt_configs(*)), verification_results(*), regenerations(*)").eq("id", run_id).limit(1).execute()
            if res.data and len(res.data) > 0:
                g = res.data[0]
                tr = g.get("test_runs") or {}
                pc = tr.get("prompt_configs", [{}])[0] if isinstance(tr.get("prompt_configs"), list) and len(tr.get("prompt_configs")) > 0 else {}
                return {
                    "generation": g,
                    "test_run": tr,
                    "prompt_config": pc,
                    "verification_results": g.get("verification_results", []),
                    "regenerations": g.get("regenerations", [])
                }
        except Exception as e:
            print(f"Supabase run detail query error: {e}")

    gen = next((g for g in _in_memory_db["generations"] if g["id"] == run_id), None)
    if not gen:
        return None
    tr = next((t for t in _in_memory_db["test_runs"] if t["id"] == gen["test_run_id"]), {})
    pc = next((p for p in _in_memory_db["prompt_configs"] if p["test_run_id"] == tr.get("id")), {})
    vrs = [v for v in _in_memory_db["verification_results"] if v["generation_id"] == run_id]
    regs = [r for r in _in_memory_db["regenerations"] if r["generation_id"] == run_id]
    return {
        "generation": gen,
        "test_run": tr,
        "prompt_config": pc,
        "verification_results": vrs,
        "regenerations": regs
    }

def get_comparison_runs(test_run_id: str) -> List[Dict[str, Any]]:
    runs = []
    if supabase_client:
        try:
            res = supabase_client.table("generations").select("*, test_runs(*, prompt_configs(*)), verification_results(*), regenerations(*)").eq("test_run_id", test_run_id).execute()
            if res.data:
                for g in res.data:
                    if g.get("status") in ["Verified", "Regenerated", "Pass", "PASS"] and "error" not in g.get("output_json", {}):
                        tr = g.get("test_runs") or {}
                        pc = tr.get("prompt_configs", [{}])[0] if isinstance(tr.get("prompt_configs"), list) and len(tr.get("prompt_configs")) > 0 else {}
                        runs.append({
                            "generation": g,
                            "test_run": tr,
                            "prompt_config": pc,
                            "verification_results": g.get("verification_results", []),
                            "regenerations": g.get("regenerations", [])
                        })
                return runs
        except Exception as e:
            print(f"Supabase comparison query error: {e}")

    for g in _in_memory_db["generations"]:
        if g.get("test_run_id") == test_run_id or not test_run_id or test_run_id == "default":
            if g.get("status") in ["Verified", "Regenerated", "Pass", "PASS"] and "error" not in g.get("output_json", {}):
                tr = next((t for t in _in_memory_db["test_runs"] if t["id"] == g["test_run_id"]), {})
                pc = next((p for p in _in_memory_db["prompt_configs"] if p["test_run_id"] == g["test_run_id"]), {})
                vrs = [v for v in _in_memory_db["verification_results"] if v["generation_id"] == g["id"]]
                regs = [r for r in _in_memory_db["regenerations"] if r["generation_id"] == g["id"]]
                runs.append({
                    "generation": g,
                    "test_run": tr,
                    "prompt_config": pc,
                    "verification_results": vrs,
                    "regenerations": regs
                })
    return runs


# =====================================================================
# Per-field batch data layer (v2)
# =====================================================================

def get_field_definitions(schema_type: str = "city_page") -> List[Dict[str, Any]]:
    """Returns the configurable field list for a schema/page type."""
    return [
        f for f in _in_memory_db["field_definitions"]
        if f.get("schema_type", "city_page") == schema_type
    ]

def get_test_run(test_run_id: str) -> Optional[Dict[str, Any]]:
    """Returns a test_run + its prompt_config by test_run id (memory + Supabase fallback)."""
    tr = next((t for t in _in_memory_db["test_runs"] if t["id"] == test_run_id), None)
    pc = next((p for p in _in_memory_db["prompt_configs"] if p.get("test_run_id") == test_run_id), {})

    if tr:
        return {"test_run": tr, "prompt_config": pc}

    # Fall back to Supabase so a fresh/restarted process still resolves existing test runs.
    if supabase_client:
        try:
            res = supabase_client.table("test_runs").select("*, prompt_configs(*)").eq("id", test_run_id).limit(1).execute()
            if res.data:
                tr = res.data[0]
                pcs = tr.get("prompt_configs", [])
                pc = pcs[0] if isinstance(pcs, list) and pcs else {}
                return {"test_run": tr, "prompt_config": pc}
        except Exception as e:
            print(f"Supabase get_test_run error: {e}")

    return None

def get_field_definition(field_key: str) -> Optional[Dict[str, Any]]:
    return next((f for f in _in_memory_db["field_definitions"] if f["field_key"] == field_key), None)

def get_or_create_field_configs(test_run_id: str, field_keys: List[str]) -> List[Dict[str, Any]]:
    """Returns existing field_configs for the run, creating defaults from the catalogue where missing."""
    configs = [c for c in _in_memory_db["field_configs"] if c.get("test_run_id") == test_run_id]
    existing_keys = {c["field_key"] for c in configs}

    # Load any stored configs for this run from Supabase (another serverless instance may own them).
    if supabase_client:
        try:
            res = supabase_client.table("field_configs").select("*").eq("test_run_id", test_run_id).execute()
            for row in res.data or []:
                if row["field_key"] not in existing_keys:
                    _in_memory_db["field_configs"].append(row)
                    configs.append(row)
                    existing_keys.add(row["field_key"])
        except Exception as e:
            print(f"Supabase get_or_create_field_configs error: {e}")

    for fk in field_keys:
        if fk in existing_keys:
            continue
        fdef = get_field_definition(fk)
        if not fdef:
            continue
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cfg = {
            "id": str(uuid.uuid4()),
            "test_run_id": test_run_id,
            "field_key": fk,
            "length_mode": fdef.get("length_mode", "range"),
            "length_min": fdef.get("length_min"),
            "length_max": fdef.get("length_max"),
            "length_target": None,
            "length_tolerance_pct": None,
            "unit": fdef.get("unit", "characters"),
            "tone": None,
            "tone_override": False,
            "audience": None,
            "audience_override": False,
            "banned_keywords": None,
            "banned_keywords_override": False,
            "style_guide": None,
            "style_guide_override": False,
            "created_at": now
        }
        _in_memory_db["field_configs"].append(cfg)
        configs.append(cfg)
        existing_keys.add(fk)

    return configs

def get_field_config(test_run_id: str, field_key: str) -> Optional[Dict[str, Any]]:
    mem = next((c for c in _in_memory_db["field_configs"] if c["test_run_id"] == test_run_id and c["field_key"] == field_key), None)
    if mem:
        return mem
    if supabase_client:
        try:
            res = supabase_client.table("field_configs").select("*").eq("test_run_id", test_run_id).eq("field_key", field_key).limit(1).execute()
            if res.data:
                row = res.data[0]
                _in_memory_db["field_configs"].append(row)
                return row
        except Exception as e:
            print(f"Supabase get_field_config error: {e}")
    return None

def get_batch_field_jobs(batch_id: str) -> List[Dict[str, Any]]:
    """Returns all field jobs for a batch, each with its verification results attached."""
    jobs = list_field_jobs(batch_id)
    out = []
    for j in jobs:
        out.append({
            "field_job_id": j["id"],
            "field_key": j["field_key"],
            "status": j["status"],
            "output": j.get("output_json_fragment"),
            "verification_results": get_verification_results_for_field(j["id"]),
            "cost": j.get("cost", 0.0),
            "tokens": j.get("tokens", 0),
            "latency_ms": j.get("latency_ms", 0),
        })
    return out

def get_comparison_batches(test_run_id: str) -> List[Dict[str, Any]]:
    """Returns one entry per batch (a run) for a test_run, with per-field jobs attached.

    This is the v2 comparison source: side-by-side comparison joins across field_jobs
    for each selected batch_id, not a single flat generations row.
    """
    runs = []
    for b in _in_memory_db["batches"]:
        if b.get("test_run_id") != test_run_id:
            continue
        jobs = get_batch_field_jobs(b["id"])
        # A batch is comparable if it reached a terminal state and has at least one field with output.
        runs.append({
            "batch_id": b["id"],
            "test_run_id": b.get("test_run_id"),
            "model_name": b.get("model_name"),
            "status": b.get("status"),
            "created_at": b.get("created_at"),
            "fields": jobs,
        })
    return runs

def create_batch(test_run_id: str, model_name: str) -> str:
    batch_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    batch = {
        "id": batch_id,
        "test_run_id": test_run_id,
        "model_name": model_name,
        "status": "pending",
        "plan_json": None,
        "created_at": now
    }
    _in_memory_db["batches"].append(batch)
    if supabase_client:
        try:
            supabase_client.table("batches").insert(batch).execute()
        except Exception as e:
            print(f"Supabase batch insert error: {e}")
    return batch_id

def create_field_job(batch_id: str, field_key: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    job = {
        "id": job_id,
        "batch_id": batch_id,
        "field_key": field_key,
        "compiled_system_prompt": system_prompt,
        "compiled_user_prompt": user_prompt,
        "status": "queued",
        "output_json_fragment": None,
        "cost": 0.0,
        "tokens": 0,
        "latency_ms": 0,
        "attempt_count": 0,
        "created_at": now,
        "updated_at": now
    }
    _in_memory_db["field_jobs"].append(job)
    if supabase_client:
        try:
            supabase_client.table("field_jobs").insert(job).execute()
        except Exception as e:
            print(f"Supabase field_job insert error: {e}")
    return job

def update_field_job(field_job_id: str, update_data: Dict[str, Any]):
    job = next((j for j in _in_memory_db["field_jobs"] if j["id"] == field_job_id), None)
    if job:
        job.update(update_data)
        job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if supabase_client:
        try:
            supabase_client.table("field_jobs").update(update_data).eq("id", field_job_id).execute()
        except Exception as e:
            print(f"Supabase field_job update error: {e}")

def _cache_batch(b: Dict[str, Any]) -> Dict[str, Any]:
    """Upsert a batch row into the in-memory mirror (serverless: instance-local cache)."""
    existing = next((x for x in _in_memory_db["batches"] if x["id"] == b.get("id")), None)
    if existing:
        existing.update(b)
    else:
        _in_memory_db["batches"].append(b)
    return b

def _cache_field_job(j: Dict[str, Any]) -> Dict[str, Any]:
    existing = next((x for x in _in_memory_db["field_jobs"] if x["id"] == j.get("id")), None)
    if existing:
        existing.update(j)
    else:
        _in_memory_db["field_jobs"].append(j)
    return j

def get_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    mem = next((b for b in _in_memory_db["batches"] if b["id"] == batch_id), None)
    if mem:
        return mem
    if supabase_client:
        try:
            res = supabase_client.table("batches").select("*").eq("id", batch_id).limit(1).execute()
            if res.data:
                return _cache_batch(res.data[0])
        except Exception as e:
            print(f"Supabase get_batch error: {e}")
    return None

def list_field_jobs(batch_id: str) -> List[Dict[str, Any]]:
    """All field jobs for a batch, loading from Supabase on cache miss (serverless-safe)."""
    jobs = [j for j in _in_memory_db["field_jobs"] if j["batch_id"] == batch_id]
    if jobs or not supabase_client:
        return jobs
    try:
        res = supabase_client.table("field_jobs").select("*").eq("batch_id", batch_id).order("created_at").execute()
        out = []
        for row in res.data or []:
            out.append(_cache_field_job(row))
        return out
    except Exception as e:
        print(f"Supabase list_field_jobs error: {e}")
        return jobs

def get_batch_status(batch_id: str) -> Optional[Dict[str, Any]]:
    batch = get_batch(batch_id)
    if not batch:
        return None
    return {"batch": batch, "fields": list_field_jobs(batch_id)}

def get_field_job(field_job_id: str) -> Optional[Dict[str, Any]]:
    mem = next((j for j in _in_memory_db["field_jobs"] if j["id"] == field_job_id), None)
    if mem:
        return mem
    if supabase_client:
        try:
            res = supabase_client.table("field_jobs").select("*").eq("id", field_job_id).limit(1).execute()
            if res.data:
                return _cache_field_job(res.data[0])
        except Exception as e:
            print(f"Supabase get_field_job error: {e}")
    return None

def get_field_job_in_batch(batch_id: str, field_key: str) -> Optional[Dict[str, Any]]:
    return next((j for j in list_field_jobs(batch_id) if j["field_key"] == field_key), None)

def update_batch_status(batch_id: str, status: str):
    batch = get_batch(batch_id)
    if batch:
        batch["status"] = status
    if supabase_client:
        try:
            supabase_client.table("batches").update({"status": status}).eq("id", batch_id).execute()
        except Exception as e:
            print(f"Supabase batch status update error: {e}")

def update_batch_plan(batch_id: str, plan_json: Optional[Dict[str, Any]]):
    """Stores the Semantic Consistency Planner result on the batch for audit/debugging."""
    batch = get_batch(batch_id)
    if batch:
        batch["plan_json"] = plan_json
    if supabase_client:
        try:
            supabase_client.table("batches").update({"plan_json": plan_json}).eq("id", batch_id).execute()
        except Exception as e:
            print(f"Supabase batch plan update error: {e}")

def save_verification_results_scoped(field_job_id: str, verification_attempt: int, results: List[Dict[str, Any]]):
    """Saves verification results scoped to a field job (v2)."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    records = []
    for r in results:
        rec = {
            "id": str(uuid.uuid4()),
            "field_job_id": field_job_id,
            "generation_id": None,
            "verification_attempt": verification_attempt,
            "parameter": r["parameter"],
            "status": r["status"],
            "reason": r.get("reason", ""),
            "affected_fields": r.get("affected_fields", []),
            "created_at": now
        }
        records.append(rec)
        _in_memory_db["verification_results"].append(rec)
    if supabase_client:
        try:
            supabase_client.table("verification_results").insert(records).execute()
        except Exception as e:
            print(f"Supabase scoped verification insert error: {e}")

def get_verification_results_for_field(field_job_id: str) -> List[Dict[str, Any]]:
    mem = [v for v in _in_memory_db["verification_results"] if v.get("field_job_id") == field_job_id]
    if mem or not supabase_client:
        return mem
    try:
        res = supabase_client.table("verification_results").select("*").eq("field_job_id", field_job_id).order("created_at").execute()
        out = []
        for row in res.data or []:
            _in_memory_db["verification_results"].append(row)
            out.append(row)
        return out
    except Exception as e:
        print(f"Supabase get_verification_results_for_field error: {e}")
        return mem

def save_regeneration_scoped(field_job_id: str, parameter: str, previous_output: Any, new_output: Any, reason: str):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec = {
        "id": str(uuid.uuid4()),
        "field_job_id": field_job_id,
        "generation_id": None,
        "parameter": parameter,
        "previous_output": previous_output,
        "new_output": new_output,
        "reason": reason,
        "created_at": now
    }
    _in_memory_db["regenerations"].append(rec)
    if supabase_client:
        try:
            supabase_client.table("regenerations").insert(rec).execute()
        except Exception as e:
            print(f"Supabase scoped regeneration insert error: {e}")


# =====================================================================
# Serverless queue helpers
# =====================================================================

def _parse_iso(ts) -> Optional[datetime.datetime]:
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return None


def requeue_stale_jobs(batch_id: str, stale_after_sec: int = 120, max_attempts: int = 4) -> int:
    """Reset field jobs stuck in 'running'/'regenerating' so a later poll can pick them up.

    Serverless instances freeze mid-request; if the instance dies the job stays
    'running' forever. Any poll older than stale_after_sec resets those jobs to
    'queued' so the current (alive) instance retries them. Jobs that exceed
    max_attempts are failed outright so the batch cannot loop forever.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    requeued = 0
    for j in list_field_jobs(batch_id):
        if j.get("status") not in {"running", "regenerating"}:
            continue
        updated = _parse_iso(j.get("updated_at")) or _parse_iso(j.get("created_at"))
        if updated and (now - updated).total_seconds() > stale_after_sec:
            attempts = int(j.get("attempt_count") or 0) + 1
            if attempts >= max_attempts:
                update_field_job(j["id"], {"status": "failed", "output_json_fragment": {"error": "Job timed out repeatedly on the server; please re-run this field."}})
            else:
                update_field_job(j["id"], {"status": "queued", "attempt_count": attempts})
                requeued += 1
    return requeued


def claim_next_queued_job(batch_id: str) -> Optional[Dict[str, Any]]:
    """Atomically claim one queued field job (queued -> running).

    In serverless the status poll IS the worker; several instances may poll
    concurrently. The conditional UPDATE .. WHERE status='queued' guarantees only
    one instance wins each job, so we never double-pay for a generation.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # In-memory path (local dev / single process).
    if not supabase_client:
        for j in list_field_jobs(batch_id):
            if j.get("status") == "queued":
                update_field_job(j["id"], {"status": "running", "updated_at": now})
                return get_field_job(j["id"])
        return None

    try:
        # Pick the oldest queued job…
        sel = supabase_client.table("field_jobs").select("id").eq("batch_id", batch_id).eq("status", "queued").order("created_at").limit(1).execute()
        if not sel.data:
            return None
        cand_id = sel.data[0]["id"]
        # …and claim it conditionally so only one concurrent instance wins.
        upd = supabase_client.table("field_jobs").update({"status": "running", "updated_at": now}).eq("id", cand_id).eq("status", "queued").execute()
        if not upd.data:
            return None  # someone else claimed it
        row = upd.data[0]
        _cache_field_job(row)
        return row
    except Exception as e:
        print(f"Supabase claim_next_queued_job error: {e}")
        return None


def fail_orphan_batch(batch_id: str) -> bool:
    """If every job is terminal but the batch itself is stuck as running, mark it done."""
    batch = get_batch(batch_id)
    if not batch or batch.get("status") not in {"running", "pending"}:
        return False
    jobs = list_field_jobs(batch_id)
    if not jobs:
        return False
    terminal = {"passed", "regenerated_pass", "failed", "regenerated_fail"}
    if all(j.get("status") in terminal for j in jobs):
        statuses = [j.get("status") for j in jobs]
        if all(s in {"passed", "regenerated_pass"} for s in statuses):
            update_batch_status(batch_id, "completed")
        elif any(s in {"passed", "regenerated_pass"} for s in statuses):
            update_batch_status(batch_id, "partial_failure")
        else:
            update_batch_status(batch_id, "failed")
        return True
    return False
