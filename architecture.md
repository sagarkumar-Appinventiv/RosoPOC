# 🏗️ Architecture — RosoTravel AI Model Comparison POC

> A full-stack tool to generate, verify, compare, and audit AI-generated travel content across multiple LLMs via OpenRouter.

---

## 📐 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BROWSER / USER                             │
│                    React + TypeScript (Vite)                        │
│                         localhost:5173                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  HTTP REST (fetch API)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FASTAPI BACKEND                               │
│                         localhost:8000                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  main.py     │  │ openrouter.py│  │    verification.py       │  │
│  │  (API Routes)│  │ (LLM Calls)  │  │  (Verify + Regenerate)   │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
│         │                 │                        │                │
│  ┌──────▼─────────────────▼────────────────────────▼─────────────┐  │
│  │                      database.py                              │  │
│  │         (Dual-Layer: Supabase + In-Memory Fallback)           │  │
│  └──────┬─────────────────────────────────────────────────────── ┘  │
└─────────┼───────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────┐       ┌──────────────────────────────┐
│      SUPABASE (DB)      │       │    OPENROUTER API            │
│  PostgreSQL (Cloud)     │       │  https://openrouter.ai/api/v1│
│  - test_runs            │       │  Routes to: GPT-4o, Claude,  │
│  - prompt_configs       │       │  Gemini, Llama, DeepSeek,    │
│  - generations          │       │  Mistral, Qwen, Cohere...    │
│  - verification_results │       └──────────────────────────────┘
│  - regenerations        │
│  - app_settings         │
└─────────────────────────┘
```

---

## 📁 Project Directory Structure

```
Model-Camparison-Roso-/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py          # Env vars (API keys, URLs)
│   │   ├── main.py            # FastAPI app + all API routes
│   │   ├── openrouter.py      # LLM call logic + model list
│   │   ├── database.py        # DB layer (Supabase + in-memory)
│   │   └── verification.py    # Verify + regen logic
│   ├── data/                  # (Scratch/static data if any)
│   ├── setup_db.py            # One-time DB schema setup script
│   ├── test_regen.py          # Manual test for regeneration
│   ├── requirements.txt       # Python dependencies
│   └── .env                   # Secret keys (gitignored)
│
└── frontend/
    ├── src/
    │   ├── App.tsx             # Root component + tab router
    │   ├── main.tsx            # React entry point
    │   ├── index.css           # Global design tokens & styles
    │   ├── pages/
    │   │   ├── SecretKeyPage.tsx        # Auth gate
    │   │   ├── DashboardPage.tsx        # Stats overview
    │   │   ├── ContentGenerationPage.tsx # Main generate UI
    │   │   ├── HistoryPage.tsx          # All past runs
    │   │   ├── ModelComparisonPage.tsx  # Side-by-side compare
    │   │   └── SettingsPage.tsx         # Verifier settings
    │   ├── components/
    │   │   ├── Sidebar.tsx              # Left nav
    │   │   ├── Header.tsx               # Top header bar
    │   │   ├── RunDetailDrawer.tsx      # Slide-in run details
    │   │   └── VerificationLogsModal.tsx # Modal for verify results
    │   ├── services/
    │   │   └── api.ts          # All fetch() calls to backend
    │   └── types/              # TypeScript type definitions
    ├── package.json
    └── vite.config.ts
```

---

## 🔄 Core User Flow (End-to-End)

```
1. USER opens app → SecretKeyPage (auth gate)
        │
        ▼ POST /api/auth/verify (secret_key)
2. Backend returns session token → stored in localStorage
        │
        ▼
3. USER goes to "Content Generation" page
   - Selects: Country, City, Language
   - Inputs: JSON data (attractions, activities, etc.)
   - Configures: Tone, Audience, Word Count, Banned Keywords, Style Guide
   - Picks: an LLM model from dropdown (fetched from OpenRouter)
        │
        ▼ POST /api/content/generate
4. Backend:
   a) Finds or creates a Test Run (country+city+language = group key)
   b) Builds the system prompt + user prompt
   c) Calls OpenRouter → gets AI-generated travel JSON
   d) Saves generation to DB (status = "Unverified")
   e) Returns output_json + metrics (tokens, latency, cost)
        │
        ▼
5. USER clicks "Verify"
        │
        ▼ POST /api/content/verify
6. Backend runs 5 parameter checks:
   [1] Content Length       → Code-based word count check
   [2] Banned Keywords      → Regex-based keyword scan
   [3] Tone                 → LLM-based evaluation (skipped if blank)
   [4] Audience Variant     → LLM-based evaluation (skipped if blank)
   [5] Style Guide          → LLM-based evaluation (skipped if blank)
   → Status updated to "Verified" or "Failed"
        │
        ▼ (if FAIL)
