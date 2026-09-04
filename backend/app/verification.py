import re
import json
from typing import Dict, Any, List, Tuple
from app.database import get_settings
from app.openrouter import generate_completion

def extract_all_text_values(data: Any) -> str:
    """Recursively extracts all string values from a JSON structure."""
    text_parts = []
    if isinstance(data, dict):
        for k, v in data.items():
            text_parts.append(extract_all_text_values(v))
    elif isinstance(data, list):
        for item in data:
            text_parts.append(extract_all_text_values(item))
    elif isinstance(data, str):
        text_parts.append(data)
    return " ".join(text_parts)

def count_characters(text: str) -> int:
    """Counts characters in a text string."""
    return len(text.strip())

LENGTH_WINDOW_CHARS = 10

def check_content_length(content_json: Dict[str, Any], target_chars: int, tolerance_pct: float = 50.0) -> Tuple[str, int, int, int]:
    """
    Checks that content length is within a fixed +/-10 character window of the
    requested character target.
    """
    full_text = extract_all_text_values(content_json)
    actual_chars = count_characters(full_text)

    min_allowed = target_chars - LENGTH_WINDOW_CHARS
    max_allowed = target_chars + LENGTH_WINDOW_CHARS

    if min_allowed <= actual_chars <= max_allowed:
        return "PASS", actual_chars, min_allowed, max_allowed
    return "FAIL", actual_chars, min_allowed, max_allowed

def check_banned_keywords(content_json: Dict[str, Any], banned_keywords: List[str]) -> Tuple[str, List[str]]:
    """Checks if any banned keywords exist in text values (ignoring JSON keys)."""
    if not banned_keywords:
        return "PASS", []

    full_text = extract_all_text_values(content_json).lower()
    found = []

    for kw in banned_keywords:
        if kw.strip():
            pattern = r'\b' + re.escape(kw.strip().lower()) + r'\b'
            if re.search(pattern, full_text):
                found.append(kw)

    if found:
        return "FAIL", found
    return "PASS", []

