import React, { useState, useEffect } from 'react';
import {
  fetchModels, getOrCreateTestRun, fetchFieldSchema, compileBatch, generateBatch, rerunField
} from '../services/api';
import type { ModelInfo, FieldDefinition, CompiledFieldPrompt } from '../types';
import { useActiveGeneration } from '../context/ActiveGenerationContext';
import { Sparkles, Upload, Globe, Database, Sliders, Bot, RefreshCw, Clock, Cpu, DollarSign, Layers, X, ChevronDown, ChevronRight } from 'lucide-react';

const PREDEFINED_AUDIENCES = [
  'First-Time Visitor', 'Family Traveler', 'Couple Traveler', 'Comfort / Easy-Pace Traveler',
  'Solo / Social Traveler', 'Interest / Deep-Dive Traveler', 'Active / Adventure Traveler'
];

const SUGGESTED_TONES = ['Friendly', 'Professional', 'Inspirational', 'Informative', 'Casual'];
const SUGGESTED_KEYWORDS = ['perfect', 'amazing', 'best', 'must-visit'];
const PREDEFINED_LANGUAGES = ['English', 'Spanish', 'French', 'German', 'Italian', 'Portuguese', 'Dutch', 'Russian', 'Polish', 'Swedish', 'Danish', 'Finnish', 'Greek', 'Czech', 'Romanian', 'Hungarian'];

const FULL_OPENROUTER_MODELS: ModelInfo[] = [
  { id: "openai/gpt-4o", name: "GPT-4o (OpenAI)", context_length: 128000, pricing: { prompt: "0.0000025", completion: "0.00001" } },
  { id: "openai/gpt-4o-mini", name: "GPT-4o Mini (OpenAI)", context_length: 128000, pricing: { prompt: "0.00000015", completion: "0.0000006" } },
  { id: "meta-llama/llama-3.3-70b-instruct", name: "Llama 3.3 70B Instruct (Meta)", context_length: 128000, pricing: { prompt: "0.0000004", completion: "0.0000004" } },
  { id: "deepseek/deepseek-chat", name: "DeepSeek V3 (DeepSeek)", context_length: 64000, pricing: { prompt: "0.00000014", completion: "0.00000028" } },
  { id: "qwen/qwen-2.5-72b-instruct", name: "Qwen 2.5 72B Instruct (Qwen)", context_length: 131072, pricing: { prompt: "0.00000035", completion: "0.0000004" } },
];

const defaultFieldConfig = (fd: FieldDefinition) => ({
  field_key: fd.field_key,
  length_mode: fd.length_mode,
  length_min: fd.length_min,
  length_max: fd.length_max,
  length_target: null,
  length_tolerance_pct: null,
  unit: fd.unit,
  tone: null, tone_override: false,
  audience: null, audience_override: false,
  banned_keywords: [], banned_keywords_override: false,
  style_guide: null, style_guide_override: false,
});

