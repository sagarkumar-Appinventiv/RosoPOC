import uuid
import datetime
from typing import Dict, Any, List, Optional

import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load .env file for Supabase credentials (runs at import time)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

_supabase_client: Client | None = None

def get_supabase_client() -> Client | None:
    """Lazily initialize and return the Supabase client."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if supabase_url and supabase_key:
        try:
            _supabase_client = create_client(supabase_url, supabase_key)
        except Exception as e:
            print(f"Failed to initialize Supabase client (Invalid API key?): {e}")
            _supabase_client = None
    else:
        _supabase_client = None
    
    return _supabase_client

def _supabase_is_configured() -> bool:
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))

def _raise_persistence_error(operation: str, error: Exception) -> None:
    message = f"Supabase persistence failed during {operation}: {error}"
    print(message)
    raise RuntimeError(message) from error

def _get_persistence_client(operation: str) -> Client | None:
    client = get_supabase_client()
    if client is None and _supabase_is_configured():
        raise RuntimeError(f"Supabase is configured but unavailable during {operation}")
    return client

def _fetch_all_supabase_rows(table: str, select: str) -> List[Dict[str, Any]]:
    """Read every row in pages so history is not silently capped at 500 rows."""
    client = get_supabase_client()
    if not client:
        return []

    rows: List[Dict[str, Any]] = []
    page_size = 1000
    offset = 0
    while True:
        page = client.table(table).select(select).order("created_at", desc=True).range(offset, offset + page_size - 1).execute()
        data = page.data or []
        rows.extend(data)
        if len(data) < page_size:
            return rows
        offset += page_size

# For backward compatibility - use property-like access
# supabase_client is now accessed via get_supabase_client()
# This variable is kept for backward compatibility but should not be used directly
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
    "field_jobs": [],
    "translations": []
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

    if get_supabase_client():
        try:
            res = get_supabase_client().table("app_settings").select("*").limit(1).execute()
            if res.data and len(res.data) > 0:
                return {**default_settings, **res.data[0]}
        except Exception as e:
            print(f"Supabase fetch settings error: {e}")

    return default_settings

def update_settings(new_settings: Dict[str, Any]) -> Dict[str, Any]:
    current = get_settings()
    updated = {**current, **new_settings}

    if get_supabase_client():
        try:
            res = get_supabase_client().table("app_settings").select("id").limit(1).execute()
            if res.data and len(res.data) > 0:
                settings_id = res.data[0]["id"]
                get_supabase_client().table("app_settings").update(updated).eq("id", settings_id).execute()
            else:
                updated["id"] = str(uuid.uuid4())
                get_supabase_client().table("app_settings").insert(updated).execute()
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

    if get_supabase_client():
        try:
            res = get_supabase_client().table("test_runs").select("*, prompt_configs(*)").order("created_at", desc=True).limit(10).execute()
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

    client = _get_persistence_client("test run creation")
    if client:
        try:
            client.table("test_runs").insert(tr_record).execute()
            client.table("prompt_configs").insert(pc_record).execute()
        except Exception as e:
            if _supabase_is_configured():
                _raise_persistence_error("test run creation", e)
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

    client = _get_persistence_client("generation creation")
    if client:
        try:
            client.table("generations").insert(rec).execute()
        except Exception as e:
            if _supabase_is_configured():
                _raise_persistence_error("generation creation", e)
            print(f"Supabase insert generation error: {e}")

    return gen_id

def update_generation_record(generation_id: str, update_data: Dict[str, Any]):
    gen = next((g for g in _in_memory_db["generations"] if g["id"] == generation_id), None)
    if gen:
        gen.update(update_data)

    if get_supabase_client():
        try:
            get_supabase_client().table("generations").update(update_data).eq("id", generation_id).execute()
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

    if get_supabase_client():
        try:
            get_supabase_client().table("verification_results").insert(records).execute()
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
    if get_supabase_client():
        try:
            get_supabase_client().table("regenerations").insert(rec).execute()
        except Exception as e:
            print(f"Supabase regeneration insert error: {e}")

def _derive_batch_ui_status(batch_status: Optional[str], jobs: List[Dict[str, Any]]) -> str:
    """Maps a batch's raw status + field-job outcomes onto the UI status
    vocabulary (verified / regenerated / failed / partial_failure / pending /
    running) used by the History filters, History badges and Dashboard KPIs.

    Raw batch statuses are completed/partial_failure/failed/pending/running;
    "completed" becomes "verified" (or "regenerated" when any field went
    through a targeted regeneration), so filters and dashboard counters work.
    """
    s = (batch_status or "pending").lower()
    if s in ("failed", "partial_failure", "pending", "running"):
        return s
    if s in ("completed", "pass"):
        regenerated = any(j.get("status") in {"regenerated_pass", "regenerated_fail"} for j in jobs)
        return "regenerated" if regenerated else "verified"
    return s

def get_history_runs() -> List[Dict[str, Any]]:
    """Returns past BATCH runs (post-v2) + legacy generations, deduplicated by batch_id/generation id.
    Loads from Supabase (historical) + in-memory (current session)."""
    history_map = {}
    client = _get_persistence_client("history read")

    # 1. Load batches from Supabase (historical data across all serverless instances)
    if client:
        try:
            # Get all batches with their test_runs, ordered by created_at desc
            batches = _fetch_all_supabase_rows("batches", "*, test_runs(*)")
            if batches:
                # Field job stats for all batches in a few chunked queries (not one per batch)
                jobs_by_batch = list_field_jobs_bulk([b["id"] for b in batches])
                for b in batches:
                    tr = b.get("test_runs") or {}
                    test_run_id = b.get("test_run_id")
                    jobs = jobs_by_batch.get(b["id"], [])
                    total = len(jobs)
                    passed = sum(1 for j in jobs if j.get("status") in {"passed", "regenerated_pass"})
                    history_map[b["id"]] = {
                        "run_id": b["id"],
                        "batch_id": b["id"],
                        "test_run_id": test_run_id,
                        "country": tr.get("country", "France"),
                        "city": tr.get("city", "Paris"),
                        "language": tr.get("language", "English"),
                        "model": b.get("model_name"),
                        "model_id": b.get("model_name"),
                        "attempt_number": 1,
                        "status": _derive_batch_ui_status(b.get("status"), jobs),
                        "batch_status": b.get("status"),
                        "fields_passed": passed,
                        "fields_total": total,
                        "latency_ms": sum(j.get("latency_ms", 0) for j in jobs),
                        "total_tokens": sum(j.get("tokens", 0) for j in jobs),
                        "cost": round(sum(j.get("cost", 0.0) for j in jobs), 6),
                        "created_at": b.get("created_at")
                    }
        except Exception as e:
            if _supabase_is_configured():
                _raise_persistence_error("batch history read", e)
            print(f"Supabase history batches query error: {e}")

    # 2. Load legacy generations from Supabase
    if client:
        try:
            generations = _fetch_all_supabase_rows("generations", "*, test_runs(*)")
            if generations:
                for g in generations:
                    if g["id"] in history_map:
                        continue
                    tr = g.get("test_runs") or {}
                    test_run_id = g.get("test_run_id")
                    history_map[g["id"]] = {
                        "run_id": g["id"],
                        "batch_id": None,
                        "test_run_id": test_run_id,
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
        except Exception as e:
            if _supabase_is_configured():
                _raise_persistence_error("generation history read", e)
            print(f"Supabase history generations query error: {e}")

    # 3. Merge in-memory (current session) - overrides Supabase for latest state
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
            "status": _derive_batch_ui_status(b.get("status"), jobs),
            "batch_status": b.get("status"),
            "fields_passed": passed,
            "fields_total": total,
            "latency_ms": sum(j.get("latency_ms", 0) for j in jobs),
            "total_tokens": sum(j.get("tokens", 0) for j in jobs),
            "cost": round(sum(j.get("cost", 0.0) for j in jobs), 6),
            "created_at": b.get("created_at")
        }

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

    # Sort by created_at desc (newest first)
    result = list(history_map.values())
    result.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return result

def get_storage_health() -> Dict[str, Any]:
    """Return non-sensitive storage connectivity and row-count diagnostics."""
    configured = _supabase_is_configured()
    client = get_supabase_client()
    health: Dict[str, Any] = {
        "supabase_configured": configured,
        "supabase_connected": client is not None,
        "tables": {},
    }
    if not client:
        return health

    for table in ("test_runs", "generations", "batches", "field_jobs"):
        result = client.table(table).select("id, created_at", count="exact").order("created_at", desc=True).limit(1).execute()
        health["tables"][table] = {
            "count": result.count,
            "latest_created_at": result.data[0].get("created_at") if result.data else None,
        }
    return health

def get_used_models_for_test_run(test_run_id: str) -> List[str]:
    used = set()
    for g in _in_memory_db["generations"]:
        if g.get("test_run_id") == test_run_id:
            used.add(g.get("model_id"))
    return list(used)

def get_run_details(run_id: str) -> Optional[Dict[str, Any]]:
    if get_supabase_client():
        try:
            res = get_supabase_client().table("generations").select("*, test_runs(*, prompt_configs(*)), verification_results(*), regenerations(*)").eq("id", run_id).limit(1).execute()
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
    if get_supabase_client():
        try:
            res = get_supabase_client().table("generations").select("*, test_runs(*, prompt_configs(*)), verification_results(*), regenerations(*)").eq("test_run_id", test_run_id).execute()
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
    """Returns the configurable field list for a schema/page type.

    Loads from Supabase when memory is empty (e.g. fresh serverless instance),
    then caches locally. Falls back to the in-process seed catalogue.
    """
    mem = [
        f for f in _in_memory_db["field_definitions"]
        if f.get("schema_type", "city_page") == schema_type
    ]
    if mem:
        return mem

    if get_supabase_client():
        try:
            res = get_supabase_client().table("field_definitions").select("*").eq("schema_type", schema_type).order("default_order").execute()
            if res.data:
                _in_memory_db["field_definitions"].extend(res.data)
                return res.data
        except Exception as e:
            print(f"Supabase get_field_definitions error: {e}")

    return mem

def get_test_run(test_run_id: str) -> Optional[Dict[str, Any]]:
    """Returns a test_run + its prompt_config by test_run id (memory + Supabase fallback)."""
    tr = next((t for t in _in_memory_db["test_runs"] if t["id"] == test_run_id), None)
    pc = next((p for p in _in_memory_db["prompt_configs"] if p.get("test_run_id") == test_run_id), {})

    if tr:
        return {"test_run": tr, "prompt_config": pc}

    # Fall back to Supabase so a fresh/restarted process still resolves existing test runs.
    if get_supabase_client():
        try:
            res = get_supabase_client().table("test_runs").select("*, prompt_configs(*)").eq("id", test_run_id).limit(1).execute()
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
    """Returns existing field_configs for the run, creating defaults from the catalogue where missing.
    
    Also refreshes stale configs to match current field_definitions (fixes legacy target_tolerance configs).
    """
    configs = [c for c in _in_memory_db["field_configs"] if c.get("test_run_id") == test_run_id]
    existing_keys = {c["field_key"] for c in configs}

    # Load any stored configs for this run from Supabase (another serverless instance may own them).
    if get_supabase_client():
        try:
            res = get_supabase_client().table("field_configs").select("*").eq("test_run_id", test_run_id).execute()
            for row in res.data or []:
                if row["field_key"] not in existing_keys:
                    _in_memory_db["field_configs"].append(row)
                    configs.append(row)
                    existing_keys.add(row["field_key"])
        except Exception as e:
            print(f"Supabase get_or_create_field_configs error: {e}")

    # Refresh stale configs to match current field_definitions
    for cfg in configs:
        fk = cfg["field_key"]
        fdef = get_field_definition(fk)
        if not fdef:
            continue
        
        expected_mode = fdef.get("length_mode", "range")
        expected_min = fdef.get("length_min")
        expected_max = fdef.get("length_max")
        expected_unit = fdef.get("unit", "characters")
        
        # Check if config is stale (mode or bounds don't match field_definition)
        is_stale = (
            cfg.get("length_mode") != expected_mode or
            cfg.get("length_min") != expected_min or
            cfg.get("length_max") != expected_max or
            cfg.get("unit") != expected_unit
        )
        
        if is_stale:
            # Update in-memory config
            cfg["length_mode"] = expected_mode
            cfg["length_min"] = expected_min
            cfg["length_max"] = expected_max
            cfg["length_target"] = None
            cfg["length_tolerance_pct"] = None
            cfg["unit"] = expected_unit
            
            # Persist to Supabase
            if get_supabase_client():
                try:
                    get_supabase_client().table("field_configs").update({
                        "length_mode": expected_mode,
                        "length_min": expected_min,
                        "length_max": expected_max,
                        "length_target": None,
                        "length_tolerance_pct": None,
                        "unit": expected_unit
                    }).eq("test_run_id", test_run_id).eq("field_key", fk).execute()
                except Exception as e:
                    print(f"Supabase field_config refresh error for {fk}: {e}")

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
        if get_supabase_client():
            try:
                get_supabase_client().table("field_configs").insert(cfg).execute()
            except Exception as e:
                print(f"Supabase field_config insert error: {e}")

    return configs

def get_field_config(test_run_id: str, field_key: str) -> Optional[Dict[str, Any]]:
    mem = next((c for c in _in_memory_db["field_configs"] if c["test_run_id"] == test_run_id and c["field_key"] == field_key), None)
    if mem:
        return mem
    if get_supabase_client():
        try:
            res = get_supabase_client().table("field_configs").select("*").eq("test_run_id", test_run_id).eq("field_key", field_key).limit(1).execute()
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
    Loads from Supabase (historical) + in-memory (current session).
    """
    runs = []

    # Gather batch rows from Supabase (historical across all serverless instances)
    # and in-memory (current session). In-memory rows override Supabase rows with
    # the same id so the UI always shows the latest state.
    batches_by_id: Dict[str, Dict[str, Any]] = {}
    if get_supabase_client():
        try:
            res = get_supabase_client().table("batches").select("*").eq("test_run_id", test_run_id).order("created_at", desc=True).execute()
            for b in res.data or []:
                batches_by_id[b["id"]] = b
        except Exception as e:
            print(f"Supabase comparison batches query error: {e}")
    for b in _in_memory_db["batches"]:
        if b.get("test_run_id") == test_run_id:
            batches_by_id[b["id"]] = b

    # Attach field jobs (with verification results) for ALL batches in a few
    # chunked queries, instead of one query per batch + one per field job.
    jobs_by_batch = get_batch_field_jobs_bulk(list(batches_by_id.keys())) if batches_by_id else {}
    for bid, b in batches_by_id.items():
        runs.append({
            "batch_id": bid,
            "test_run_id": b.get("test_run_id"),
            "model_name": b.get("model_name"),
            "status": b.get("status"),
            "created_at": b.get("created_at"),
            "fields": jobs_by_batch.get(bid, []),
        })

    return runs


