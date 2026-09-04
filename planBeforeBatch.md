# Semantic Consistency Planner — Reference

The "planner" is a single LLM call that runs **once per batch, before any field generation starts**.
Its job is to keep the independently-generated field outputs from reading like disconnected pieces —
avoiding repeated facts, inconsistent tone, and inconsistent naming of the same attraction.

This file tells you exactly what the planner does, what parameters control it, and where to change them.

---

## 1. Where the code lives

| File | What it owns |
|---|---|
| `backend/app/prompt_compiler.py` | The planner prompt, plan schema, and per-field slicing |
| `backend/app/batch_engine.py` | Runs the planner, stores the plan, injects slices into field prompts |
| `backend/app/database.py` | `batches.plan_json` column + `update_batch_plan()` |
| `backend/setup_db.py` | `plan_json JSONB` migration |

---

## 2. The flow (when you click "Run Batch")

1. `generate-batch` creates a `batches` row + N `field_jobs` (with the user-edited prompts).
2. `_run_async` runs `_generate_plan()` **once** — before any field job.
3. The planner returns a **Content Plan** JSON, which is stored on `batches.plan_json`.
4. Each field job's **System prompt** gets a small "SHARED CONTEXT" block appended:
   - the shared `narrative_core` (same for every field), and
   - **only that field's** `fact_allocation` slice (never the full map).
5. Then the N field jobs run concurrently as before.

If the planner fails or times out, the batch still runs — just without the shared context ("unplanned"). A warning is logged on `batches.plan_json`.

---

## 3. The Content Plan JSON shape

```json
{
  "narrative_core": "150-250 char string: overall angle/hook, tone anchor with 1-2 example phrasing lines, and naming conventions",
  "fact_allocation": {
    "meta_title": ["fact string assigned ONLY to meta_title"],
    "snippet": ["fact string assigned ONLY to snippet"],
    "...": ["..."]
  }
}
```

- `narrative_core` — shared by all fields. Keep it small (~150–250 chars).
- `fact_allocation` — a map of `field_key -> [fact strings]`. Each source fact should be assigned to **exactly one field** so it isn't repeated.

Only the slice `{ narrative_core, fact_allocation[this_field_key] }` is injected into any single field's prompt.

---

## 4. Parameters you can change (and where)

### 4.1 The planner prompt itself

**File:** `backend/app/prompt_compiler.py` → `build_planner_prompt()`

The whole prompt is built here. Change any of:

- The system role text: `"You are a content planner for RosoTravel..."`
- The per-field summary format (what the planner is told about each field)
- The RULES block (e.g. "Assign each source fact to EXACTLY ONE field")

The JSON schema instructions are hardcoded in that function, in this string:

```python
'{"narrative_core": "...", "fact_allocation": {"field_key": ["..."], ...}}'
```

Change that string if you want the planner to emit a different shape.

### 4.2 The `narrative_core` size

**File:** `backend/app/prompt_compiler.py` → `build_planner_prompt()`

The `"150-250 char string"` text is a prompt instruction, not an enforced limit. To change the target size, edit that string (and the RULES line that says `narrative_core must be 150-250 characters`). There is no hard truncation in code.

### 4.3 Which model runs the planner

**File:** `backend/app/batch_engine.py` → `_generate_plan()`

The planner uses **the same model as the batch** (`model_name`), which is the model you selected in the UI. If you want a dedicated/cheaper planner model, change this call:

```python
success, result_json, *_ = generate_completion(
    model_id=model_name,   # <-- change to a fixed model id if desired
    prompt=prompt,
    api_key=api_key,
    system_prompt="You are a travel content planner. Output valid JSON only."
)
```

### 4.4 Planner system prompt

**File:** `backend/app/batch_engine.py` → `_generate_plan()`

The `system_prompt="You are a travel content planner. Output valid JSON only."` is separate from the user prompt. Change wording here.

### 4.5 Failure / fallback behavior

**File:** `backend/app/batch_engine.py` → `_generate_plan()`

Currently: any failure → `None` → batch continues "unplanned" + a warning is stored. To make the planner **blocking** (fail the whole batch on planner error), change this section instead of returning `None`.

### 4.6 How the slice is injected into field prompts

**File:** `backend/app/batch_engine.py` → `_apply_plan_to_prompt()`

This controls the exact "SHARED CONTEXT" block wording, and whether it goes into the System prompt (it currently does). Change:
- The header text `"SHARED CONTEXT (for batch coherence):"`
- The labels `NARRATIVE CORE` / `FACTS ASSIGNED TO THIS FIELD ONLY`

### 4.7 Where the plan is persisted

**File:** `backend/app/database.py` → `update_batch_plan()`

Writes to in-memory + Supabase `batches.plan_json`. The schema migration lives in `backend/setup_db.py`.

---

## 5. Important token-budget rule (don't break this)

The full plan is **never** injected into every field prompt. Each field gets:

- the fixed-size `narrative_core` (~150–250 chars), plus
- **only its own** `fact_allocation` slice.

This is why `slice_plan_for_field()` exists. If you change injection, keep this per-field slicing — otherwise prompt size grows linearly with field count and defeats the design.

---

## 6. Quick "where to change what" table

| I want to change... | Go to |
|---|---|
| Planner instructions / rules | `prompt_compiler.py` → `build_planner_prompt()` |
| `narrative_core` length target | `prompt_compiler.py` → `build_planner_prompt()` |
| Planner model | `batch_engine.py` → `_generate_plan()` |
| Planner system prompt | `batch_engine.py` → `_generate_plan()` |
| Fail-open vs fail-closed | `batch_engine.py` → `_generate_plan()` |
| Injected block wording | `batch_engine.py` → `_apply_plan_to_prompt()` |
| Plan JSON schema | `prompt_compiler.py` → `build_planner_prompt()` |
| Where plan is stored | `database.py` → `update_batch_plan()` |
| DB column | `setup_db.py` (`plan_json JSONB`) |