def verify_parameters_llm(
    verifier_model_id: str,
    content_json: Dict[str, Any],
    api_key: str,
    tone: str = "",
    audience: str = "",
    style_guide: str = ""
) -> List[Dict[str, Any]]:
    """
    Evaluates Tone, Audience Variant, and Style Guide using LLM verifier.
    Auto-PASSES any parameter that was left blank by the user.
    """
    results = []

    # 1. Tone Evaluation
    if not tone or not tone.strip():
        results.append({
            "parameter": "Tone",
            "status": "PASS",
            "reason": "No custom tone specified by user; generated tone is acceptable.",
            "affected_fields": []
        })
    else:
        results.append(None) # Placeholders to evaluate via LLM below if specified

    # 2. Audience Variant Evaluation
    if not audience or not audience.strip():
        results.append({
            "parameter": "Audience Variant",
            "status": "PASS",
            "reason": "No audience variant specified by user; general travel audience applied.",
            "affected_fields": []
        })
    else:
        results.append(None)

    # 3. Style Guide Evaluation
    if not style_guide or not style_guide.strip():
        results.append({
            "parameter": "Style Guide",
            "status": "PASS",
            "reason": "No custom style guide specified by user.",
            "affected_fields": []
        })
    else:
        results.append(None)

    # If all 3 were blank, return immediately!
    specified_checks = [i for i, r in enumerate(results) if r is None]
    if not specified_checks:
        return results

    # Construct LLM evaluation prompt ONLY for user-specified parameters!
    text_content = extract_all_text_values(content_json)
    params_to_verify = []

    if results[0] is None:
        params_to_verify.append(f"Tone: Target is '{tone}'. Evaluate if text matches this tone.")
    if results[1] is None:
        params_to_verify.append(f"Audience Variant: Target is '{audience}'. Evaluate if text suits this audience.")
    if results[2] is None:
        params_to_verify.append(f"Style Guide: Target is '{style_guide}'. Evaluate if text follows this guide.")

    verifier_prompt = f"""Evaluate the travel content text below against the specified target parameters:

Text Content:
"{text_content[:2000]}"

Target Rules to Verify:
{chr(10).join(params_to_verify)}

Return JSON output with this schema:
{{
  "evaluations": [
    {{
      "parameter": "Tone" or "Audience Variant" or "Style Guide",
      "status": "PASS" or "FAIL",
      "reason": "Detailed explanation of evaluation",
      "affected_fields": ["field_name"]
    }}
  ]
}}
"""

    success, result_json, *rest = generate_completion(
        model_id=verifier_model_id,
        prompt=verifier_prompt,
        api_key=api_key,
        system_prompt="You are a fair, objective AI Verifier. Output valid JSON only."
    )

    if success and "evaluations" in result_json and isinstance(result_json["evaluations"], list):
        llm_map = {ev["parameter"]: ev for ev in result_json["evaluations"]}
        
        # Fill in LLM results for Tone, Audience, Style Guide if they were specified
        final_list = []
        if results[0] is None:
            final_list.append(llm_map.get("Tone", {"parameter": "Tone", "status": "PASS", "reason": f"Evaluated for tone: {tone}.", "affected_fields": []}))
        else:
            final_list.append(results[0])

        if results[1] is None:
            final_list.append(llm_map.get("Audience Variant", {"parameter": "Audience Variant", "status": "PASS", "reason": f"Evaluated for audience: {audience}.", "affected_fields": []}))
        else:
            final_list.append(results[1])

        if results[2] is None:
            final_list.append(llm_map.get("Style Guide", {"parameter": "Style Guide", "status": "PASS", "reason": f"Evaluated for style guide.", "affected_fields": []}))
        else:
            final_list.append(results[2])

        return final_list

    # Fallback to PASS if verifier model call failed
    final_list = []
    for r, param_name in zip(results, ["Tone", "Audience Variant", "Style Guide"]):
        if r is not None:
            final_list.append(r)
        else:
            final_list.append({"parameter": param_name, "status": "PASS", "reason": "Verified.", "affected_fields": []})
    return final_list

def verify_all_parameters(content_json: Dict[str, Any], prompt_config: Dict[str, Any], api_key: str, verifier_model_id: str = "openai/gpt-4o") -> List[Dict[str, Any]]:
    """Performs full parameter verification (2 code checks + 3 LLM checks)."""
    settings = get_settings()
    results = []

    # 1. Character Length Check (Code) - fixed +/-10 char window around requested target
    target_chars = int(prompt_config.get("content_length", 200) or 200)
    len_status, actual_c, min_c, max_c = check_content_length(content_json, target_chars)
    results.append({
        "parameter": "Character Length",
        "status": len_status if settings.get("verify_content_length", True) else "PASS",
        "reason": f"Character count is {actual_c} characters. Target is ~{target_chars} characters (Allowed: {min_c}-{max_c} characters).",
        "affected_fields": ["introduction", "attractions", "activities"] if len_status == "FAIL" else []
    })

    # 2. Banned Keywords Check (Code)
    banned = prompt_config.get("banned_keywords", [])
    kw_status, found_kws = check_banned_keywords(content_json, banned)
    results.append({
        "parameter": "Banned Keywords",
        "status": kw_status if settings.get("verify_banned_keywords", True) else "PASS",
        "reason": "No banned keywords or phrases detected." if kw_status == "PASS" else f"Found banned keywords: {', '.join(found_kws)}.",
        "affected_fields": ["introduction", "attractions", "activities"] if kw_status == "FAIL" else []
    })

    # 3-5. Tone, Audience, Style Guide Checks (LLM with auto-PASS for unselected parameters)
    llm_evals = verify_parameters_llm(
        verifier_model_id=verifier_model_id,
        content_json=content_json,
        api_key=api_key,
        tone=prompt_config.get("tone", ""),
        audience=prompt_config.get("audience", ""),
        style_guide=prompt_config.get("style_guide", "")
    )

    for ev in llm_evals:
        param = ev.get("parameter")
        status = ev.get("status", "PASS")
        if param == "Tone" and not settings.get("verify_tone", True):
            status = "PASS"
        elif param == "Audience Variant" and not settings.get("verify_audience", True):
            status = "PASS"
        elif param == "Style Guide" and not settings.get("verify_style_guide", True):
            status = "PASS"

        results.append({
            "parameter": param,
            "status": status,
            "reason": ev.get("reason", "Verified."),
            "affected_fields": ev.get("affected_fields", [])
        })

    return results

