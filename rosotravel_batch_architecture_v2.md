# RosoTravel AI Model Comparison POC — Batch / Per-Field Generation Update (v2)

> **Purpose of this document:** This is a change spec for a coding agent. It describes exactly what must change from the current single-run architecture (see `logic_and_architecture.md`) to a **per-field batch generation** model, including data model, backend flow, API contracts, and UI changes. Implement in the order given in Section 9 (Implementation Plan).

---

## 1. Summary of the Change

**Current behavior:** One JSON input → one compiled prompt (with one global Tone/Audience/Length/Keywords config) → one LLM call → one verification pass → one output JSON with all fields (Title, Introduction, Attractions, Activities, Best Time, Tips, FAQs).

**New required behavior:**

1. The page (e.g. a City Page) is broken into **Sections/Fields** (Title, Introduction, Attractions, Activities, Best Time, Tips, FAQs — configurable, not hardcoded).
2. **Each Field gets its own independent prompt configuration**: its own Target Word/Char Length, its own Tone, Audience, Banned Keywords, Style Guide (all optional overrides — see Section 3.2 for inheritance).
3. **Character/word length is removed from the Source Data / Input JSON step.** Length is now purely a per-field *generation parameter*, not part of the input payload.
4. Before execution, the UI must show **one prompt-preview block per field** (not a single combined prompt), each independently readable and **editable** by the user.
5. Execution is **always batch** — even if there is only one field — but the user only sees a single **"Run Batch"** button. There is no per-field "run individually" button; running one field alone is just a batch of size 1 conceptually, but the UI does not need a separate control for it (see Section 8.4 for the one exception: allow re-running a single failed field without re-running the whole batch).
6. The backend must generate, verify, and (if needed) regenerate **each field independently**, and report per-field status back to the UI as the batch progresses (not just one final blob).
7. Persistence must now be **per-field**, not per whole-output — every generation, verification, and regeneration record must be scoped to a `field_key` inside a batch/run.

---

## 2. Key Concepts & Terminology (new)

| Term | Meaning |
|---|---|
| **Test Run** | Same as before: grouped by `country + city + language`. Now also owns a **Batch**. |
| **Batch** | One execution cycle of "Run Batch". Contains N **Field Jobs**, one per configured field/section. |
| **Field** | A schema key to generate (e.g. `title`, `introduction`, `attractions`, `activities`, `best_time`, `tips`, `faqs`). Field list is config-driven, not hardcoded, so new fields can be added later without code changes. |
| **Field Config** | Per-field generation parameters: Target Length (words or chars — configurable unit), Tolerance %, Tone, Audience, Banned Keywords, Style Guide. Each is either **explicit** (set at field level) or **inherited** from a Global Default Config (see 3.2). |
| **Field Job** | One field's full lifecycle inside a batch: compiled prompt → generation → verification → (optional) regeneration → final status. |
| **Compiled Field Prompt** | The exact System + User prompt string for one field, shown to the user pre-execution, and editable before "Run Batch" is clicked. |

---

## 3. Data Model Changes

### 3.1 Remove from Source Data Input
- Remove `Target Word Count` / `Character Length` and `Tolerance %` from the **Source Data Block** (Left Column, Section 5.1 item 2 in the old doc).
- The Source Data Block now only contains: raw source JSON (facts about the city — attractions list, activity list, raw notes, etc.), Country/City/Language selectors. It is pure *content input*, no generation-control fields.

### 3.2 New: Field Configuration Layer
Introduce a **Global Default Config** (Tone, Audience, Length, Tolerance %, Banned Keywords, Style Guide) — this replaces what used to be "the one config for everything."

Then introduce a **Per-Field Override Config** for every field in the schema:
- Each param (Length, Tolerance, Tone, Audience, Banned Keywords, Style Guide) can be:
  - `inherit` (use Global Default), or
  - `override` (explicit value just for this field).
- UI default: all fields start as `inherit`; user can expand any field to override.
- **Length must always resolve to a concrete number per field** before prompt compilation (either inherited or overridden) — there is no "no length" state per field.

### 3.3 Database Schema Changes (Supabase / In-Memory)

