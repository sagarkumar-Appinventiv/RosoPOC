export interface ModelInfo {
  id: string;
  name: string;
  provider?: string;
  context_length: number;
  pricing: {
    prompt: string;
    completion: string;
  };
}

export interface VerificationResult {
  parameter: string;
  status: 'PASS' | 'FAIL';
  reason: string;
  affected_fields: string[];
}

export interface GenerationMetrics {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  latency_sec: number;
  cost: number;
}

export interface GeneratedOutputData {
  title?: string;
  introduction?: string;
  attractions?: Array<{ name?: string; title?: string; description?: string; highlights?: string }>;
  activities?: string[] | Array<{ title?: string; description?: string }>;
  best_time_to_visit?: any;
  travel_tips?: string[];
  faqs?: Array<{ question?: string; answer?: string }>;
  language?: string;
  [key: string]: any;
}

export interface HistoryRun {
  run_id: string;
  test_run_id: string;
  country: string;
  city: string;
  language: string;
  model: string;
  model_id: string;
  status: string;
  attempts?: number;
  attempt_number?: number;
  date?: string;
  created_at?: string;
  latency_ms: number;
  total_tokens: number;
  cost: number;
  batch_id?: string;
  batch_status?: string;
  fields_passed?: number;
  fields_total?: number;
}

export interface LegacyRunDetails {
  generation: any;
  test_run: any;
  prompt_config: any;
  verification_results: VerificationResult[];
  regenerations: any[];
}

export interface BatchFieldDetails {
  field_job_id: string;
  field_key: string;
  status: string;
  output: any;
  verification_results: VerificationResult[];
  cost: number;
  tokens: number;
  latency_ms: number;
}

export interface BatchRunDetails {
  batch: any;
  test_run: any;
  prompt_config: any;
  fields: BatchFieldDetails[];
}

export type RunDetailsPayload = LegacyRunDetails | BatchRunDetails;

export interface AppSettings {
  verifier_model_id: string;
  verify_tone: boolean;
  verify_audience: boolean;
  verify_content_length: boolean;
  verify_banned_keywords: boolean;
  verify_style_guide: boolean;
  verify_additional_instructions: boolean;
  content_length_tolerance_pct: number;
  max_verification_retries: number;
  regeneration_strategy: string;
  field_matching_strictness: string;
}

export interface FieldDefinition {
  field_key: string;
  label: string;
  length_mode: 'range' | 'target_tolerance';
  length_min: number | null;
  length_max: number | null;
  unit: string;
  default_order: number;
  schema_type: string;
  is_repeating: boolean;
  max_instances: number;
}

export interface FieldConfig {
  field_key: string;
  length_mode: 'range' | 'target_tolerance';
  length_min: number | null;
  length_max: number | null;
  length_target: number | null;
  length_tolerance_pct: number | null;
  unit: string;
  tone: string | null;
  tone_override: boolean;
  audience: string | null;
  audience_override: boolean;
  banned_keywords: string[] | null;
  banned_keywords_override: boolean;
  style_guide: string | null;
  style_guide_override: boolean;
}

export interface CompiledFieldPrompt {
  field_key: string;
  label: string;
  system_prompt: string;
  user_prompt: string;
}

export interface FieldJobStatus {
  field_job_id: string;
  field_key: string;
  status: string;
  output: any;
  verification: VerificationResult[];
  cost: number;
  tokens: number;
  latency_ms: number;
}

export interface BatchStatus {
  batch_id: string;
  batch_status: string;
  model_name: string;
  progress_phase?: string;
  progress_field?: string | null;
  fields: FieldJobStatus[];
}

export interface TranslationSource {
  source_type: 'batch' | 'generation';
  source_batch_id: string | null;
  source_generation_id: string | null;
  test_run_id: string;
  run_id: string;
  country: string;
  city: string;
  source_language: string;
  model_id: string;
  model_name: string;
  created_at: string;
  source_content: Record<string, any>;
}

export interface TranslationRun {
  id: string;
  test_run_id: string | null;
  source_batch_id: string | null;
  source_generation_id: string | null;
  source_language: string;
  target_language: string;
  model_id: string;
  model_name: string;
  additional_prompt: string;
  status: string;
  source_content: Record<string, any>;
  output_json: Record<string, any> | null;
  error_message?: string | null;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  cost: number;
  created_at: string;
}

export interface TranslationDetail {
  translation: TranslationRun;
  source: TranslationSource | null;
}
