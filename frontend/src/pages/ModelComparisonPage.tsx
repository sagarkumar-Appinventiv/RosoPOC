import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  fetchHistory, fetchComparisonRuns, fetchComparisonLanguages, fetchTranslationLanguages, fetchTranslationComparisonRuns,
  getCachedHistory, getCachedComparisonRuns, getCachedComparisonLanguages
} from '../services/api';
import type { HistoryRun } from '../types';
import { Check, Layers, Loader2 } from 'lucide-react';
import StructuredContent from '../components/StructuredContent';

const renderValue = (value: any) => {
  if (value == null) return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
};

export const ModelComparisonPage: React.FC = () => {
  // Seed from the tab-level cache so already-fetched data renders instantly
  // when switching back to this tab, while a refresh runs in the background.
  const cachedHistory = getCachedHistory();
  const cachedLanguages = getCachedComparisonLanguages();
  const [historyRuns, setHistoryRuns] = useState<HistoryRun[]>(cachedHistory ?? []);
  const [runs, setRuns] = useState<any[]>([]);
  const [selectedBatchIds, setSelectedBatchIds] = useState<string[]>([]);
  const [compared, setCompared] = useState<any[]>([]);
  const [availableLanguages, setAvailableLanguages] = useState<string[]>(cachedLanguages ?? []);
  const [selectedLanguage, setSelectedLanguage] = useState<string>('');
  const [historyLoading, setHistoryLoading] = useState(!cachedHistory);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState('');
  const [comparisonMode, setComparisonMode] = useState<'generation' | 'translation'>('generation');
  const [translationLanguages, setTranslationLanguages] = useState<string[]>([]);
  const [translationLanguage, setTranslationLanguage] = useState('');
  const [translationSourceId, setTranslationSourceId] = useState('');
  const [translationRuns, setTranslationRuns] = useState<any[]>([]);
  const [selectedTranslationIds, setSelectedTranslationIds] = useState<string[]>([]);
  const [comparedTranslations, setComparedTranslations] = useState<any[]>([]);
  const generationComparisonRef = useRef<HTMLDivElement>(null);
  const translationComparisonRef = useRef<HTMLDivElement>(null);
  const [translationRunsLoading, setTranslationRunsLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchHistory()
      .then((data) => { if (!cancelled) setHistoryRuns(data); })
      .catch((e) => console.error(e))
      .finally(() => { if (!cancelled) setHistoryLoading(false); });

    fetchComparisonLanguages().then((langs) => {
      if (!cancelled) setAvailableLanguages(langs);
    }).catch((e) => console.error(e));
    fetchTranslationLanguages().then((langs) => {
      setTranslationLanguages(langs);
      if (langs[0]) setTranslationLanguage(langs[0]);
    }).catch((e) => console.error(e));
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (comparisonMode !== 'translation' || !translationLanguage) return;
    let cancelled = false;
    setTranslationRunsLoading(true);
    setRunsError('');
    fetchTranslationComparisonRuns(translationLanguage, translationSourceId || undefined)
      .then((data) => { if (!cancelled) setTranslationRuns(data); })
      .catch((e) => { if (!cancelled) setRunsError(e.message || 'Unable to load translations.'); })
      .finally(() => { if (!cancelled) setTranslationRunsLoading(false); });
    setSelectedTranslationIds([]);
    setComparedTranslations([]);
    return () => { cancelled = true; };
  }, [comparisonMode, translationLanguage, translationSourceId]);

  useEffect(() => {
    if (comparisonMode === 'generation' && compared.length > 0) {
      generationComparisonRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    if (comparisonMode === 'translation' && comparedTranslations.length > 0) {
      translationComparisonRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [comparisonMode, compared, comparedTranslations]);

  const renderTranslationComparison = () => (
    <>
      <div className="card" style={{ padding: '24px 28px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ width: '200px' }}><label className="form-label">Target language</label><select className="select-input" value={translationLanguage} onChange={(e) => setTranslationLanguage(e.target.value)}>{translationLanguages.map((lang) => <option key={lang}>{lang}</option>)}</select></div>
          <div style={{ width: '220px' }}><label className="form-label">Source document</label><select className="select-input" value={translationSourceId} onChange={(e) => setTranslationSourceId(e.target.value)}><option value="">All sources</option>{Array.from(new Set(translationRuns.map((run) => run.source_batch_id || run.source_generation_id).filter(Boolean))).map((id) => <option key={id} value={id}>{String(id).substring(0, 8)}</option>)}</select></div>
          <div style={{ flex: 1, color: '#64748B', fontSize: '13px' }}>Select translations created from the same source document.</div>
          <button className="btn-primary" disabled={selectedTranslationIds.length < 2} onClick={() => setComparedTranslations(translationRuns.filter((run) => selectedTranslationIds.includes(run.id)))}>Compare Selected ({selectedTranslationIds.length})</button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px', marginTop: '20px' }}>
          {translationRunsLoading ? (
            <div style={{ gridColumn: '1 / -1', padding: '40px', textAlign: 'center', color: '#64748B', border: '1px dashed #CBD5E1', borderRadius: '8px' }}>
              <Loader2 size={28} className="animate-spin" color="#2563EB" />
              <div style={{ marginTop: '10px', fontSize: '13px' }}>Loading translation comparisons...</div>
            </div>
          ) : translationRuns.map((run) => {
            const checked = selectedTranslationIds.includes(run.id);
            const sourceId = run.source_batch_id || run.source_generation_id || '';
            return <div key={run.id} onClick={() => setSelectedTranslationIds((prev) => prev.includes(run.id) ? prev.filter((id) => id !== run.id) : [...prev, run.id])} style={{ border: `2px solid ${checked ? '#2563EB' : '#E2E8F0'}`, padding: '16px', borderRadius: '8px', cursor: 'pointer' }}><strong>{run.model_name}</strong><div style={{ fontSize: '12px', color: '#64748B', marginTop: '8px' }}>Source: {sourceId.substring(0, 8)} · {run.status}</div></div>;
          })}
        </div>
      </div>
      {comparedTranslations.length > 0 && (
        <div ref={translationComparisonRef} className="card" style={{ padding: '24px 28px', scrollMarginTop: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', gap: '16px', flexWrap: 'wrap' }}>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0 }}>Translation Comparison</h3>
              <p style={{ fontSize: '12px', color: '#64748B', margin: '5px 0 0' }}>
                Same English source compared across {comparedTranslations.length} models in {translationLanguage}.
              </p>
            </div>
            <span className="badge badge-verified">{translationLanguage}</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${comparedTranslations.length}, minmax(320px, 1fr))`, gap: '20px', overflowX: 'auto', alignItems: 'stretch' }}>
            {comparedTranslations.map((run) => (
              <div key={run.id} style={{ border: '1px solid #E2E8F0', borderRadius: '14px', background: '#FFFFFF', overflow: 'hidden', display: 'flex', flexDirection: 'column', minWidth: 0, boxShadow: 'var(--shadow-sm)' }}>
                <div style={{ padding: '16px 20px', background: 'linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%)', borderBottom: '1px solid #C7D2FE' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                    <h4 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: '#3730A3', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={run.model_name}>
                      {run.model_name}
                    </h4>
                    <span className={`badge badge-${String(run.status).toLowerCase()}`}>{run.status}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#64748B', marginTop: '6px' }}>
                    {run.model_id || 'OpenRouter model'} · {run.target_language || translationLanguage}
                  </div>
                </div>

                <div style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: '18px', flex: 1 }}>
                  <section>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <span style={{ width: '4px', height: '16px', background: '#94A3B8', borderRadius: '2px' }} />
                      <h5 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#64748B', margin: 0 }}>Original English</h5>
                    </div>
                    <div style={{ margin: 0, padding: '14px', background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', fontSize: '12px', maxHeight: '420px', overflowY: 'auto' }}>
                      <StructuredContent value={run.source_content} />
                    </div>
                  </section>

                  <section>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                      <span style={{ width: '4px', height: '16px', background: '#2563EB', borderRadius: '2px' }} />
                      <h5 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em', color: '#2563EB', margin: 0 }}>{translationLanguage} Translation</h5>
                    </div>
                    <div style={{ margin: 0, padding: '14px', background: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: '8px', fontSize: '12px', maxHeight: '520px', overflowY: 'auto' }}>
                      <StructuredContent value={run.translated_content ?? run.output_json} />
                    </div>
                  </section>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );

  // Filter history runs by selected language
  const filteredHistoryRuns = useMemo(
    () => selectedLanguage
      ? historyRuns.filter(r => r.language === selectedLanguage)
      : historyRuns,
    [historyRuns, selectedLanguage]
  );

  // Keep the derived list stable so checkbox clicks do not reset selection.
  const distinctTestRunIds = useMemo(() => Array.from(new Set(
    filteredHistoryRuns.map((r) => r.test_run_id).filter(Boolean)
  )), [filteredHistoryRuns]);

  // Auto-select first test_run_id from filtered runs when language changes
  // (only used when a specific language is selected)
  

  // Fetch comparison runs - for "All Languages" fetch all test_run_ids and combine
  useEffect(() => {
    if (distinctTestRunIds.length === 0) {
      setRuns([]);
      setRunsError('');
      setRunsLoading(false);
      return;
    }

    let cancelled = false;

    const fetchWithTimeout = (promise: Promise<any>, timeoutMs = 10000) => {
      return Promise.race([
        promise,
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Request timeout')), timeoutMs)
        )
      ]);
    };

    const loadRuns = async () => {
      if (!cancelled) setRunsError('');
      // Check for cached data FIRST - for both single language and all languages
      let cachedData: any[] | null = null;
      
      // A language can contain multiple test runs. Use cached data only when
      // every test-run request is cached, then combine and deduplicate it.
      const allCached = distinctTestRunIds.map(id => getCachedComparisonRuns(id));
      if (allCached.every(c => c !== null)) {
        const combined = allCached.flat();
        const seen = new Set<string>();
        cachedData = combined.filter(r => {
          const key = r.batch_id || r.generation?.id;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
      }

      // If we have cached data, use it immediately WITHOUT showing loading
      if (cachedData) {
        if (!cancelled) {
          setRuns(cachedData);
          setRunsLoading(false);
        }
      } else {
        // No cached data - show loading and fetch
        if (!cancelled) setRunsLoading(true);
      }

      // Fetch every test run for both a language filter and All Languages.
      try {
        const allRunsPromises = distinctTestRunIds.map(id =>
          fetchWithTimeout(fetchComparisonRuns(id), 10000)
        );
        const results = await Promise.allSettled(allRunsPromises);
        if (!cancelled) {
          const allRunsArrays = results
            .filter((r): r is PromiseFulfilledResult<any[]> => r.status === 'fulfilled')
            .map(r => r.value);
          const combined = allRunsArrays.flat();
          const seen = new Set<string>();
          const unique = combined.filter(r => {
            const key = r.batch_id || r.generation?.id;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
          setRuns(unique);
        }
      } catch (e) {
        console.error(e);
        if (!cancelled) setRunsError('Unable to load comparison runs. Make sure the backend is running on port 8000.');
      }
      if (!cancelled) setRunsLoading(false);
    };

    loadRuns();
    return () => { cancelled = true; };
  }, [distinctTestRunIds, selectedLanguage]);

  // Reset selection only when the test run context changes (language or test_run_ids), not on every runs update
  useEffect(() => {
    setSelectedBatchIds([]);
    setCompared([]);
  }, [distinctTestRunIds, selectedLanguage]);

  const toggleSelect = (id: string) => {
    setSelectedBatchIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  };

  const handleCompare = () => {
    setCompared(runs.filter((r) => selectedBatchIds.includes(r.batch_id || r.generation?.id)));
  };

  // For legacy (single flat generation) runs, fall back gracefully.
  const legacyMode = compared.length > 0 && compared.some((r) => !r.fields);

  return (
    <div className="workspace-container">
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <button className={comparisonMode === 'generation' ? 'btn-primary' : 'btn-secondary'} onClick={() => setComparisonMode('generation')}>Generation Comparison</button>
        <button className={comparisonMode === 'translation' ? 'btn-primary' : 'btn-secondary'} onClick={() => setComparisonMode('translation')}>Translation Comparison</button>
      </div>
      {comparisonMode === 'translation' ? renderTranslationComparison() : <>
      <div className="card" style={{ padding: '24px 28px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 800, margin: 0 }}>Model Comparison</h2>
            <p style={{ fontSize: '13px', color: '#64748B', marginTop: '4px' }}>Select 2 or more runs and compare side-by-side, per field.</p>
          </div>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'flex-end' }}>
            <div style={{ width: '180px' }}>
              <label className="form-label">Filter by Language</label>
              <select className="select-input" value={selectedLanguage} onChange={(e) => setSelectedLanguage(e.target.value)}>
                <option value="">All Languages</option>
                {availableLanguages.map((lang) => (
                  <option key={lang} value={lang}>{lang}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            <span style={{ fontSize: '14px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={18} color="#2563EB" /> Select Runs to Compare ({selectedBatchIds.length} selected)
            </span>
            <button className="btn-primary" onClick={handleCompare} disabled={selectedBatchIds.length < 2}>
              <Check size={16} /> Compare Selected ({selectedBatchIds.length})
            </button>
          </div>

          {historyLoading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748B', border: '1px dashed #CBD5E1', borderRadius: '8px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', fontSize: '13px' }}>
              <Loader2 size={28} className="animate-spin" color="#2563EB" />
              Loading test runs...
            </div>
          ) : runsLoading ? (
            <div style={{ padding: '40px', textAlign: 'center', color: '#64748B', border: '1px dashed #CBD5E1', borderRadius: '8px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', fontSize: '13px' }}>
              <Loader2 size={28} className="animate-spin" color="#2563EB" />
              Loading runs for this test run...
            </div>
          ) : runsError ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#B91C1C', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '8px', fontSize: '13px' }}>
              {runsError}
            </div>
          ) : runs.length > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
              {runs.map((r, idx) => {
                const id = r.batch_id || r.generation?.id || `run-${idx}`;
                const model = r.model_name || r.generation?.model_name || r.generation?.model_id || 'unknown';
                const status = r.status || r.generation?.status || 'unknown';
                const checked = selectedBatchIds.includes(id);
                return (
                  <div key={id} onClick={() => toggleSelect(id)} style={{
                    background: checked ? '#F5F3FF' : '#fff', border: '2px solid', borderColor: checked ? '#6366F1' : '#E2E8F0',
                    borderRadius: '12px', padding: '16px', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '10px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                        <input type="checkbox" checked={checked} onChange={() => {}} />
                        <h4 style={{ fontSize: '14px', fontWeight: 800, margin: 0 }}>🤖 {model}</h4>
                      </div>
                      <span className={`badge badge-${String(status).toLowerCase()}`}>{status}</span>
                    </div>
                    {r.fields && <span style={{ fontSize: '11px', color: '#64748B' }}>{r.fields.length} fields</span>}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ padding: '20px', textAlign: 'center', color: '#64748B', border: '1px dashed #CBD5E1', borderRadius: '8px' }}>
              No runs found for this test run yet. Generate a batch first.
            </div>
          )}
        </div>
      </div>

      {compared.length > 0 && (
        <div ref={generationComparisonRef} className="card" style={{ scrollMarginTop: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 800, marginBottom: '16px' }}>Side-by-Side Comparison</h3>
          {legacyMode ? (
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${compared.length}, minmax(280px, 1fr))`, gap: '16px' }}>
              {compared.map((r, i) => (
                <div key={i} style={{ border: '1px solid #E2E8F0', borderRadius: '8px', padding: '12px' }}>
                  <strong>{r.generation?.model_name || r.generation?.model_id}</strong>
                  <pre style={{ fontSize: '11px', whiteSpace: 'pre-wrap' }}>{JSON.stringify(r.generation?.output_json, null, 2)}</pre>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${compared.length}, minmax(320px, 1fr))`, gap: '20px', overflowX: 'auto' }}>
              {compared.map((r, i) => {
                const fieldKeys = (r.fields || []).map((f: any) => f.field_key);
                return (
                  <div key={i} style={{ border: '1px solid #E2E8F0', borderRadius: '14px', background: '#FFFFFF', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: 'var(--shadow-sm)' }}>
                    <div style={{ padding: '16px 20px', background: 'linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%)', borderBottom: '1px solid #C7D2FE' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <h4 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: '#3730A3' }}>🤖 {r.model_name}</h4>
                        <span className={`badge badge-${String(r.status).toLowerCase()}`}>{r.status}</span>
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748B', marginTop: '6px' }}>{fieldKeys.length} fields generated</div>
                    </div>

                    <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '16px', flex: 1 }}>
                      {fieldKeys.length === 0 && (
                        <div style={{ color: '#64748B', fontSize: '12px' }}>No fields available for this run.</div>
                      )}
{fieldKeys.map((fk: string) => {
                            const field = (r.fields || []).find((f: any) => f.field_key === fk);
                            return (
                              <div key={fk} style={{ borderBottom: '1px solid #F1F5F9', paddingBottom: '12px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                                  <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.03em', color: '#64748B' }}>{fk}</span>
                                </div>
                                <div style={{ fontSize: '12px', color: '#334155', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
                                  {renderValue(field?.output)}
                                </div>
                              </div>
                            );
                          })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
      </>}
    </div>
  );
};

export default ModelComparisonPage;