Modify/add tables:

- **`test_runs`** — unchanged (Location, Language, Input JSON, minus length/tolerance which move out).
- **`field_definitions`** (NEW) — config-driven list of fields available for a schema/page type: `id`, `field_key`, `label`, `default_order`, `schema_type` (e.g. `city_page`). Lets the field list be edited without redeploying.
- **`prompt_configs`** — becomes the **Global Default Config**, tied to a Test Run: Tone, Audience, Length, Tolerance %, Banned Keywords, Style Guide (all now defaults/fallbacks, not final values).
- **`field_configs`** (NEW) — one row per `(test_run_id, field_key)`: `is_override` boolean per param, and the override value if set (Tone, Audience, Length, Tolerance %, Banned Keywords, Style Guide). This is what actually drives prompt compilation for that field.
- **`batches`** (NEW) — one row per "Run Batch" click: `id`, `test_run_id`, `model_name`, `status` (pending/running/completed/partial_failure/failed), `created_at`.
- **`field_jobs`** (NEW, replaces flat `generations` for the per-field granularity) — one row per field per batch: `id`, `batch_id`, `field_key`, `compiled_system_prompt`, `compiled_user_prompt` (as edited by user, snapshot at execute time), `status` (queued/running/passed/failed/regenerating/regenerated_pass/regenerated_fail), `output_json_fragment`, `cost`, `tokens`, `latency_ms`.
- **`verification_results`** — add `field_job_id` FK (replacing/alongside the old generation FK) so every PASS/FAIL check is scoped to one field's job.
- **`regenerations`** — add `field_job_id` FK; snapshot before/after is now per field, not per whole document.
- **`app_settings`** — unchanged (global engine toggles, verifier model, etc.)

> Migration note: keep old tables/columns intact but unused if easier, and point all new writes at the new tables — avoids breaking any existing comparison history while the new flow is built.

### 3.4 Default Field Catalogue & Length Constraints (seed data for `field_definitions`)