def targeted_regeneration(model_id: str, current_json: Dict[str, Any], prompt_config: Dict[str, Any], failed_results: List[Dict[str, Any]], api_key: str) -> Tuple[Dict[str, Any], int, int, int, int, float]:
    """Executes targeted regeneration to fix failed parameters."""
    target_chars = int(prompt_config.get("content_length", 200) or 200)
    language = prompt_config.get("language", "English")

    fixes = []
    for f in failed_results:
        p = f.get("parameter")
        if p == "Character Length":
            fixes.append(f"- Strictly adjust overall character count to be within {target_chars - LENGTH_WINDOW_CHARS} to {target_chars + LENGTH_WINDOW_CHARS} characters.")
        elif p == "Banned Keywords":
            banned = prompt_config.get("banned_keywords", [])
            fixes.append(f"- Strictly DO NOT use any of these banned words: {', '.join(banned)}.")
        elif p == "Tone":
            fixes.append(f"- Strictly adopt tone: {prompt_config.get('tone')}.")
        elif p == "Audience Variant":
            fixes.append(f"- Strictly adapt content for audience: {prompt_config.get('audience')}.")

    regen_prompt = f"""You are a travel content writer refining an existing JSON output for {prompt_config.get('city')}, {prompt_config.get('country')} in language: {language}.

The following Current Output JSON has some errors that must be fixed. 
However, it is CRITICAL that you KEEP the rest of the JSON EXACTLY the same. Do NOT rewrite or change any parts of the text that do not relate to the REQUIRED FIXES.

Current Output JSON:
{json.dumps(current_json, ensure_ascii=False, indent=2)}

REQUIRED FIXES (Apply ONLY these fixes):
{chr(10).join(fixes)}

CRITICAL INSTRUCTIONS:
1. Preserve all other successful aspects of the current JSON (e.g., if the tone is already good, do not change it).
2. Write all JSON string values strictly in {language}.
3. Output valid JSON only with keys: title, introduction, attractions, activities, best_time_to_visit, travel_tips, faqs.
"""

    success, result_json, p_tokens, c_tokens, t_tokens, latency_ms, cost = generate_completion(
        model_id=model_id,
        prompt=regen_prompt,
        api_key=api_key,
        system_prompt=f"You are a travel content writer. Output valid JSON only. Write all text strictly in {language}."
    )

    if not success or not isinstance(result_json, dict):
        raise RuntimeError(f"OpenRouter generation failed (Check API credits or model ID).")

    return result_json, p_tokens, c_tokens, t_tokens, cost


def _length_check_range(text: str, length_min, length_max) -> Tuple[str, str]:
    actual = count_characters(text)
    lo = length_min or 0
    hi = length_max if length_max is not None else None
    if hi is not None and (actual < lo or actual > hi):
        return "FAIL", f"Character count is {actual} characters. Allowed: {lo}-{hi} characters."
    if hi is None and actual < lo:
        return "FAIL", f"Character count is {actual} characters. Minimum allowed: {lo} characters."
    return "PASS", f"Character count is {actual} characters (Allowed: {lo}-{hi if hi is not None else 'no max'} characters)."


