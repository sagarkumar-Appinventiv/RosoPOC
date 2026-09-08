import React, { useState, useEffect, useMemo } from 'react';
import {
  fetchHistory, fetchComparisonRuns, fetchComparisonLanguages,
  getCachedHistory, getCachedComparisonRuns, getCachedComparisonLanguages
} from '../services/api';
import type { HistoryRun } from '../types';
import { Check, Layers, Loader2 } from 'lucide-react';

const renderValue = (v: any) => {
  if (v == null) return '—';
  if (typeof v === 'string') return v;
  return JSON.stringify(v);
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

  useEffect(() => {
    let cancelled = false;
    fetchHistory()
      .then((data) => { if (!cancelled) setHistoryRuns(data); })
      .catch((e) => console.error(e))
      .finally(() => { if (!cancelled) setHistoryLoading(false); });

    fetchComparisonLanguages().then((langs) => {
      if (!cancelled) setAvailableLanguages(langs);
    }).catch((e) => console.error(e));
    return () => { cancelled = true; };
  }, []);

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
        <div className="card">
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
    </div>
  );
};

export default ModelComparisonPage;