This is the concrete field list + default length range to seed into `field_definitions` (and used as the **default Length override** for each field's `field_configs` row, since a fixed target/tolerance pair works better here than a single Global Default length for all fields — see note below).

| `field_key` | Label | Length Constraint | Unit |
|---|---|---|---|
| `meta_title` | Meta Title | 60–75 chars | characters |
| `meta_description` | Meta Description | 140–160 chars | characters |
| `snippet` | Snippet / Summary | 180–260 chars | characters |
| `intro_paragraph` | Intro Paragraph | 350–550 chars | characters |
| `long_description` | Long Description | 1,600–2,400 chars | characters |
| `option_name` | Option Name (Variant) | ≤ 80 chars | characters |
| `option_description` | Option Description | ≤ 255 chars | characters |
| `highlight_bullet` | Highlight bullet | ≤ 85 chars | characters |
| `faq_answer` | FAQ Answer | 220–350 chars | characters |
| `faq_city` | FAQ (city-specific, up to 9 per run) | — (inherits `faq_answer` constraint per item) | characters |

**Important implication for Section 3.2 / 4.4 (Length check):**
- All of these fields use a **min–max range**, not a single target ± tolerance %. The Verification Engine's Length check (Section 4.4, check #1) must therefore support **two length modes** per field:
  - `range` mode: `{min, max}` in characters (used by every field above).
  - `target_tolerance` mode: `{target, tolerance_pct}` (the original mode, kept for any future field that prefers it, e.g. a long-form article field measured in words).
- Store this as `length_mode` + `length_min`/`length_max` (or `length_target`/`length_tolerance_pct`) columns on `field_configs`, not a single numeric column.
- `faq_city` is a **repeating field** (up to 9 instances per Test Run, one per FAQ question) — model this as one `field_definitions` row with `is_repeating = true, max_instances = 9`, so the batch engine fans it out into up to 9 separate `field_jobs` rows (`faq_city[1]` … `faq_city[9]`) at execution time, each independently generated, verified, and regenerable, but all sharing the same inherited length/tone/etc. config unless a specific instance is overridden.
- All 10 rows above should be seeded with `length_mode = range`, character unit, and the min/max shown, as their **default** — the user can still override per Test Run via the Field List Block (Section 7.2, item 3).

- **Batches** — add `plan_json` column (see Section 4.7) storing the compiled batch-level Content Plan, so it's persisted alongside the batch and visible for debugging/audit, not just used transiently in memory.

---

## 4. Backend Logic Changes

### 4.1 Prompt Compilation (`app/main.py` / new `app/prompt_compiler.py`)
- Replace the single `compile_prompt(input_json, config)` with `compile_field_prompt(input_json, field_key, resolved_field_config)`.
- `resolved_field_config` = Global Default Config merged with any Field Config overrides for that `field_key` (override wins).
- Output: `{system_prompt: str, user_prompt: str}` **for that field only** — the user prompt should ask the LLM to generate **only that field's content**, referencing the shared source JSON as context, still enforcing `response_format: json_object` scoped to that field's expected shape (e.g. `{ "attractions": [...] }`), not the entire page schema.
- A new endpoint must expose this without executing anything:
  - `POST /api/content/compile-batch` → body: `{ test_run_id, field_keys: [...] }` → returns array of `{ field_key, system_prompt, user_prompt }` for the confirmation screen.

### 4.2 Language Mandate & JSON Enforcement
- Unchanged in principle, but now applied per field: the Target Language instruction is injected into every field's system prompt, and the JSON schema enforced is just that field's sub-schema.

### 4.3 Batch Execution Engine (NEW: `app/batch_engine.py`)
- `POST /api/content/generate-batch` → body: `{ test_run_id, model_name, fields: [ { field_key, system_prompt, user_prompt } ] }` (the *edited* prompts from the UI, not re-compiled server-side — what the user saw is exactly what gets sent).
- Creates one `batches` row + one `field_jobs` row per field, all `status = queued`.
- **Before per-field execution begins, runs the Semantic Consistency Planner (Section 4.7) once for the whole batch**, storing the result as `batches.plan_json` and slicing it into each field's already-compiled prompt (append the `narrative_core` + that field's `fact_allocation` slice as a "Shared Context" block). Note: since `compile-batch` (Section 4.1) already returned prompts to the UI for user review/editing *before* the plan exists, the plan's Shared Context block is appended server-side at execution time, after the user's edits are captured — the user reviews their own per-field instructions in the popup, and the plan-derived consistency layer is added transparently on top at run time. (If it's preferred that the user also see the plan before confirming, see the open decision in Section 11.)
- Executes field jobs **concurrently** (async, e.g. `asyncio.gather` with a concurrency cap, default 3–5 parallel calls, configurable in `app_settings`) — do not force serial execution, since fields are independent generations.
- For each field job:
  1. Call OpenRouter with that field's compiled prompt → mark `running` → `passed`/`failed` at the LLM-call level (network/API failure vs. content failure are different states).
  2. On successful LLM response, run that field through the **Verification Engine scoped to just that field** (Section 4.4).
  3. If verification fails → run **Targeted Regeneration for that field only** (Section 4.5), same LLM, same field, using only that field's previous output + that field's failed checks.
  4. Update `field_jobs.status` to final state.
- The endpoint should support **streaming/polling progress** so the UI can show live per-field status (Section 8.3). Prefer Server-Sent Events or a simple polling `GET /api/content/batch/{batch_id}/status` returning per-field job states — pick whichever fits the existing FastAPI setup; SSE preferred since generation is async and can take a while per field.
- Batch-level `status` = `completed` only when all fields are in a terminal pass state; `partial_failure` if some fields failed even after regeneration; `failed` only if the whole batch couldn't start (e.g. bad model name).

### 4.4 Verification Engine — Now Per Field
- Same 5 checks as before (Length, Banned Keywords, Tone, Audience, Style Guide), but:
  - Each check runs against **only that field's generated text**, using **that field's resolved config** (its own length target/tolerance, its own tone/audience/keywords/style if overridden).
  - `verification_results` rows are written with `field_job_id`.

### 4.5 Targeted Regeneration — Now Per Field
- Correction Prompt now contains: *this field's previous output* + *this field's list of failed checks* only.
- Still calls the same LLM/model used for the original field generation.
- Re-verifies just that field. Loop count (e.g. max 1–2 regeneration attempts per field, configurable) should be enforced per field independently — one field regenerating does not block or restart other fields in the batch.

### 4.6 Fallback Mechanism
- Unchanged in spirit (mock content on missing key / HTTP 402), but the mock must now be generated **per field** so the batch UI still shows N field cards with mock content when running in fallback/demo mode.

### 4.7 Semantic Consistency Planner (NEW — fixes "fields feel disconnected")

**Problem this solves:** Since each field is generated independently (and often in parallel), the resulting page can read like disconnected stitched-together pieces instead of one coherent city page — repeated facts, inconsistent tone, inconsistent naming of the same attraction, etc.

**Fix: a Planning Phase runs once per batch, before any field generation starts.**

1. **Planner Call:** One extra LLM call, made once per batch (not per field), given: the raw Source Data JSON, the list of included fields for this batch, and each field's resolved config (tone/audience/style if overridden). It does **not** generate any field content — it only produces a structured **Content Plan**.

2. **Content Plan structure** (JSON, stored as `batches.plan_json`):
   - `narrative_core` (small, fixed-size, ~150–250 chars): the city's overall angle/hook + a tone anchor (1–2 example phrasing lines) + naming conventions (how to refer to the city, key attractions, any nickname/spelling to standardize on).
   - `fact_allocation`: a map of `field_key → [fact ids / short fact strings from the source data assigned to that field]`. This is how repetition is avoided — a given fact (e.g. "built in 1850", "average visit 2 hours") is assigned to exactly one field, not left for every field to independently decide to mention it.

3. **CRITICAL — token budget handling (do not inject the whole plan into every field prompt):**
   - Every field's compiled prompt (Section 4.1) includes the small, fixed-size `narrative_core` (cheap — same ~150–250 chars regardless of batch size).
   - Every field's compiled prompt includes **only its own slice** of `fact_allocation` (i.e. `fact_allocation[this_field_key]`), never the full map for all fields.
   - This means per-field prompt size stays roughly constant as more fields are added to a batch — the plan does not compound into a linearly-growing shared blob that gets pasted into every single field's prompt.
   - The full `plan_json` is still persisted at the batch level for auditing/debugging (Section 3.3 addition), even though only slices of it are ever sent to any single field-generation call.

4. **Compilation change:** `compile_field_prompt(input_json, field_key, resolved_field_config, plan_slice)` — `plan_slice = { narrative_core, allocated_facts: fact_allocation[field_key] }` — gets folded into the field's System Prompt as a short "Shared Context" block, alongside the existing per-field config instructions.

5. **Planner failure handling:** If the Planner call fails or times out, fall back to the old behavior (no shared plan, fields generate independently) rather than blocking the whole batch — log a warning on the batch record so it's visible this batch ran "unplanned."

6. **Optional (flag as a follow-up, not required for v1 of this fix) — Dependency-ordered queue:** Instead of all fields generating fully in parallel, generate a small "anchor" subset first (e.g. Title + Intro Paragraph), then pass their actual generated output (not just the plan) forward as extra context into the remaining fields' prompts. This gives even tighter coherence than the plan alone, at the cost of some added latency since those fields can no longer run at the very start of the batch. Recommend implementing the Planner (steps 1–5) first and only adding this if coherence still isn't strong enough after testing.

7. **Optional (flag as a follow-up) — Final coherence check pass:** After all fields reach a terminal passed state, one more LLM call reviews all field outputs together for repeated facts, tone drift, or naming inconsistencies, and flags specific fields for a coherence-focused regeneration (separate from the existing per-field verification checks in Section 4.4, which don't look across fields at all).

---

## 5. API Contract Summary (new/changed endpoints)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/fields/schema` | GET | Returns the configurable field list for a schema type (from `field_definitions`) so the UI can render field-level config blocks dynamically. |
| `/api/content/compile-batch` | POST | Compiles (but does not execute) one prompt per field, for the confirmation/preview screen. Returns editable prompt text per field. |
| `/api/content/generate-batch` | POST | Executes the batch using the (possibly user-edited) prompts returned/edited from `compile-batch`. Kicks off async per-field jobs. |
| `/api/content/batch/{batch_id}/status` | GET (or SSE) | Live per-field job status: queued/running/passed/failed/regenerating/etc., plus output + verification results as they land. |
| `/api/content/batch/{batch_id}/field/{field_key}/rerun` | POST | Re-run a single field job without touching the rest of the batch (for the "fix just this one" case, Section 8.4). |

Removed/deprecated: the old single-shot `POST /api/content/generate` that took one global config and returned one combined JSON — superseded by the batch flow above. Keep it only if backward compatibility with old comparison data is required; otherwise remove.

---

## 6. Frontend State Management Changes

- Introduce a `fieldConfigs` state map: `{ [field_key]: { length: {mode: 'inherit'|'override', value}, tolerance: {...}, tone: {...}, audience: {...}, bannedKeywords: {...}, styleGuide: {...} } }`.
- Introduce a `compiledPrompts` state map: `{ [field_key]: { systemPrompt, userPrompt, edited: boolean } }`, populated by calling `compile-batch`, and mutated in place when the user edits a field's prompt text in the popup.
- Introduce a `batchStatus` state: `{ batchId, fields: { [field_key]: { status, output, verification, cost, tokens, latency } } }`, updated by polling/SSE after "Run Batch" is confirmed.
- The old single `generationResult` / `verificationLog` state (one blob for the whole page) is replaced by the per-field maps above.

---

## 7. Updated Frontend UI/UX Structure

### 7.1 Left Column — Input & Context Layer (updated)
1. **Location & Language Block** — unchanged.
2. **Source Data Block** — unchanged **except**: remove any Length/Char-Count input that previously lived here. This block is now pure content (facts JSON), nothing about generation control.

### 7.2 Right Column — Control Layer (updated)
3. **Field List Block (NEW)** — one collapsible row per field (Title, Introduction, Attractions, …, driven by `/api/fields/schema`). Each row has:
   - A toggle: include this field in this batch run (default: all on).
   - Per-param controls (Length + unit, Tolerance %, Tone, Audience, Banned Keywords, Style Guide), each with an **"Inherit from Default" / "Override"** switch.
4. **Global Default Config Block** — the old "Prompt Parameters Block" becomes the *default* values that unset fields fall back to (Tone, Audience, Banned Keywords, Style Guide, default Length/Tolerance).
5. **Model Selection** — unchanged, one model for the whole batch (all fields use the same model per run, consistent with "SAME LLM" fixing itself).
6. **Execution Button** — renamed **"Review Batch Prompts"** (this is what used to be "Generate Content"; it does NOT call the API, it opens the new multi-field popup below).

### 7.3 New: Multi-Field Prompt Confirmation Popup (replaces the old single-prompt popup)
- **Title:** "Review Batch — N Fields"
- **Body:** A **list/accordion of N cards, one per included field** (Title, Introduction, Attractions, …). Each card shows:
  - Field name + its resolved config summary (e.g. "Length: 120 words ±30%, Tone: Friendly (override), Keywords: inherited").
  - A read-only-by-default, **editable** syntax-highlighted code block with that field's exact compiled System + User prompt.
  - An "Edit" affordance so the user can tweak that specific field's prompt text before running (edits are stored back into `compiledPrompts[field_key]` with `edited: true`).
- **Warning banner:** "You are about to execute N requests using [Model Name]." (N = number of included fields, since each field is its own LLM call.)
- **Popup Actions:**
  - `Cancel / Edit Settings` — closes modal, back to field config screen.
  - **`Run Batch`** — single button, always batch semantics even for N=1 — calls `generate-batch` with the (possibly edited) prompts.

### 7.4 Bottom Full-Width Section — Output Layer (updated)
- Replace the single Results View with a **per-field results grid/list**: one card per field showing:
  - Live status chip (Queued → Running → Passed / Failed → Regenerating → Regenerated-Pass/Fail).
  - The field's generated content.
  - That field's own PASS/FAIL verification badges (Length, Keywords, Tone, Audience, Style).
  - Cost/tokens/latency for that field's job(s).
  - A **"Rerun this field"** button (calls the single-field rerun endpoint) for any field that ended in a failed state, without re-running the whole batch.
- Keep an overall batch summary strip at the top (e.g. "5/7 fields passed, 2 regenerated, 0 failed") for quick scanning.

---

## 8. Behavioral Rules to Preserve / Clarify

1. **Batch is always the execution unit**, even for a single field — there is no separate "single run" code path; a lone field is just a batch of size 1. This avoids maintaining two parallel execution engines.
2. **Length is never part of the Source Data input** — it only exists inside Field Config / Global Default Config.
3. **Every field's prompt must be visible and editable before execution** — no field can be executed "blind."
4. **Editing a field's prompt in the popup only affects that field** — it does not re-trigger recompilation of other fields' prompts.
5. **Regeneration remains same-model, same-field, targeted-fix-only** — unchanged principle from the old spec, just scoped down to one field instead of the whole document.
6. **Single-field rerun** (Section 5, last row) is the one allowed exception to "everything is a batch" — it exists so the user isn't forced to re-spend API credits on 6 already-passing fields just to fix 1 failing one. It still creates its own `field_jobs` row and re-verifies, just doesn't touch sibling fields.

---

## 9. Implementation Plan (order of work for the coding agent)

1. **DB migrations:** add `field_definitions`, `field_configs`, `batches`, `field_jobs`; add `field_job_id` FKs to `verification_results` and `regenerations`. Seed `field_definitions` (and default `field_configs` length ranges) with the **10-field catalogue in Section 3.4** (Meta Title, Meta Description, Snippet, Intro Paragraph, Long Description, Option Name, Option Description, Highlight Bullet, FAQ Answer, FAQ City ×9-repeating) — replacing the earlier placeholder list of 7 generic page fields.
2. **Backend: prompt compiler refactor** — extract `compile_field_prompt`, add config resolution (inherit vs override) helper `resolve_field_config(global_default, field_override)`.
3. **Backend: `/api/fields/schema` and `/api/content/compile-batch`** endpoints.
4. **Backend: `batch_engine.py`** — implement the Semantic Consistency Planner (Section 4.7) as the first step of batch execution, storing `plan_json`; then async per-field execution (with the planner's narrative_core + per-field fact_allocation slice appended to each field's prompt at run time), verification, targeted regeneration, all scoped per field; wire up `/api/content/generate-batch` and the status/SSE endpoint.
5. **Backend: single-field rerun endpoint.**
6. **Frontend: remove Length/Tolerance from Source Data Block.**
7. **Frontend: Field List Block** with per-field inherit/override controls, backed by `/api/fields/schema`.
8. **Frontend: rework "Generate Content" button → "Review Batch Prompts" → calls `compile-batch`.**
9. **Frontend: Multi-Field Prompt Confirmation Popup** (accordion of editable prompt cards) with the single `Run Batch` action calling `generate-batch`.
10. **Frontend: per-field Results grid** with live status via polling/SSE, plus per-field "Rerun this field" button.
11. **Regression pass:** confirm old single-run history/comparison views (if kept) still read correctly against legacy `generations` rows, or are cleanly migrated/deprecated per the decision in Section 5.

---

## 10. Fix Request: History is Empty / Multi-Model Comparison is Missing

> **Status:** Regression. This feature (viewing past runs + selecting 2 or more of them to compare side-by-side) existed before and worked. It is currently not visible/functional after the batch refactor. This section is a bug-fix + feature-restore spec, not new-from-scratch design.

### 11.1 Instructions for the coding agent (read first)

- **You have code access. Investigate before changing anything.** Do not guess why history is empty — find the actual cause by reading the current codebase (frontend history/comparison components, the API routes they call, and the DB read queries behind those routes).
- Specifically check, and report back what you find for each, before writing a fix:
  1. Is there still an API endpoint that lists past runs (e.g. an old `GET /api/runs` or `GET /api/generations`)? Does it still exist, and does it query the **old** tables (`test_runs`, `generations`) or has something changed under it?
  2. Since Section 3–4 of this doc introduced `batches` / `field_jobs` replacing flat `generations`, does the history-listing endpoint/query still point at the **old** table/columns that per-field generation no longer writes to? (This is the most likely root cause — the write path moved to `field_jobs` but the read path for history may still be reading `generations`.)
  3. Is the frontend History page/component still mounted and routed to, or was it dropped/hidden during the batch UI rework in Section 7?
  4. Are rows actually being written at all right now (check `test_runs`, `batches`, `field_jobs` directly in Supabase / in-memory store) — i.e. is this a **read/query bug** or a **write bug**?
- **Do not invent a data model for this.** Use the actual `test_runs` / `batches` / `field_jobs` / `verification_results` schema already defined in Sections 3.3–3.4 of this doc. If something doesn't line up (e.g. a field this feature needs doesn't exist yet), flag it explicitly rather than fabricating a workaround.
- If you are not sure whether a given file/route is the one responsible, say so and show what you checked, rather than rewriting things speculatively.

### 11.2 Required Behavior (restore + extend for batch model)

1. **History List:** A page/panel listing past runs for a Test Run (or globally, filterable by country/city/language) — each entry shows at minimum: date/time, model used, country/city/language, and overall batch status (e.g. "6/7 fields passed").
2. **Selection for Comparison:** The user can select **2 or more** past runs (not capped at 2 — could be 3, 4, or more) via checkboxes in the History List.
3. **Compare View:** Selecting runs and clicking "Compare" opens a view showing the selected runs **side-by-side, per field** — e.g. a row per field (Meta Title, Meta Description, …) and a column per selected run/model, each cell showing that run's generated content for that field, formatted (not raw JSON), plus its PASS/FAIL verification badges.
4. Since generation is now per-field (Section 4), comparison must join across `field_jobs` for each selected `batch_id`, not across a single flat `generations` row per run as before — this is the main structural change needed to restore the old feature under the new schema.
5. This must work for **any number of selected runs**, not just exactly 2 — the old UI's comparison should generalize to an N-column layout (with horizontal scroll if needed for many runs).

### 11.3 Suggested Diagnosis-to-Fix Order

1. Confirm whether writes are happening (query `batches`/`field_jobs` directly for a run you just generated).
2. If writes are fine → the bug is in the History List's read query or the route/component wiring — trace it and fix the query/route to read from `batches` + `field_jobs` instead of any stale reference to `generations`.
3. If writes are missing → trace the batch engine (Section 4.3) to confirm every field job actually persists on completion, not just on final batch completion (a partially-failed batch should still show whatever fields did complete).
4. Rebuild/reconnect the Compare View last, once history is confirmed populated and correct, using the per-field join described in 11.2.4.

---

## 11. Open Decisions for the User/Team (flag, don't assume)

- **Should the user see the Planner's Content Plan before confirming the batch?** Currently spec'd as: plan runs at execution time, after the user has already reviewed/edited per-field prompts (Section 5, `generate-batch` bullet). Alternative: run the Planner earlier (during `compile-batch`) so the user can see and edit the shared `narrative_core`/`fact_allocation` too, at the cost of one extra round-trip before the popup can render. Confirm which UX is preferred.
- **Dependency-ordered queue and final coherence check (Section 4.7, items 6–7)** — confirm whether these follow-ups are needed for v1, or only if the Planner alone doesn't produce strong enough coherence in testing.

- **History/Comparison root cause** — once the coding agent reports back per Section 10.1, confirm which of the four causes it actually was, so this doesn't regress again in a future refactor.
- **Concurrency cap** for parallel field generation calls (suggested default: 3–5) — confirm against OpenRouter rate limits for the chosen model.
- **Max regeneration attempts per field** (suggested default: 1–2) — confirm.
- **Whether to keep the old single-shot `/api/content/generate` endpoint** for backward compatibility with existing comparison data, or deprecate it outright.
- **Length unit default** — words vs. characters — should this be selectable per field or fixed project-wide?