7. USER clicks "Regenerate"
        │
        ▼ POST /api/content/regenerate
8. Backend:
   a) Identifies failed parameters
   b) Builds targeted fix prompt for those specific failures
   c) Re-calls the SAME LLM model with targeted corrections
   d) Re-runs full verification on new output
   e) Updates generation record: new output_json, new attempt number, new status
        │
        ▼
9. USER goes to "Model Comparison" page
   - Picks a Test Run ID
   - Sees all verified/regenerated outputs side by side per model
        │
10. USER can browse "History" — all past runs with status, cost, latency
```

---

## 🧩 Backend Module Breakdown

### `config.py` — Environment Configuration
| Variable | Source | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | `.env` | Authenticates all LLM calls |
| `SUPABASE_URL` | `.env` | Supabase project endpoint |
| `SUPABASE_SERVICE_ROLE_KEY` | `.env` | Supabase admin access |
| `POC_SECRET_KEY` | `.env` (default: `9090`) | App auth gate password |
| `OPENROUTER_BASE_URL` | Hardcoded | `https://openrouter.ai/api/v1` |

---

### `main.py` — FastAPI Routes

| Method | Endpoint | What it does |
|---|---|---|
| `POST` | `/api/auth/verify` | Validates secret key, returns session token |
| `GET` | `/api/models` | Lists all available LLM models from OpenRouter |
| `GET` | `/api/settings` | Fetches verifier config |
| `POST` | `/api/settings` | Updates verifier config |
| `GET` | `/api/dashboard/stats` | Aggregate metrics: runs, cost, latency |
| `POST` | `/api/content/generate` | Main generation endpoint |
| `POST` | `/api/content/verify` | Runs 5-parameter verification |
| `POST` | `/api/content/regenerate` | Targeted fix-and-re-verify |
| `GET` | `/api/history` | All past generation runs |
| `GET` | `/api/history/{run_id}` | Full detail of a single run |
| `GET` | `/api/comparison/{test_run_id}` | All verified runs for a test group |
| `GET` | `/api/test-runs/{test_run_id}/models` | Which models were used for a test run |

**Session Auth:** A simple in-memory set `_active_session_tokens` holds valid session tokens for the lifetime of the process. Token is verified via `Authorization: Bearer <token>` header.

---

### `openrouter.py` — LLM Integration

**`fetch_openrouter_models()`**
- Calls `GET https://openrouter.ai/api/v1/models`
- Returns normalized list with `id`, `name`, `context_length`, `pricing`
- Falls back to a **hardcoded `FALLBACK_MODELS` list** (18 models) if API key is missing or call fails

**`generate_completion(model_id, prompt, system_prompt)`**
- Calls `POST https://openrouter.ai/api/v1/chat/completions`
- Uses `response_format: { type: "json_object" }` to enforce JSON output
- Tracks: input tokens, output tokens, latency (ms), cost
- **Fallback chain:**
  1. If `OPENROUTER_API_KEY` is empty → uses `_create_mock_content()` (demo mode)
  2. If API returns 402 (credit limit) → falls back to mock
  3. On any exception → falls back to mock
- Returns: `(success, output_json, in_tokens, out_tokens, total_tokens, latency_ms, cost)`

