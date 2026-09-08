import React, { useEffect, useState } from 'react';
import { fetchRunDetails, fetchTranslationDetails } from '../services/api';
import { X } from 'lucide-react';

interface RunDetailDrawerProps {
  runId: string;
  kind?: 'generation' | 'translation';
  onClose: () => void;
}

const renderValue = (v: any) => {
  if (v == null) return '—';
  if (typeof v === 'string') return v;
  return JSON.stringify(v, null, 2);
};

const statusBadgeClass = (s: string) => {
  const st = String(s || '').toLowerCase();
  if (['passed', 'regenerated_pass', 'verified', 'completed', 'pass'].includes(st)) return 'verified';
  if (['failed', 'regenerated_fail'].includes(st)) return 'failed';
  return 'unverified';
};

const VerificationTable: React.FC<{ results: any[] }> = ({ results }) => (
  <table className="data-table">
    <thead>
      <tr>
        <th>Parameter</th>
        <th>Status</th>
        <th>Reason</th>
      </tr>
    </thead>
    <tbody>
      {results.length > 0 ? results.map((v: any, i: number) => (
        <tr key={i}>
          <td style={{ fontWeight: 600 }}>{v.parameter}</td>
          <td>
            <span className={`badge badge-${v.status === 'PASS' ? 'verified' : 'failed'}`}>
              {v.status}
            </span>
          </td>
          <td style={{ fontSize: '12px', color: '#475569' }}>{v.reason}</td>
        </tr>
      )) : (
        <tr>
          <td colSpan={3} style={{ fontSize: '12px', color: '#94A3B8' }}>No verification results recorded.</td>
        </tr>
      )}
    </tbody>
  </table>
);

const OutputBlock: React.FC<{ output: any }> = ({ output }) => (
  <pre style={{
    backgroundColor: '#0F172A',
    color: '#E2E8F0',
    padding: '12px',
    borderRadius: '8px',
    fontSize: '12px',
    maxHeight: '300px',
    overflowY: 'auto',
    fontFamily: 'monospace',
    margin: 0
  }}>
    {renderValue(output)}
  </pre>
);

