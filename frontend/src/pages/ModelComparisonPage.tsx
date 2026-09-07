import React, { useState, useEffect } from 'react';
import { fetchHistory, fetchComparisonRuns } from '../services/api';
import type { HistoryRun } from '../types';
import { Check, Layers } from 'lucide-react';

const renderValue = (v: any) => {
  if (v == null) return '—';
  if (typeof v === 'string') return v;
  return JSON.stringify(v);
};

export const ModelComparisonPage: React.FC = () => {
  const [historyRuns, setHistoryRuns] = useState<HistoryRun[]>([]);
  const [selectedTestRunId, setSelectedTestRunId] = useState('');
  const [runs, setRuns] = useState<any[]>([]); // one entry per batch/run with fields[]
  const [selectedBatchIds, setSelectedBatchIds] = useState<string[]>([]);
  const [compared, setCompared] = useState<any[]>([]);

  useEffect(() => {
    fetchHistory().then((data) => {
      setHistoryRuns(data);
      if (data.length > 0) setSelectedTestRunId(data[0].test_run_id);
    }).catch((e) => console.error(e));
  }, []);

  useEffect(() => {
    if (selectedTestRunId) {
      fetchComparisonRuns(selectedTestRunId).then((data) => {
        setRuns(data);
        setSelectedBatchIds([]);
        setCompared([]);
      }).catch((e) => console.error(e));
    }
  }, [selectedTestRunId]);

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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
          <div>
            <h2 style={{ fontSize: '20px', fontWeight: 800, margin: 0 }}>Model Comparison</h2>
            <p style={{ fontSize: '13px', color: '#64748B', marginTop: '4px' }}>Select 2 or more runs and compare side-by-side, per field.</p>
          </div>
          <div style={{ width: '260px' }}>
            <label className="form-label">Select Test Run Context</label>
            <select className="select-input" value={selectedTestRunId} onChange={(e) => setSelectedTestRunId(e.target.value)}>
              {historyRuns.filter((v, i, a) => a.findIndex((x) => x.test_run_id === v.test_run_id) === i).map((r) => (
                <option key={r.run_id} value={r.test_run_id}>{r.city}, {r.country} ({r.language || 'English'})</option>
              ))}
              {historyRuns.length === 0 && <option value="default">Paris, France</option>}
            </select>
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

          {runs.length > 0 ? (
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
