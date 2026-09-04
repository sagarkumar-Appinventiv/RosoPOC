import React, { useEffect, useState } from 'react';
import { fetchRunDetails } from '../services/api';
import { X } from 'lucide-react';

interface RunDetailDrawerProps {
  runId: string;
  onClose: () => void;
}

export const RunDetailDrawer: React.FC<RunDetailDrawerProps> = ({ runId, onClose }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchRunDetails(runId)
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [runId]);

  if (loading) {
    return (
      <div className="drawer-overlay" onClick={onClose}>
        <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
          <div style={{ padding: '32px', color: '#64748B' }}>Loading Run Details...</div>
        </div>
      </div>
    );
  }

  const gen = data?.generation || {};
  const tr = data?.test_run || {};
  const pc = data?.prompt_config || {};
  const vrs = data?.verification_results || [];

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-content" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid #E2E8F0' }}>
          <div>
            <h3 style={{ fontSize: '18px', fontWeight: 700 }}>Run Details ({runId.substring(0, 8)})</h3>
            <span style={{ fontSize: '12px', color: '#64748B' }}>Test Run ID: {tr.id}</span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}>
            <X size={24} />
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '24px' }}>
          <div className="metric-card" style={{ padding: '12px' }}>
            <div className="metric-label">Latency</div>
            <div style={{ fontWeight: 700, fontSize: '16px' }}>{((gen.latency_ms || 0) / 1000.0).toFixed(2)}s</div>
          </div>
          <div className="metric-card" style={{ padding: '12px' }}>
            <div className="metric-label">Tokens</div>
            <div style={{ fontWeight: 700, fontSize: '16px' }}>{gen.total_tokens || 0}</div>
          </div>
          <div className="metric-card" style={{ padding: '12px' }}>
            <div className="metric-label">Cost</div>
            <div style={{ fontWeight: 700, fontSize: '16px' }}>${(gen.cost || 0).toFixed(4)}</div>
          </div>
        </div>

        <div style={{ marginBottom: '24px' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#334155' }}>Prompt Configuration</h4>
          <div style={{ backgroundColor: '#F8FAFC', padding: '12px', borderRadius: '8px', border: '1px solid #E2E8F0', fontSize: '13px' }}>
            <div><strong>Location:</strong> {tr.city}, {tr.country}</div>
            <div><strong>Language:</strong> {tr.language}</div>
            <div><strong>Tone:</strong> {pc.tone}</div>
            <div><strong>Audience:</strong> {pc.audience}</div>
            <div><strong>Content Length:</strong> {pc.content_length} words</div>
            <div><strong>Banned Keywords:</strong> {JSON.stringify(pc.banned_keywords || [])}</div>
          </div>
        </div>

        <div style={{ marginBottom: '24px' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#334155' }}>Verification Breakdown</h4>
          <table className="data-table">
            <thead>
              <tr>
                <th>Parameter</th>
                <th>Status</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {vrs.map((v: any, i: number) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{v.parameter}</td>
                  <td>
                    <span className={`badge badge-${v.status === 'PASS' ? 'verified' : 'failed'}`}>
                      {v.status}
                    </span>
                  </td>
                  <td style={{ fontSize: '12px', color: '#475569' }}>{v.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <h4 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#334155' }}>Final Output JSON</h4>
          <pre style={{
            backgroundColor: '#0F172A',
            color: '#E2E8F0',
            padding: '16px',
            borderRadius: '8px',
            fontSize: '12px',
            maxHeight: '300px',
            overflowY: 'auto',
            fontFamily: 'monospace'
          }}>
            {JSON.stringify(gen.output_json, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};