export const ContentGenerationPage: React.FC = () => {
  const [country] = useState('France');
  const [city] = useState('Paris');
  const [selectedLanguage, setSelectedLanguage] = useState('English');
  const [models, setModels] = useState<ModelInfo[]>(FULL_OPENROUTER_MODELS);
  const [selectedModel, setSelectedModel] = useState('');

  // Source data (pure content input — no generation-control fields)
  const [inputJson, setInputJson] = useState<any>(null);
  const [jsonText, setJsonText] = useState('');

  // Global default config
  const [globalTone, setGlobalTone] = useState('');
  const [globalAudience, setGlobalAudience] = useState('');
  const [globalBanned, setGlobalBanned] = useState<string[]>([]);
  const [globalStyle, setGlobalStyle] = useState('');

  // Field schema + per-field overrides
  const [fieldDefs, setFieldDefs] = useState<FieldDefinition[]>([]);
  const [fieldConfigs, setFieldConfigs] = useState<Record<string, any>>({});
  const [includedFields, setIncludedFields] = useState<Record<string, boolean>>({});
  const [expandedField, setExpandedField] = useState<string | null>(null);

  // Batch state (shared across navigation via ActiveGenerationContext)
  const { batchStatus, running, testRunId, setTestRunId, startPolling } = useActiveGeneration();
  const [compiledPrompts, setCompiledPrompts] = useState<CompiledFieldPrompt[]>([]);
  const [showReview, setShowReview] = useState(false);

  useEffect(() => {
    fetch('/paris.json')
      .then((r) => r.json())
      .then((d) => { setInputJson(d); setJsonText(JSON.stringify(d, null, 2)); })
      .catch(() => {
        const fb = { city: "Paris", country: "France", attractions: [{ name: "Eiffel Tower" }, { name: "Louvre Museum" }], activities: ["Seine River Cruise"] };
        setInputJson(fb); setJsonText(JSON.stringify(fb, null, 2));
      });

    fetchModels().then((d) => { if (d && d.length) setModels(d); }).catch(() => {});
    fetchFieldSchema().then((fds: FieldDefinition[]) => {
      setFieldDefs(fds);
      const cfgs: Record<string, any> = {};
      const inc: Record<string, boolean> = {};
      fds.forEach((fd) => { cfgs[fd.field_key] = defaultFieldConfig(fd); inc[fd.field_key] = true; });
      setFieldConfigs(cfgs);
      setIncludedFields(inc);
    }).catch(() => {});
  }, []);

  const handleGenerateClick = async () => {
    if (!selectedModel) { alert('Please select an OpenRouter model.'); return; }
    if (!inputJson || !Object.keys(inputJson).length) { alert('Please provide source JSON data.'); return; }
    try {
      const tr = await getOrCreateTestRun({
        country, city, language: selectedLanguage, input_json: inputJson,
        tone: globalTone, audience: globalAudience, banned_keywords: globalBanned, style_guide: globalStyle
      });
      setTestRunId(tr.test_run_id);
      const keys = fieldDefs.filter((f) => includedFields[f.field_key]).map((f) => f.field_key);
      const prompts = await compileBatch(tr.test_run_id, keys);
      setCompiledPrompts(prompts);
      setShowReview(true);
    } catch (e: any) {
      alert(e.message || 'Failed to compile batch prompts.');
    }
  };

  const handleRunBatch = async () => {
    setShowReview(false);
    try {
      const payload = {
        test_run_id: testRunId,
        model_name: selectedModel,
        fields: compiledPrompts.map((p) => ({ field_key: p.field_key, system_prompt: p.system_prompt, user_prompt: p.user_prompt }))
      };
      const res = await generateBatch(payload);
      startPolling(res.batch_id);
    } catch (e: any) {
      alert(e.message || 'Failed to start batch.');
    }
  };

  const handleRerunField = async (fieldKey: string) => {
    if (!batchStatus) return;
    try {
      await rerunField(batchStatus.batch_id, fieldKey);
      startPolling(batchStatus.batch_id);
    } catch (e: any) {
      alert(e.message || 'Failed to re-run field.');
    }
  };

  const updateFieldConfig = (fieldKey: string, patch: any) => {
    setFieldConfigs((prev) => ({ ...prev, [fieldKey]: { ...prev[fieldKey], ...patch } }));
  };

  const toggleIncluded = (fieldKey: string) => {
    setIncludedFields((prev) => ({ ...prev, [fieldKey]: !prev[fieldKey] }));
  };

  const renderFieldValue = (output: any) => {
    if (output == null) return '—';
    if (typeof output === 'string') return output;
    return JSON.stringify(output);
  };

  const terminalPass = (s: string) => ['passed', 'regenerated_pass'].includes(s);
  const terminalFail = (s: string) => ['failed', 'regenerated_fail'].includes(s);

  const includedKeys = fieldDefs.filter((f) => includedFields[f.field_key]).map((f) => f.field_key);
  const summary = batchStatus
    ? {
        passed: batchStatus.fields.filter((f) => terminalPass(f.status)).length,
        failed: batchStatus.fields.filter((f) => terminalFail(f.status)).length,
        total: batchStatus.fields.length
      }
    : null;

  return (
    <div className="workspace-container">
      <div className="two-column-workspace">
        {/* LEFT COLUMN — Input & Context */}
        <div>
          <div className="card">
            <div className="card-header-badge"><div className="step-number">1</div><div className="step-title"><Globe size={16} color="#2563EB" /> Location, Language & Model</div></div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
              <div><label className="form-label">Country</label><select className="select-input" value={country} disabled><option>France</option></select></div>
              <div><label className="form-label">City</label><select className="select-input" value={city} disabled><option>Paris</option></select></div>
              <div><label className="form-label">Target Language</label>
                <select className="select-input" value={selectedLanguage} onChange={(e) => setSelectedLanguage(e.target.value)}>
                  {PREDEFINED_LANGUAGES.map((l) => <option key={l}>{l}</option>)}
                </select>
              </div>
              <div><label className="form-label">OpenRouter Model</label>
                <select className="select-input" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)}>
                  <option value="">Select a Model...</option>
                  {models.map((m) => <option key={m.id} value={m.id}>🤖 {m.name}</option>)}
                </select>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header-badge" style={{ justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div className="step-number">2</div><div className="step-title"><Database size={16} color="#2563EB" /> Source Data</div>
              </div>
              <label className="btn-secondary" style={{ cursor: 'pointer', padding: '5px 12px', fontSize: '12px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                <Upload size={14} /> Upload JSON
                <input type="file" accept=".json" style={{ display: 'none' }} onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  const r = new FileReader();
                  r.onload = () => { try { const d = JSON.parse(r.result as string); setInputJson(d); setJsonText(JSON.stringify(d, null, 2)); } catch { alert('Invalid JSON.'); } };
                  r.readAsText(f);
                }} />
              </label>
            </div>
            <textarea className="textarea-input" rows={8} value={jsonText} onChange={(e) => {
              setJsonText(e.target.value);
              try { setInputJson(JSON.parse(e.target.value)); } catch {}
            }} style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', backgroundColor: '#F8FAFC' }} />
            <p style={{ fontSize: '11px', color: '#64748B', margin: '6px 0 0' }}>Pure content input — facts about the destination. Length/tone/etc. live in the field config, not here.</p>
          </div>
        </div>

        {/* RIGHT COLUMN — Control */}
        <div style={{ position: 'sticky', top: '24px' }}>
          <div className="card">
            <div className="card-header-badge"><div className="step-number">3</div><div className="step-title"><Sliders size={16} color="#2563EB" /> Global Default Config</div></div>
            <div className="form-group">
              <label className="form-label">Tone (default)</label>
              <div className="pill-grid">
                {SUGGESTED_TONES.map((t) => <button key={t} className={`pill-button ${globalTone === t ? 'selected' : ''}`} onClick={() => setGlobalTone(globalTone === t ? '' : t)}>{t}</button>)}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Audience (default)</label>
              <div className="pill-grid">
                {PREDEFINED_AUDIENCES.map((a) => <button key={a} className={`pill-button ${globalAudience === a ? 'selected' : ''}`} onClick={() => setGlobalAudience(globalAudience === a ? '' : a)}>{a}</button>)}
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Banned Keywords (default)</label>
              <div className="pill-grid">
                {SUGGESTED_KEYWORDS.map((k) => { const sel = globalBanned.includes(k); return <button key={k} className={`pill-button ${sel ? 'selected' : ''}`} onClick={() => setGlobalBanned(sel ? globalBanned.filter((x) => x !== k) : [...globalBanned, k])}>{sel ? '☑' : '☐'} {k}</button>; })}
              </div>
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label className="form-label">Style Guide (default)</label>
              <textarea className="textarea-input" rows={2} value={globalStyle} onChange={(e) => setGlobalStyle(e.target.value)} placeholder="Optional style guide..." />
            </div>
          </div>

          <div className="card">
            <div className="card-header-badge"><div className="step-number">4</div><div className="step-title"><Layers size={16} color="#2563EB" /> Field List ({includedKeys.length}/{fieldDefs.length})</div></div>
            {fieldDefs.length === 0 && <p style={{ fontSize: '12px', color: '#64748B' }}>Loading field schema...</p>}
            {fieldDefs.map((fd) => {
              const cfg = fieldConfigs[fd.field_key];
              const expanded = expandedField === fd.field_key;
              return (
                <div key={fd.field_key} style={{ border: '1px solid #E2E8F0', borderRadius: '8px', marginBottom: '8px', overflow: 'hidden' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 10px', background: '#F8FAFC' }}>
                    <input type="checkbox" checked={!!includedFields[fd.field_key]} onChange={() => toggleIncluded(fd.field_key)} />
                    <span style={{ fontSize: '13px', fontWeight: 700, flex: 1 }}>{fd.label}</span>
                    <span style={{ fontSize: '11px', color: '#64748B' }}>
                      {fd.length_min && fd.length_max ? `${fd.length_min}–${fd.length_max} ${fd.unit}` : fd.length_max ? `≤ ${fd.length_max} ${fd.unit}` : ''}
                      {fd.is_repeating ? ` · up to ${fd.max_instances}` : ''}
                    </span>
                    <button className="btn-secondary" style={{ padding: '2px 6px' }} onClick={() => setExpandedField(expanded ? null : fd.field_key)}>
                      {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                  </div>
                  {expanded && cfg && (
                    <div style={{ padding: '10px', borderTop: '1px solid #E2E8F0', fontSize: '12px' }}>
                      <div style={{ marginBottom: '8px' }}>
                        <label className="form-label">Length ({cfg.length_mode === 'range' ? 'min–max' : 'target ± tol'})</label>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          {cfg.length_mode === 'range' ? (
                            <>
                              <input className="input-text" type="number" placeholder="min" value={cfg.length_min ?? ''} onChange={(e) => updateFieldConfig(fd.field_key, { length_min: e.target.value ? Number(e.target.value) : null })} style={{ width: '80px' }} />
                              <input className="input-text" type="number" placeholder="max" value={cfg.length_max ?? ''} onChange={(e) => updateFieldConfig(fd.field_key, { length_max: e.target.value ? Number(e.target.value) : null })} style={{ width: '80px' }} />
                            </>
                          ) : (
                            <>
                              <input className="input-text" type="number" placeholder="target" value={cfg.length_target ?? ''} onChange={(e) => updateFieldConfig(fd.field_key, { length_target: e.target.value ? Number(e.target.value) : null })} style={{ width: '80px' }} />
                              <input className="input-text" type="number" placeholder="tol %" value={cfg.length_tolerance_pct ?? ''} onChange={(e) => updateFieldConfig(fd.field_key, { length_tolerance_pct: e.target.value ? Number(e.target.value) : null })} style={{ width: '80px' }} />
                            </>
                          )}
                        </div>
                      </div>
                      <div style={{ fontSize: '11px', color: '#94A3B8' }}>Tone / Audience / Keywords / Style inherit from Global Default.</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="card">
            <div className="card-header-badge"><div className="step-number">5</div><div className="step-title"><Bot size={16} color="#2563EB" /> Execute</div></div>
            <button className="btn-primary" style={{ width: '100%', padding: '14px', fontSize: '15px' }} onClick={handleGenerateClick} disabled={running || !selectedModel}>
              <Sparkles size={18} /> {running ? 'Working...' : 'Review Batch Prompts'}
            </button>
            <p style={{ fontSize: '11px', color: '#64748B', marginTop: '6px' }}>Every field gets its own prompt. Review all prompts before spending API credits.</p>
          </div>
        </div>
      </div>

      {/* BOTTOM FULL-WIDTH — per-field results */}
      {batchStatus && (
        <div className="card" style={{ marginTop: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0 }}>Batch Results</h3>
            <span className={`badge badge-${batchStatus.batch_status === 'completed' ? 'verified' : batchStatus.batch_status === 'failed' ? 'failed' : 'unverified'}`}>{batchStatus.batch_status}</span>
            {summary && <span style={{ fontSize: '12px', color: '#64748B' }}>{summary.passed}/{summary.total} passed · {summary.failed} failed</span>}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
            {batchStatus.fields.map((f) => (
              <div key={f.field_job_id} style={{ border: '1px solid #E2E8F0', borderRadius: '10px', padding: '14px', background: '#FFFFFF' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <strong style={{ fontSize: '13px' }}>{f.field_key}</strong>
                  <span className={`badge badge-${terminalPass(f.status) ? 'verified' : terminalFail(f.status) ? 'failed' : 'unverified'}`}>{f.status}</span>
                </div>
                <div style={{ fontSize: '12px', color: '#334155', background: '#F8FAFC', padding: '8px', borderRadius: '6px', maxHeight: '120px', overflowY: 'auto' }}>
                  {renderFieldValue(f.output)}
                </div>
                <div style={{ display: 'flex', gap: '10px', marginTop: '8px', fontSize: '11px', color: '#64748B' }}>
                  <span><Clock size={12} /> {(f.latency_ms / 1000).toFixed(1)}s</span>
                  <span><Cpu size={12} /> {f.tokens}</span>
                  <span><DollarSign size={12} /> ${f.cost?.toFixed(4)}</span>
                </div>
                {f.verification && f.verification.length > 0 && (
                  <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                    {f.verification.map((v, i) => (
                      <span key={i} className={`badge badge-${v.status === 'PASS' ? 'verified' : 'failed'}`} style={{ fontSize: '10px' }}>{v.parameter}: {v.status}</span>
                    ))}
                  </div>
                )}
                {terminalFail(f.status) && (
                  <button className="btn-secondary" style={{ marginTop: '10px', width: '100%', padding: '6px', fontSize: '12px' }} onClick={() => handleRerunField(f.field_key)}>
                    <RefreshCw size={12} /> Rerun this field
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FULL-SCREEN multi-field prompt review modal */}
      {showReview && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(15,23,42,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
          <div style={{ width: '100%', maxWidth: '1100px', height: '90vh', background: '#fff', borderRadius: '16px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ padding: '18px 24px', borderBottom: '1px solid #E2E8F0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 800 }}>Review Batch — {compiledPrompts.length} Fields</h3>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748B' }}>Each field is one LLM call. You are about to execute {compiledPrompts.length} requests using {selectedModel}.</p>
              </div>
              <button className="btn-secondary" onClick={() => setShowReview(false)}><X size={16} /> Close</button>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px', background: '#F8FAFC' }}>
              {compiledPrompts.map((p) => (
                <div key={p.field_key} style={{ border: '1px solid #E2E8F0', borderRadius: '10px', marginBottom: '12px', background: '#fff', overflow: 'hidden' }}>
                  <div style={{ padding: '10px 14px', background: '#F1F5F9', fontWeight: 700, fontSize: '13px' }}>
                    {p.label} <span style={{ color: '#64748B', fontWeight: 400 }}>({p.field_key})</span>
                  </div>
                  <div style={{ padding: '12px 14px' }}>
                    <label className="form-label" style={{ fontSize: '10px' }}>System Prompt</label>
                    <textarea className="textarea-input" rows={4} value={p.system_prompt} onChange={(e) => setCompiledPrompts((prev) => prev.map((x) => x.field_key === p.field_key ? { ...x, system_prompt: e.target.value } : x))} style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }} />
                    <label className="form-label" style={{ fontSize: '10px', marginTop: '8px' }}>User Prompt</label>
                    <textarea className="textarea-input" rows={8} value={p.user_prompt} onChange={(e) => setCompiledPrompts((prev) => prev.map((x) => x.field_key === p.field_key ? { ...x, user_prompt: e.target.value } : x))} style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }} />
                  </div>
                </div>
              ))}
            </div>
            <div style={{ padding: '16px 24px', borderTop: '1px solid #E2E8F0', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button className="btn-secondary" onClick={() => setShowReview(false)}>Cancel / Edit Settings</button>
              <button className="btn-primary" onClick={handleRunBatch} disabled={running}><Sparkles size={16} /> Run Batch</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContentGenerationPage;
