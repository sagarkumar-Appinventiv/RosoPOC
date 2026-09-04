-- RosoTravel POC — required Supabase migrations
-- Run this in Supabase Dashboard → SQL Editor.
-- Idempotent: safe to run multiple times.

-- 1. batches: Semantic Consistency Planner result
ALTER TABLE batches ADD COLUMN IF NOT EXISTS plan_json JSONB;

-- 2. field_jobs: serverless queue retry-loop protection
ALTER TABLE field_jobs ADD COLUMN IF NOT EXISTS attempt_count INT DEFAULT 0;

-- 3. verification_results: per-field scoping (v2)
ALTER TABLE verification_results ADD COLUMN IF NOT EXISTS field_job_id UUID REFERENCES field_jobs(id) ON DELETE CASCADE;

-- 4. regenerations: per-field scoping (v2)
ALTER TABLE regenerations ADD COLUMN IF NOT EXISTS field_job_id UUID REFERENCES field_jobs(id) ON DELETE CASCADE;

-- 5. prompt_configs: content_length column (legacy ensure)
ALTER TABLE prompt_configs ADD COLUMN IF NOT EXISTS content_length INT;

-- Refresh PostgREST schema cache so the API sees the new columns immediately.
NOTIFY pgrst, 'reload schema';