**`validate_and_parse_json(text)`**
- Strips markdown code fences (` ```json `)
- Parses JSON and validates required keys: `title`, `introduction`, `attractions`, `activities`
- Backfills missing optional keys with Paris-based defaults

**`calculate_completion_cost(model_id, input_tokens, output_tokens, models_list)`**
- Per-token cost = `(input_tokens × prompt_price) + (output_tokens × completion_price)`

---

### `database.py` — Dual-Layer Persistence

**Design Pattern:** Write-through with in-memory fallback.

```
Every write operation:
  1. Appends to _in_memory_db (always)
  2. Inserts to Supabase (if client is initialized)

Every read operation:
  1. Tries Supabase first
  2. Falls back to _in_memory_db if Supabase fails or is not configured
```

**In-Memory Store Structure:**
```python
_in_memory_db = {
    "test_runs": [],          # Location + language groupings
    "prompt_configs": [],     # Prompt params per test run
    "generations": [],        # Model outputs + metrics
    "verification_results": [], # Per-parameter check results
    "regenerations": []       # Before/after regeneration snapshots
}
```

**Key Functions:**
| Function | Purpose |
|---|---|
| `find_matching_test_run()` | Prevents duplicate test runs for same city+country+language |
| `create_test_run()` | Creates test run + prompt config records |
| `save_generation()` | Saves an LLM output with metrics |
| `update_generation_record()` | Updates status, attempt count, or output |
| `save_verification_results()` | Saves per-parameter check results |
| `save_regeneration()` | Saves before/after snapshot of a regen |
| `get_history_runs()` | Merges Supabase + in-memory (deduped by ID) |
| `get_run_details()` | Full detail for one run (generation + test run + verification + regen) |
| `get_comparison_runs()` | All verified/regenerated runs for a test group |

---

### `verification.py` — 5-Parameter Quality Check

**Verification runs 2 code checks + up to 3 LLM checks:**

```
Parameter             Method          Trigger Condition
─────────────────────────────────────────────────────────
1. Content Length     Code (regex)    Always (word count vs target ± tolerance%)
2. Banned Keywords    Code (regex)    Always (whole-word match in text values only)
3. Tone               LLM call        Only if tone field was filled by user
4. Audience Variant   LLM call        Only if audience field was filled by user
5. Style Guide        LLM call        Only if style guide was filled by user
```

**LLM Parameters are auto-PASS'd if the user left them blank** — this avoids penalizing default outputs for unconfigured criteria.

**`targeted_regeneration()`:**
- Builds a focused correction prompt listing **only the specific failing parameters**
- Calls the **same model** that originally generated the content
- Re-runs full 5-parameter verification on the new output
- Returns updated JSON + token/cost metrics

---

## 🗄️ Database Schema (Supabase / PostgreSQL)

```
test_runs
├── id (UUID PK)
├── country, city, language, input_json
├── prompt_version (default: 'V1')
└── created_at

prompt_configs
├── id (UUID PK)
├── test_run_id → test_runs(id)
├── tone, audience, content_length
├── banned_keywords (JSONB array)
├── style_guide, final_prompt
└── created_at

generations
├── id (UUID PK)
├── test_run_id → test_runs(id)
├── model_id, model_name
├── attempt_number (1 = original, 2+ = regenerated)
├── output_json (JSONB)
├── status (Unverified | Verified | Failed | Regenerated)
├── input_tokens, output_tokens, total_tokens
├── latency_ms, cost
└── created_at

verification_results
├── id (UUID PK)
├── generation_id → generations(id)
├── verification_attempt
├── parameter (Content Length | Banned Keywords | Tone | ...)
├── status (PASS | FAIL)
├── reason, affected_fields (JSONB)
└── created_at

regenerations
├── id (UUID PK)
├── generation_id → generations(id)
├── parameter (which param triggered regen)
├── previous_output (JSONB)
├── new_output (JSONB)
├── reason
└── created_at

app_settings
├── id (UUID PK)
├── verifier_model_id (default: openai/gpt-4o)
├── verify_tone, verify_audience, verify_content_length (BOOL)
├── verify_banned_keywords, verify_style_guide (BOOL)
├── content_length_tolerance_pct (default: 10%)
├── max_verification_retries (default: 2)
├── regeneration_strategy
└── field_matching_strictness
```

---

## 🖥️ Frontend Architecture

**Framework:** React 18 + TypeScript + Vite  
**State Management:** Local `useState` per page (no Redux/Zustand)  
**Routing:** Custom tab-based routing via `activeTab` state in `App.tsx`

### Pages

| Page | File | Purpose |
|---|---|---|
| Auth Gate | `SecretKeyPage.tsx` | Prompts for `POC_SECRET_KEY`, stores token in `localStorage` |
| Dashboard | `DashboardPage.tsx` | Total runs, success rate, avg latency, cost, recent runs table |
| Generate | `ContentGenerationPage.tsx` | Full form: location, input JSON, prompt config, model picker, generate → verify → regenerate flow |
| History | `HistoryPage.tsx` | Paginated table of all past runs with status badges |
| Comparison | `ModelComparisonPage.tsx` | Test run picker + side-by-side model output cards with verification results |
| Settings | `SettingsPage.tsx` | Toggle verifier checks, set verifier model, tolerance %, retry count |

### Components

| Component | Purpose |
|---|---|
| `Sidebar.tsx` | Left navigation with tab links |
| `Header.tsx` | Top bar showing current page title |
| `RunDetailDrawer.tsx` | Slide-in panel showing full generation details |
| `VerificationLogsModal.tsx` | Modal showing all 5 parameter check results (PASS/FAIL with reasons) |

### API Service (`services/api.ts`)

All backend communication is centralized here. Auth token is read from `localStorage` and injected as `Authorization: Bearer <token>` on every request.

```
verifyAuth()              → POST /api/auth/verify
fetchModels()             → GET  /api/models
generateContent()         → POST /api/content/generate
verifyContent()           → POST /api/content/verify
regenerateContent()       → POST /api/content/regenerate
fetchDashboardStats()     → GET  /api/dashboard/stats
fetchHistory()            → GET  /api/history
fetchRunDetails()         → GET  /api/history/:id
fetchComparisonRuns()     → GET  /api/comparison/:test_run_id
fetchSettings()           → GET  /api/settings
updateSettings()          → POST /api/settings
fetchTestRunUsedModels()  → GET  /api/test-runs/:id/models
```

---

## 🔑 Authentication Flow

```
User enters POC_SECRET_KEY (default: "9090")
          │
          ▼
POST /api/auth/verify
          │
          ├─ Valid → Backend generates session-<UUID> token
          │          Token added to in-memory set
          │          Token returned to frontend
          │          Frontend stores in localStorage as 'roso_session_token'
          │
          └─ Invalid → 401 Unauthorized
```

> **Note:** The token persists only for the lifetime of the backend process. Restarting the server clears all active tokens (users must re-authenticate).

---

## 🤖 Supported LLM Models (via OpenRouter)

| Provider | Model |
|---|---|
| OpenAI | GPT-4o, GPT-4o Mini, o3-mini |
| Anthropic | Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus |
| Google | Gemini 2.0 Flash, Gemini 1.5 Pro |
| Meta | Llama 3.3 70B Instruct, Llama 3.1 405B Instruct |
| DeepSeek | DeepSeek V3 (Chat), DeepSeek R1 (Reasoning) |
| Qwen | Qwen 2.5 72B Instruct, Qwen 2.5 Coder 32B |
| Mistral AI | Mistral Large 2, Mistral Small 24B |
| Cohere | Command R+ |
| Perplexity | Sonar Reasoning |

> If `OPENROUTER_API_KEY` is absent or credits run out, the backend automatically falls back to **deterministic mock content** specific to each model (so the UI remains functional for demo/dev).

---

## ⚙️ Settings & Configurable Parameters

All settings are persisted in the `app_settings` Supabase table (or returned as defaults from code).

| Setting | Default | Description |
|---|---|---|
| `verifier_model_id` | `openai/gpt-4o` | Which LLM is used for tone/audience/style checks |
| `verify_tone` | `true` | Toggle tone check on/off |
| `verify_audience` | `true` | Toggle audience check on/off |
| `verify_content_length` | `true` | Toggle word count check on/off |
| `verify_banned_keywords` | `true` | Toggle keyword scan on/off |
| `verify_style_guide` | `true` | Toggle style guide check on/off |
| `content_length_tolerance_pct` | `50%` | How far from target word count is still acceptable |
| `max_verification_retries` | `3` | Max regeneration attempts |
| `regeneration_strategy` | `targeted` | Currently: targeted (fix only failed params) |
| `field_matching_strictness` | `moderate` | Strictness of field-level JSON matching |

---

## 🚀 Local Development Setup

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Edit .env with your keys (OPENROUTER_API_KEY, SUPABASE_URL, etc.)
python setup_db.py          # One-time DB schema setup
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev                  # Starts at http://localhost:5173
```

### Required `.env` Variables
```env
OPENROUTER_API_KEY=<your_key>
SUPABASE_URL=<your_supabase_project_url>
SUPABASE_SERVICE_ROLE_KEY=<your_jwt_service_role_key>
POC_SECRET_KEY=9090          # App login password
```

> **No Supabase?** The app works entirely with in-memory storage — data resets on backend restart, but all features are functional.

---

## 📊 Generation Status Lifecycle

```
                    ┌─────────────┐
                    │  Unverified │  ← Immediately after generation
                    └──────┬──────┘
                           │ POST /api/content/verify
              ┌────────────┴────────────┐
              ▼                         ▼
         ┌──────────┐             ┌──────────┐
         │ Verified │             │  Failed  │
         └──────────┘             └────┬─────┘
          (all 5 PASS)                 │ POST /api/content/regenerate
                                  ┌────▼──────────┐
                                  │  Regenerated  │  ← All 5 checks PASS after fix
                                  └───────────────┘
                                       or
                                  ┌──────────┐
                                  │  Failed  │  ← Still failing after regen
                                  └──────────┘
```

---

## 🧠 Key Design Decisions

1. **Test Run Grouping:** Multiple model outputs for the same `city + country + language` combination are grouped under one `test_run_id` — this is the comparison unit.

2. **Dual Storage:** In-memory + Supabase write-through means the app is fully usable without a database configured. Supabase is optional but recommended for persistence across restarts.

3. **Selective LLM Verification:** The verifier only calls an LLM for tone/audience/style if the user actually configured those fields. Blank = auto-PASS. This avoids unnecessary API costs.

4. **Same Model for Regen:** Regeneration uses the exact same model that originally generated the content, ensuring the comparison remains fair (one model's output vs. its own corrected version).

5. **OpenRouter Abstraction:** All LLM vendors are accessed through a single OpenRouter API, giving access to 100+ models without managing separate API keys per provider.

6. **Mock Fallback:** Model-specific mock content is baked in so the tool remains demo-able without any API keys or credits.