def get_available_languages_for_comparison() -> List[str]:
    """Returns distinct languages from all test_runs that have batches/generations."""
    languages = set()

    # From Supabase
    if get_supabase_client():
        try:
            res = get_supabase_client().table("test_runs").select("language").execute()
            if res.data:
                for tr in res.data:
                    lang = tr.get("language")
                    if lang:
                        languages.add(lang)
        except Exception as e:
            print(f"Supabase get languages error: {e}")

    # From in-memory
    for tr in _in_memory_db["test_runs"]:
        lang = tr.get("language")
        if lang:
            languages.add(lang)

    # Default European languages if none found
    default_langs = ["English", "German", "French", "Spanish", "Italian", "Portuguese", "Dutch", "Polish", "Russian", "Swedish", "Danish", "Finnish", "Greek", "Czech", "Romanian", "Hungarian"]
    for lang in default_langs:
        languages.add(lang)

    return sorted(list(languages))

def create_batch(test_run_id: str, model_name: str) -> str:
    batch_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    batch = {
        "id": batch_id,
        "test_run_id": test_run_id,
        "model_name": model_name,
        "status": "pending",
        "plan_json": None,
        "progress_phase": "initializing",
        "progress_field": None,
        "created_at": now
    }
    client = _get_persistence_client("batch creation")
    if client:
        try:
            client.table("batches").insert(batch).execute()
        except Exception as e:
            if _supabase_is_configured():
                _raise_persistence_error("batch creation", e)
            print(f"Supabase batch insert error: {e}")
    _in_memory_db["batches"].append(batch)
    return batch_id


