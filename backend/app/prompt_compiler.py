import json
from typing import Dict, Any, List
from app.database import get_field_definition


# Per-field JSON sub-schema keys (the output JSON object only carries this field's content)
FIELD_SUB_SCHEMA = {
    "meta_title": {"meta_title": "string"},
    "meta_description": {"meta_description": "string"},
    "snippet": {"snippet": "string"},
    "intro_paragraph": {"intro_paragraph": "string"},
    "long_description": {"long_description": "string"},
    "option_name": {"option_name": "string"},
    "option_description": {"option_description": "string"},
    "highlight_bullet": {"highlight_bullet": "string"},
    "faq_answer": {"faq_answer": "string"},
    "faq_city": {"faq_city": {"question": "string", "answer": "string"}},
}

# Human instructions per field; keeps each field's generation scoped to its own goal.
FIELD_INSTRUCTIONS = {
    "meta_title": "a single SEO meta title",
    "meta_description": "a single meta description",
    "snippet": "a single one-sentence hero snippet",
    "intro_paragraph": "an introductory paragraph",
    "long_description": "a long-form descriptive paragraph",
    "option_name": "a short product/tour option name",
    "option_description": "a short option description",
    "highlight_bullet": "a single highlight bullet",
    "faq_answer": "a single FAQ answer",
    "faq_city": "one city-specific FAQ question and answer",
}


def _length_instruction(field_key: str, cfg: Dict[str, Any]) -> str:
    """Renders the field's min/max length constraint as natural language."""
    mode = cfg.get("length_mode", "range")
    unit = cfg.get("unit", "characters")
    if mode == "range":
        lo = cfg.get("length_min")
        hi = cfg.get("length_max")
        if lo and hi:
            return f"between {lo} and {hi} {unit}"
        if hi:
            return f"at most {hi} {unit}"
        if lo:
            return f"at least {lo} {unit}"
        return "appropriate length"
    # target_tolerance mode (kept for future word-mode fields)
    target = cfg.get("length_target")
    tol = cfg.get("length_tolerance_pct")
    if target and tol is not None:
        return f"approximately {target} {unit} (±{tol}%)"
    if target:
        return f"approximately {target} {unit}"
    return "appropriate length"


def resolve_field_config(global_default: Dict[str, Any], field_override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge global default with per-field override; override wins where explicitly set."""
    resolved = dict(global_default or {})

    # Length always resolves to concrete per-field numbers
    if field_override.get("length_mode") == "range":
        resolved["length_mode"] = "range"
        resolved["length_min"] = field_override.get("length_min")
        resolved["length_max"] = field_override.get("length_max")
        resolved["unit"] = field_override.get("unit", "characters")
    elif field_override.get("length_mode") == "target_tolerance":
        resolved["length_mode"] = "target_tolerance"
        resolved["length_target"] = field_override.get("length_target")
        resolved["length_tolerance_pct"] = field_override.get("length_tolerance_pct")
        resolved["unit"] = field_override.get("unit", "characters")

    for param in ("tone", "audience", "banned_keywords", "style_guide"):
        if field_override.get(f"{param}_override"):
            resolved[param] = field_override.get(param)

    return resolved


def compile_field_prompt(input_json: Dict[str, Any], field_key: str, resolved_config: Dict[str, Any]) -> Dict[str, str]:
    """Build System + User prompt for ONE field only, grounded in the shared source JSON."""
    fdef = get_field_definition(field_key) or {}
    label = fdef.get("label", field_key)
    instruction = FIELD_INSTRUCTIONS.get(field_key, f"content for {field_key}")
    sub_schema = FIELD_SUB_SCHEMA.get(field_key, {field_key: "string"})

    language = resolved_config.get("language") or resolved_config.get("target_language") or "English"
    tone = resolved_config.get("tone", "")
    audience = resolved_config.get("audience", "")
    banned = resolved_config.get("banned_keywords", []) or []
    style = resolved_config.get("style_guide", "")
    length_rule = _length_instruction(field_key, resolved_config)

    # Compact facts brief: real city/attraction names so the model does not invent them.
    city = input_json.get("city") or input_json.get("name") or ""
    country = input_json.get("country") or ""
    attraction_names = []
    attractions = input_json.get("attractions") or []
    if isinstance(attractions, list):
        for a in attractions:
            if isinstance(a, dict):
                attraction_names.append(a.get("name") or a.get("title") or "")
            elif isinstance(a, str):
                attraction_names.append(a)
    attraction_names = [n for n in attraction_names if n]

    facts_brief_lines = [f"Destination: {city}, {country}".strip(", ")]
    if attraction_names:
        facts_brief_lines.append("Real attractions (use only these names): " + ", ".join(attraction_names))
    facts_brief = "\n".join(facts_brief_lines)

    system_prompt = (
        f"You are a professional travel content writer for RosoTravel.\n"
        f"CRITICAL LANGUAGE MANDATE:\n"
        f"Write ALL text values in the JSON output strictly in {language}. "
        f"Do NOT write in English unless the target language is English.\n"
    )

    user_parts = [
        f"Generate {instruction} for this destination.",
        f"FACTS BRIEF (ground your content in these real names; do not invent named places):\n{facts_brief}",
        f"LENGTH: {length_rule}.",
    ]
    if tone:
        user_parts.append(f"Tone: {tone}")
    if audience:
        user_parts.append(f"Audience Variant: {audience}")
    if banned:
        user_parts.append("BANNED KEYWORDS (CRITICAL: DO NOT USE ANY OF THESE WORDS):\n" + "\n".join("- " + str(k) for k in banned))
    if style:
        user_parts.append(f"Style Guide:\n{style}")
    user_parts.append(
        f"Return strictly valid JSON only, matching this exact schema:\n"
        f"{json.dumps(sub_schema)}\n"
        f"Do not wrap the JSON in markdown code fences."
    )

    return {
        "field_key": field_key,
        "label": label,
        "system_prompt": system_prompt,
        "user_prompt": "\n\n".join(user_parts),
    }


def compile_batch_prompts(input_json: Dict[str, Any], field_keys: List[str], global_default: Dict[str, Any], field_overrides: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
    """Compile (no execution) one prompt per requested field."""
    out = []
    for fk in field_keys:
        override = field_overrides.get(fk, {})
        resolved = resolve_field_config(global_default, override)
        out.append(compile_field_prompt(input_json, fk, resolved))
    return out