export const RunDetailDrawer: React.FC<RunDetailDrawerProps> = ({ runId, kind = 'generation', onClose }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const request = kind === 'translation' ? fetchTranslationDetails(runId) : fetchRunDetails(runId);
    request
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [runId, kind]);

  if (kind === 'translation' && data?.translation) {
    const translation = data.translation;
    return (
      <div className="drawer-overlay" onClick={onClose}>
        <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid #E2E8F0' }}>
            <div><h3 style={{ fontSize: '18px', fontWeight: 700 }}>Translation Details ({runId.substring(0, 8)})</h3><span style={{ fontSize: '12px', color: '#64748B' }}>{data.source?.city}, {data.source?.country} · {translation.target_language}</span></div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}><X size={24} /></button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '24px' }}>
            <div className="metric-card" style={{ padding: '12px' }}><div className="metric-label">Latency</div><div style={{ fontWeight: 700 }}>{(translation.latency_ms / 1000).toFixed(2)}s</div></div>
            <div className="metric-card" style={{ padding: '12px' }}><div className="metric-label">Tokens</div><div style={{ fontWeight: 700 }}>{translation.total_tokens}</div></div>
            <div className="metric-card" style={{ padding: '12px' }}><div className="metric-label">Cost</div><div style={{ fontWeight: 700 }}>${(translation.cost || 0).toFixed(4)}</div></div>
          </div>
          <p style={{ fontSize: '13px' }}><strong>Model:</strong> {translation.model_name} · <strong>Status:</strong> {translation.status}</p>
          <h4>Original English</h4><OutputBlock output={translation.source_content} />
          <h4 style={{ marginTop: '20px' }}>Translated Output</h4><OutputBlock output={translation.output_json || translation.error_message} />
        </div>
      </div>
    );
  }

  // v2 batch run shape: { batch, test_run, prompt_config, fields[] }
  // legacy single-generation shape: { generation, test_run, prompt_config, verification_results[] }
  const isBatch = !!(data?.batch || data?.fields?.length > 0);
  const gen = data?.generation || {};
  const tr = data?.test_run || {};
  const pc = data?.prompt_config || {};
  const fields = data?.fields || [];

  // Aggregates: batch runs sum across field jobs; legacy runs carry their own metrics.
  const totalLatency = isBatch
    ? fields.reduce((acc: number, f: any) => acc + (f.latency_ms || 0), 0)
    : (gen.latency_ms || 0);
  const totalTokens = isBatch
    ? fields.reduce((acc: number, f: any) => acc + (f.tokens || 0), 0)
    : (gen.total_tokens || 0);
  const totalCost = isBatch
    ? fields.reduce((acc: number, f: any) => acc + (f.cost || 0), 0)
    : (gen.cost || 0);

  const testRunId = data?.test_run_id || data?.batch?.test_run_id || gen.test_run_id || tr.id || '';

  if (loading) {
    return (
      <div className="drawer-overlay" onClick={onClose}>
        <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
          <div style={{ padding: '32px', color: '#64748B' }}>Loading Run Details...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid #E2E8F0' }}>
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: 700 }}>Run Details ({runId.substring(0, 8)})</h3>
            <span style={{ fontSize: '12px', color: '#64748B' }}>Test Run ID: {testRunId}</span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}>
            <X size={24} />
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '24px' }}>
          <div className="metric-card" style={{ padding: '12px' }}>
            <div className="metric-label">Latency</div>
            <div style={{ fontWeight: 700, fontSize: '16px' }}>{(totalLatency / 1000.0).toFixed(2)}s</div>
          </div>
          <div className="metric-card" style={{ padding: '12px' }}>
            <div className="metric-label">Tokens</div>
            <div style={{ fontWeight: 700, fontSize: '16px' }}>{totalTokens}</div>
          </div>
          <div className="metric-card" style={{ padding: '12px' }}>
            <div className="metric-label">Cost</div>
            <div style={{ fontWeight: 700, fontSize: '16px' }}>${(totalCost || 0).toFixed(4)}</div>
          </div>
        </div>

        <div style={{ marginBottom: '24px' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#334155' }}>Prompt Configuration</h4>
          <div style={{ backgroundColor: '#F8FAFC', padding: '12px', borderRadius: '8px', border: '1px solid #E2E8F0', fontSize: '13px' }}>
            {(tr.city || tr.country) && <div><strong>Location:</strong> {tr.city}, {tr.country}</div>}
            <div><strong>Language:</strong> {tr.language || pc.language || 'English'}</div>
            <div><strong>Tone:</strong> {pc.tone}</div>
            <div><strong>Audience:</strong> {pc.audience}</div>
            <div><strong>Content Length:</strong> {pc.content_length} words</div>
            <div><strong>Banned Keywords:</strong> {JSON.stringify(pc.banned_keywords || [])}</div>
          </div>
        </div>

        <div>
          <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#334155' }}>Verification Breakdown</h4>

          {isBatch ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {fields.map((f: any, fi: number) => {
                const vrs = f.verification_results || f.verification || [];
                const output = f.output ?? f.output_json_fragment;
                return (
                  <div key={fi} style={{ border: '1px solid #E2E8F0', borderRadius: '8px', overflow: 'hidden', background: '#fff' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#F8FAFC', padding: '8px 12px', borderBottom: '1px solid #E2E8F0' }}>
                      <strong style={{ fontSize: '12px' }}>{f.field_key}</strong>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '11px', color: '#64748B' }}>{(f.latency_ms || 0) / 1000}s · {f.tokens || 0} tok · ${(f.cost || 0).toFixed(4)}</span>
                        <span className={`badge badge-${statusBadgeClass(f.status)}`}>{f.status || 'unknown'}</span>
                      </div>
                    </div>
                    <VerificationTable results={vrs} />
                    {output != null && (
                      <div style={{ borderTop: '1px solid #E2E8F0' }}>
                        <OutputBlock output={output} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <>
              <VerificationTable results={data?.verification_results || []} />
              <div style={{ marginTop: '16px' }}>
                <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#334155' }}>Final Output JSON</h4>
                <OutputBlock output={gen.output_json} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
