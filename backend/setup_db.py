import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

SQL_SCHEMA = """
-- Test Runs table
CREATE TABLE IF NOT EXISTS test_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    language TEXT NOT NULL,
    input_json JSONB NOT NULL,
    prompt_version TEXT DEFAULT 'V1',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Prompt Configs table
CREATE TABLE IF NOT EXISTS prompt_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_run_id UUID REFERENCES test_runs(id) ON DELETE CASCADE,
    tone TEXT,
    audience TEXT,
    content_length INT,
    banned_keywords JSONB,
    style_guide TEXT,
    additional_instructions TEXT,
    final_prompt TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Generations table
CREATE TABLE IF NOT EXISTS generations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_run_id UUID REFERENCES test_runs(id) ON DELETE CASCADE,
    model_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    attempt_number INT DEFAULT 1,
    output_json JSONB NOT NULL,
    output_text TEXT,
    status TEXT NOT NULL,
    input_tokens INT DEFAULT 0,
    output_tokens INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    latency_ms INTEGER DEFAULT 0,
    cost FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Verification Results table
CREATE TABLE IF NOT EXISTS verification_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID REFERENCES generations(id) ON DELETE CASCADE,
    verification_attempt INTEGER DEFAULT 1,
    parameter TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    affected_fields JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Regenerations table
CREATE TABLE IF NOT EXISTS regenerations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    generation_id UUID REFERENCES generations(id) ON DELETE CASCADE,
    parameter TEXT NOT NULL,
    previous_output JSONB,
    new_output JSONB,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- App Settings table
CREATE TABLE IF NOT EXISTS app_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verifier_model_id TEXT NOT NULL DEFAULT 'openai/gpt-4o',
    verify_tone BOOLEAN DEFAULT TRUE,
    verify_audience BOOLEAN DEFAULT TRUE,
    verify_content_length BOOLEAN DEFAULT TRUE,
    verify_banned_keywords BOOLEAN DEFAULT TRUE,
    verify_style_guide BOOLEAN DEFAULT TRUE,
    verify_additional_instructions BOOLEAN DEFAULT TRUE,
    content_length_tolerance_pct INTEGER DEFAULT 10,
    max_verification_retries INTEGER DEFAULT 2,
    regeneration_strategy TEXT DEFAULT 'update_failed_sections',
    field_matching_strictness TEXT DEFAULT 'medium',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default app settings if empty
INSERT INTO app_settings (verifier_model_id)
SELECT 'openai/gpt-4o'
WHERE NOT EXISTS (SELECT 1 FROM app_settings);

-- ---------------------------------------------------------------------
-- v2 per-field batch schema (idempotent migrations for existing tables)
-- ---------------------------------------------------------------------

-- 1. prompt_configs: ensure content_length exists (it is an intended field)
ALTER TABLE prompt_configs ADD COLUMN IF NOT EXISTS content_length INT;

-- 2. field_definitions
CREATE TABLE IF NOT EXISTS field_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    field_key TEXT NOT NULL UNIQUE,
    label TEXT,
    default_order INT,
    schema_type TEXT DEFAULT 'city_page',
    length_mode TEXT DEFAULT 'range',
    length_min INT,
    length_max INT,
    unit TEXT DEFAULT 'characters',
    is_repeating BOOLEAN DEFAULT FALSE,
    max_instances INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. field_configs
CREATE TABLE IF NOT EXISTS field_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_run_id UUID REFERENCES test_runs(id) ON DELETE CASCADE,
    field_key TEXT,
    length_mode TEXT DEFAULT 'range',
    length_min INT,
    length_max INT,
    length_target INT,
    length_tolerance_pct INT,
    unit TEXT DEFAULT 'characters',
    tone TEXT,
    tone_override BOOLEAN DEFAULT FALSE,
    audience TEXT,
    audience_override BOOLEAN DEFAULT FALSE,
    banned_keywords JSONB,
    banned_keywords_override BOOLEAN DEFAULT FALSE,
    style_guide TEXT,
    style_guide_override BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. batches
CREATE TABLE IF NOT EXISTS batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_run_id UUID REFERENCES test_runs(id) ON DELETE CASCADE,
    model_name TEXT,
    status TEXT DEFAULT 'pending',
    plan_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE batches ADD COLUMN IF NOT EXISTS plan_json JSONB;

-- 5. field_jobs (created with updated_at)
CREATE TABLE IF NOT EXISTS field_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID REFERENCES batches(id) ON DELETE CASCADE,
    field_key TEXT,
    compiled_system_prompt TEXT,
    compiled_user_prompt TEXT,
    status TEXT DEFAULT 'queued',
    output_json_fragment JSONB,
    cost FLOAT DEFAULT 0.0,
    tokens INT DEFAULT 0,
    latency_ms INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. field_jobs: ensure updated_at exists on an existing table
ALTER TABLE field_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- 7. verification_results: add per-field FK
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS field_job_id UUID REFERENCES field_jobs(id) ON DELETE CASCADE;

-- 8. regenerations: add per-field FK
ALTER TABLE regenerations ADD COLUMN IF NOT EXISTS field_job_id UUID REFERENCES field_jobs(id) ON DELETE CASCADE;
"""

def setup():
    print("Checking Supabase connection...")
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        print("No Supabase URL provided. Backend will use robust fallback storage.")
        return

    if SUPABASE_SERVICE_ROLE_KEY.startswith("sb_"):
        print(f"Warning: Loaded key '{SUPABASE_SERVICE_ROLE_KEY[:10]}...' starts with 'sb_'.")
        print("Python supabase SDK requires the JWT service_role key starting with 'eyJ...'.")
        print("Please update backend/.env with your eyJ... key and save the file in your editor.")
        return

    try:
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        # Execute each statement individually so one failure doesn't abort the rest.
        statements = [s.strip() for s in SQL_SCHEMA.split(";") if s.strip()]
        for stmt in statements:
            try:
                client.rpc("exec_sql", {"query": stmt}).execute()
            except Exception:
                # Fall back to raw postgrest query if exec_sql RPC isn't available.
                try:
                    client.postgrest.rpc("exec_sql", {"query": stmt}).execute()
                except Exception as e:
                    print(f"Statement skipped (may already exist or RPC unavailable): {e}")
        print("Database setup complete.")
    except Exception as e:
        print(f"Supabase connection warning: {e}")


if __name__ == "__main__":
    setup()
