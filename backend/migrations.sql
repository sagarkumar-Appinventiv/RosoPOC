-- RosoTravel POC — required Supabase migrations
-- Run this in Supabase Dashboard → SQL Editor.
-- Idempotent: safe to run multiple times.

-- 0. model_configs: shared Generation/Translation selector allowlist
CREATE TABLE IF NOT EXISTS model_configs (
	model_id TEXT PRIMARY KEY,
	generation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
	translation_enabled BOOLEAN NOT NULL DEFAULT FALSE,
	updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_configs_generation_enabled
	ON model_configs(generation_enabled);
CREATE INDEX IF NOT EXISTS idx_model_configs_translation_enabled
	ON model_configs(translation_enabled);

-- 1. batches: Semantic Consistency Planner result
ALTER TABLE batches ADD COLUMN IF NOT EXISTS plan_json JSONB;
ALTER TABLE batches ADD COLUMN IF NOT EXISTS progress_phase TEXT DEFAULT 'initializing';
ALTER TABLE batches ADD COLUMN IF NOT EXISTS progress_field TEXT;

-- 2. field_jobs: serverless queue retry-loop protection
ALTER TABLE field_jobs ADD COLUMN IF NOT EXISTS attempt_count INT DEFAULT 0;

-- 3. verification_results: per-field scoping (v2)
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS field_job_id UUID REFERENCES field_jobs(id) ON DELETE CASCADE;

-- 4. regenerations: per-field scoping (v2)
ALTER TABLE regenerations ADD COLUMN IF NOT EXISTS field_job_id UUID REFERENCES field_jobs(id) ON DELETE CASCADE;

-- 6. translations: full-document translations of completed English outputs
CREATE TABLE IF NOT EXISTS translations (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	test_run_id UUID REFERENCES test_runs(id) ON DELETE SET NULL,
	source_batch_id UUID REFERENCES batches(id) ON DELETE SET NULL,
	source_generation_id UUID REFERENCES generations(id) ON DELETE SET NULL,
	source_language TEXT NOT NULL DEFAULT 'English',
	target_language TEXT NOT NULL,
	model_id TEXT NOT NULL,
	model_name TEXT NOT NULL,
	additional_prompt TEXT DEFAULT '',
	status TEXT NOT NULL DEFAULT 'pending',
	source_content JSONB NOT NULL,
	output_json JSONB,
	error_message TEXT,
	input_tokens INT DEFAULT 0,
	output_tokens INT DEFAULT 0,
	total_tokens INT DEFAULT 0,
	latency_ms INT DEFAULT 0,
	cost FLOAT DEFAULT 0.0,
	created_at TIMESTAMPTZ DEFAULT NOW(),
	updated_at TIMESTAMPTZ DEFAULT NOW(),
	CONSTRAINT translations_one_source CHECK (
		(source_batch_id IS NOT NULL AND source_generation_id IS NULL)
		OR (source_batch_id IS NULL AND source_generation_id IS NOT NULL)
	)
);

CREATE INDEX IF NOT EXISTS idx_translations_test_run ON translations(test_run_id);
CREATE INDEX IF NOT EXISTS idx_translations_source_batch ON translations(source_batch_id);
CREATE INDEX IF NOT EXISTS idx_translations_source_generation ON translations(source_generation_id);
CREATE INDEX IF NOT EXISTS idx_translations_language ON translations(target_language);
CREATE INDEX IF NOT EXISTS idx_translations_model ON translations(model_id);

NOTIFY pgrst, 'reload schema';

-- 5. prompt_configs: content_length column (legacy ensure)
ALTER TABLE prompt_configs ADD COLUMN IF NOT EXISTS content_length INT;

-- Refresh PostgREST schema cache so the API sees the new columns immediately.
NOTIFY pgrst, 'reload schema';