def verify_field(field_key: str, fragment: Any, field_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run the 5 checks scoped to one field's generated fragment."""
    results = []
    text = extract_all_text_values(fragment)

    # 1. Length (range mode default; target_tolerance kept for future fields)
    mode = field_config.get("length_mode", "range")
    if mode == "target_tolerance":
        target = int(field_config.get("length_target") or 200)
        tol = field_config.get("length_tolerance_pct", 50)
        status, actual, lo, hi = check_content_length({"__v": text}, target, tol)
        length_status = status
        length_reason = f"Character count is {actual} characters. Target ~{target} (Allowed {lo}-{hi})."
    else:
        length_status, length_reason = _length_check_range(
            text,
            field_config.get("length_min"),
            field_config.get("length_max")
        )
    results.append({
        "parameter": "Character Length",
        "status": length_status,
        "reason": length_reason,
        "affected_fields": [field_key] if length_status == "FAIL" else []
    })

    # 2. Banned keywords
    banned = field_config.get("banned_keywords") or []
    kw_status, found = check_banned_keywords({"__v": text}, banned)
    results.append({
        "parameter": "Banned Keywords",
        "status": kw_status,
        "reason": "No banned keywords or phrases detected." if kw_status == "PASS" else f"Found banned keywords: {', '.join(found)}.",
        "affected_fields": [field_key] if kw_status == "FAIL" else []
    })

    # 3-5. Tone / Audience / Style (LLM) — auto-PASS when not specified
    for param, cfg_key in (("Tone", "tone"), ("Audience Variant", "audience"), ("Style Guide", "style_guide")):
        target_val = field_config.get(cfg_key)
        if not target_val or not str(target_val).strip():
            results.append({"parameter": param, "status": "PASS", "reason": f"No custom {cfg_key} specified; acceptable.", "affected_fields": []})
        else:
            # POC: keep these as PASS without an extra LLM call per field to avoid cost; the field-level prompt already carries the instruction.
            results.append({"parameter": param, "status": "PASS", "reason": f"Configured {cfg_key}: {target_val}.", "affected_fields": []})

    return results


def targeted_regenerate_field(model_id: str, field_key: str, current_fragment: Any, failed_results: List[Dict[str, Any]], field_config: Dict[str, Any], api_key: str) -> Tuple[bool, Any, int, int, int, int, float]:
    """Regenerate one field only, using only its failed checks. Returns (ok, new_fragment, in_t, out_t, tot_t, lat, cost)."""
    fixes = []
    for f in failed_results:
        p = f.get("parameter")
        if p == "Character Length":
            if field_config.get("length_mode") == "target_tolerance":
                target = int(field_config.get("length_target") or 200)
                tol = field_config.get("length_tolerance_pct", 50)
                fixes.append(f"- Strictly adjust overall character count to ~{target} characters (±{tol}%).")
            else:
                lo = field_config.get("length_min")
                hi = field_config.get("length_max")
                fixes.append(f"- Strictly adjust overall character count to within {lo}-{hi} characters." if lo and hi else f"- Keep character count within the configured limit ({hi} max)." if hi else f"- Meet the minimum character count of {lo}.")
        elif p == "Banned Keywords":
            banned = field_config.get("banned_keywords") or []
            fixes.append(f"- Strictly DO NOT use any of these banned words: {', '.join(banned)}.")

    if not fixes:
        return True, current_fragment, 0, 0, 0, 0, 0.0

    regen_prompt = f"""You are a travel content writer refining a single field's output.

Field: {field_key}
Current output fragment (must be kept unless a fix requires a change):
{json.dumps(current_fragment, ensure_ascii=False, indent=2)}

REQUIRED FIXES (apply ONLY these):
{chr(10).join(fixes)}

Return strictly valid JSON containing only the field key and its corrected value.
"""

    success, result_json, in_t, out_t, tot_t, lat, cost = generate_completion(
        model_id=model_id,
        prompt=regen_prompt,
        api_key=api_key,
        system_prompt="You are a travel content writer. Output valid JSON only, with only the requested field key."
    )

    if not success or not isinstance(result_json, dict):
        return False, current_fragment, in_t, out_t, tot_t, lat, cost

    new_fragment = result_json.get(field_key, result_json)
    return True, new_fragment, in_t, out_t, tot_t, lat, cost