def update_batch_progress(batch_id: str, progress_phase: str, progress_field: Optional[str] = None):
    """Update batch progress phase and current field being processed."""
    batch = get_batch(batch_id)
    if batch:
        batch["progress_phase"] = progress_phase
        if progress_field is not None:
            batch["progress_field"] = progress_field
    if get_supabase_client():
        try:
            update_data = {"progress_phase": progress_phase}
            if progress_field is not None:
                update_data["progress_field"] = progress_field
            get_supabase_client().table("batches").update(update_data).eq("id", batch_id).execute()
        except Exception as e:
            print(f"Supabase batch progress update error: {e}")

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
    client = _get_persistence_client("field job creation")
    if client:
        try:
            client.table("field_jobs").insert(job).execute()
        except Exception as e:
            if _supabase_is_configured():
                _raise_persistence_error("field job creation", e)
            print(f"Supabase field_job insert error: {e}")
    _in_memory_db["field_jobs"].append(job)
    return job

def update_field_job(field_job_id: str, update_data: Dict[str, Any]):
    job = next((j for j in _in_memory_db["field_jobs"] if j["id"] == field_job_id), None)
    if job:
        job.update(update_data)
        job["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if get_supabase_client():
        try:
            get_supabase_client().table("field_jobs").update(update_data).eq("id", field_job_id).execute()
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
    if get_supabase_client():
        try:
            res = get_supabase_client().table("batches").select("*").eq("id", batch_id).limit(1).execute()
            if res.data:
                return _cache_batch(res.data[0])
        except Exception as e:
            print(f"Supabase get_batch error: {e}")
    return None

def _chunked(ids: List[str], size: int = 50):
    for i in range(0, len(ids), size):
        yield ids[i:i + size]

def list_field_jobs_bulk(batch_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """All field jobs for many batches, fetched in a few chunked queries.

    Avoids the N+1 pattern of calling list_field_jobs() per batch, which makes
    one Supabase round-trip per batch and is extremely slow on serverless.
    """
    by_batch: Dict[str, List[Dict[str, Any]]] = {bid: [] for bid in batch_ids}
    missing = []
    for bid in batch_ids:
        mem = [j for j in _in_memory_db["field_jobs"] if j["batch_id"] == bid]
        if mem:
            by_batch[bid] = mem
        else:
            missing.append(bid)
    if missing and get_supabase_client():
        for chunk in _chunked(missing):
            try:
                res = get_supabase_client().table("field_jobs").select("*").in_("batch_id", chunk).order("created_at").execute()
                for row in res.data or []:
                    if row.get("batch_id") in by_batch:
                        by_batch[row["batch_id"]].append(_cache_field_job(row))
            except Exception as e:
                print(f"Supabase list_field_jobs_bulk error: {e}")
    return by_batch

def get_verification_results_bulk(field_job_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Latest-attempt verification results for many field jobs in a few chunked queries.

    Same semantics as get_verification_results_for_field(), without the per-job
    Supabase round-trip.
    """
    by_job: Dict[str, List[Dict[str, Any]]] = {}
    missing = []
    for fid in field_job_ids:
        mem = [v for v in _in_memory_db["verification_results"] if v.get("field_job_id") == fid]
        by_job[fid] = mem
        if not mem:
            missing.append(fid)
    if missing and get_supabase_client():
        for chunk in _chunked(missing):
            try:
                res = get_supabase_client().table("verification_results").select("*").in_("field_job_id", chunk).order("created_at").execute()
                for row in res.data or []:
                    fid = row.get("field_job_id")
                    if fid in by_job:
                        by_job[fid].append(row)
                        _in_memory_db["verification_results"].append(row)
            except Exception as e:
                print(f"Supabase get_verification_results_bulk error: {e}")
    for fid in field_job_ids:
        mem = by_job.get(fid) or []
        if not mem:
            by_job[fid] = []
            continue
        latest_attempt = max(v.get("verification_attempt", 1) for v in mem)
        by_job[fid] = [v for v in mem if v.get("verification_attempt", 1) == latest_attempt]
    return by_job

def get_batch_field_jobs_bulk(batch_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Per-batch field jobs (with verification results attached) for many batches.

    Same output shape as get_batch_field_jobs(), keyed by batch_id, but fetched
    with a handful of queries instead of one per batch + one per field job.
    """
    jobs_by_batch = list_field_jobs_bulk(batch_ids)
    all_job_ids = [j["id"] for jobs in jobs_by_batch.values() for j in jobs]
    ver_by_job = get_verification_results_bulk(all_job_ids)
    out: Dict[str, List[Dict[str, Any]]] = {}
    for bid in batch_ids:
        out[bid] = [{
            "field_job_id": j["id"],
            "field_key": j["field_key"],
            "status": j["status"],
            "output": j.get("output_json_fragment"),
            "verification_results": ver_by_job.get(j["id"], []),
            "cost": j.get("cost", 0.0),
            "tokens": j.get("tokens", 0),
            "latency_ms": j.get("latency_ms", 0),
        } for j in jobs_by_batch.get(bid, [])]
    return out

def list_field_jobs(batch_id: str) -> List[Dict[str, Any]]:
    """All field jobs for a batch, loading from Supabase on cache miss (serverless-safe)."""
    jobs = [j for j in _in_memory_db["field_jobs"] if j["batch_id"] == batch_id]
    if jobs or not get_supabase_client():
        return jobs
    try:
        res = get_supabase_client().table("field_jobs").select("*").eq("batch_id", batch_id).order("created_at").execute()
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
    if get_supabase_client():
        try:
            res = get_supabase_client().table("field_jobs").select("*").eq("id", field_job_id).limit(1).execute()
            if res.data:
                return _cache_field_job(res.data[0])
        except Exception as e:
            print(f"Supabase get_field_job error: {e}")
    return None

def get_field_job_in_batch(batch_id: str, field_key: str) -> Optional[Dict[str, Any]]:
    """Returns the LATEST field job for a key (reruns create multiple jobs)."""
    jobs = [j for j in list_field_jobs(batch_id) if j["field_key"] == field_key]
    if not jobs:
        return None
    jobs.sort(key=lambda j: j.get("created_at") or "")
    return jobs[-1]

def get_latest_field_jobs(batch_id: str) -> List[Dict[str, Any]]:
    """Returns one LATEST job per field_key for a batch.

    Reruns create multiple jobs for the same field; the UI should show only the
    latest version per field, not a new card every time a field is regenerated.
    """
    jobs = list_field_jobs(batch_id)
    latest = {}
    for j in jobs:
        key = j.get("field_key")
        if key not in latest or (j.get("created_at") or "") > (latest[key].get("created_at") or ""):
            latest[key] = j
    # Preserve the original field order as much as possible (catalogue order).
    return sorted(latest.values(), key=lambda j: (j.get("created_at") or ""))

def update_batch_status(batch_id: str, status: str):
    batch = get_batch(batch_id)
    if batch:
        batch["status"] = status
    if get_supabase_client():
        try:
            get_supabase_client().table("batches").update({"status": status}).eq("id", batch_id).execute()
        except Exception as e:
            print(f"Supabase batch status update error: {e}")

def assemble_batch_output(batch_id: str) -> Optional[Dict[str, Any]]:
    """Build one JSON document from the latest completed field per key."""
    batch = get_batch(batch_id)
    if not batch or batch.get("status") != "completed":
        return None
    jobs = get_latest_field_jobs(batch_id)
    if not jobs or any(j.get("status") not in {"passed", "regenerated_pass"} or j.get("output_json_fragment") is None for j in jobs):
        return None
    return {j["field_key"]: j["output_json_fragment"] for j in jobs}

def get_translation_sources() -> List[Dict[str, Any]]:
    """Return completed English batches and legacy generations as translation sources."""
    sources: Dict[str, Dict[str, Any]] = {}
    for run in get_history_runs():
        if (run.get("language") or "").lower() != "english":
            continue
        if run.get("batch_id"):
            content = assemble_batch_output(run["batch_id"])
            if content is None:
                continue
            source_id = f"batch:{run['batch_id']}"
            sources[source_id] = {
                "source_type": "batch",
                "source_batch_id": run["batch_id"],
                "source_generation_id": None,
                "test_run_id": run.get("test_run_id"),
                "run_id": run["run_id"],
                "country": run.get("country"),
                "city": run.get("city"),
                "source_language": run.get("language", "English"),
                "model_id": run.get("model_id"),
                "model_name": run.get("model"),
                "created_at": run.get("created_at"),
                "source_content": content,
            }
        elif run.get("run_id"):
            detail = get_run_details(run["run_id"])
            generation = (detail or {}).get("generation") or {}
            content = generation.get("output_json")
            if not isinstance(content, dict) or "error" in content or run.get("status", "").lower() in {"failed", "unverified"}:
                continue
            source_id = f"generation:{run['run_id']}"
            sources[source_id] = {
                "source_type": "generation",
                "source_batch_id": None,
                "source_generation_id": run["run_id"],
                "test_run_id": run.get("test_run_id"),
                "run_id": run["run_id"],
                "country": run.get("country"),
                "city": run.get("city"),
                "source_language": run.get("language", "English"),
                "model_id": run.get("model_id"),
                "model_name": run.get("model"),
                "created_at": run.get("created_at"),
                "source_content": content,
            }
    return sorted(sources.values(), key=lambda x: x.get("created_at") or "", reverse=True)

def create_translation(data: Dict[str, Any]) -> str:
    translation_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = {"id": translation_id, **data, "created_at": now, "updated_at": now}
    _in_memory_db["translations"].append(record)
    client = _get_persistence_client("translation creation")
    if client:
        try:
            client.table("translations").insert(record).execute()
        except Exception as e:
            if _supabase_is_configured():
                _raise_persistence_error("translation creation", e)
            print(f"Supabase translation insert error: {e}")
    return translation_id

def update_translation(translation_id: str, updates: Dict[str, Any]) -> None:
    record = next((t for t in _in_memory_db["translations"] if t["id"] == translation_id), None)
    if record:
        record.update(updates)
        record["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if get_supabase_client():
        get_supabase_client().table("translations").update(updates).eq("id", translation_id).execute()

def get_translation_history() -> List[Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    if get_supabase_client():
        try:
            res = get_supabase_client().table("translations").select("*").order("created_at", desc=True).execute()
            records.update({r["id"]: r for r in (res.data or [])})
        except Exception as e:
            print(f"Supabase translation history query error: {e}")
    records.update({r["id"]: r for r in _in_memory_db["translations"]})
    sources = {s.get("source_batch_id") or s.get("source_generation_id"): s for s in get_translation_sources()}
    result = []
    for record in records.values():
        source = sources.get(record.get("source_batch_id") or record.get("source_generation_id"), {})
        result.append({**record, "country": source.get("country"), "city": source.get("city"), "source_model": source.get("model_name")})
    return sorted(result, key=lambda x: x.get("created_at") or "", reverse=True)

def get_translation(translation_id: str) -> Optional[Dict[str, Any]]:
    record = next((t for t in _in_memory_db["translations"] if t["id"] == translation_id), None)
    if not record and get_supabase_client():
        res = get_supabase_client().table("translations").select("*").eq("id", translation_id).limit(1).execute()
        record = res.data[0] if res.data else None
    if not record:
        return None
    source_id = record.get("source_batch_id") or record.get("source_generation_id")
    source = next((s for s in get_translation_sources() if s.get("source_batch_id") == source_id or s.get("source_generation_id") == source_id), None)
    return {"translation": record, "source": source}

def get_translation_languages() -> List[str]:
    languages = {"English", "Spanish", "French", "German", "Italian", "Portuguese", "Dutch", "Russian", "Polish", "Swedish", "Danish", "Finnish", "Greek", "Czech", "Romanian", "Hungarian"}
    languages.update(t.get("target_language") for t in _in_memory_db["translations"] if t.get("target_language"))
    return sorted(languages)

def get_translation_comparisons(target_language: str, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = [r for r in get_translation_history() if r.get("target_language") == target_language and r.get("status") == "completed"]
    if source_id:
        rows = [r for r in rows if r.get("source_batch_id") == source_id or r.get("source_generation_id") == source_id]
    return [{**r, "source_content": r.get("source_content"), "translated_content": r.get("output_json")} for r in rows]

def update_batch_plan(batch_id: str, plan_json: Optional[Dict[str, Any]]):
    """Stores the Semantic Consistency Planner result on the batch for audit/debugging."""
    batch = get_batch(batch_id)
    if batch:
        batch["plan_json"] = plan_json
    if get_supabase_client():
        try:
            get_supabase_client().table("batches").update({"plan_json": plan_json}).eq("id", batch_id).execute()
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
    if get_supabase_client():
        try:
            get_supabase_client().table("verification_results").insert(records).execute()
        except Exception as e:
            print(f"Supabase scoped verification insert error: {e}")

def get_verification_results_for_field(field_job_id: str) -> List[Dict[str, Any]]:
    """Returns ONLY the latest verification attempt's results for a field job.

    Initial verify (attempt 1) and regeneration verify (attempt 2+) both save
    results for the same job. The UI should show only the latest verdict, not
    every historical attempt stacked on top of each other.
    """
    mem = [v for v in _in_memory_db["verification_results"] if v.get("field_job_id") == field_job_id]

    if not mem and get_supabase_client():
        try:
            res = get_supabase_client().table("verification_results").select("*").eq("field_job_id", field_job_id).order("created_at").execute()
            for row in res.data or []:
                _in_memory_db["verification_results"].append(row)
            mem = [row for row in (res.data or [])]
        except Exception as e:
            print(f"Supabase get_verification_results_for_field error: {e}")

    if not mem:
        return mem

    latest_attempt = max(v.get("verification_attempt", 1) for v in mem)
    return [v for v in mem if v.get("verification_attempt", 1) == latest_attempt]

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
    if get_supabase_client():
        try:
            get_supabase_client().table("regenerations").insert(rec).execute()
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
    if not get_supabase_client():
        for j in list_field_jobs(batch_id):
            if j.get("status") == "queued":
                update_field_job(j["id"], {"status": "running", "updated_at": now})
                return get_field_job(j["id"])
        return None

    try:
        # Pick the oldest queued job…
        sel = get_supabase_client().table("field_jobs").select("id").eq("batch_id", batch_id).eq("status", "queued").order("created_at").limit(1).execute()
        if not sel.data:
            return None
        cand_id = sel.data[0]["id"]
        # …and claim it conditionally so only one concurrent instance wins.
        upd = get_supabase_client().table("field_jobs").update({"status": "running", "updated_at": now}).eq("id", cand_id).eq("status", "queued").execute()
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
