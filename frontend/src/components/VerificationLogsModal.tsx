import React, { useState } from 'react';
import { X, CheckCircle, AlertTriangle, FileText, Code, ShieldCheck } from 'lucide-react';
import type { VerificationResult } from '../types';

interface VerificationLogsModalProps {
  generationId: string;
  verifierModelId: string;
  attemptNumber: number;
  results: VerificationResult[];
  onClose: () => void;
}

export const VerificationLogsModal: React.FC<VerificationLogsModalProps> = ({
  generationId,
  verifierModelId,
  attemptNumber,
  results,
  onClose
}) => {
  const [activeTab, setActiveTab] = useState<'audit' | 'raw'>('audit');

  const fullAuditRecord = {
    audit_event: "QUALITY_VERIFICATION_CHECK",
    generation_id: generationId,
    test_attempt: attemptNumber,
    verifier_model: verifierModelId,
    timestamp: new Date().toISOString(),
    evaluations: results
  };

  return (
    <div className="drawer-overlay" onClick={onClose} style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div
        className="drawer-content"
        onClick={(e) => e.stopPropagation()}
        style={{ width: '720px', height: 'auto', maxHeight: '85vh', borderRadius: '16px', padding: '28px' }}
      >
        {/* Modal Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', paddingBottom: '14px', borderBottom: '1px solid #E2E8F0' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '10px', backgroundColor: '#EFF6FF', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#2563EB' }}>
              <ShieldCheck size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.3px' }}>Complete Verification Logs</h3>
              <span style={{ fontSize: '12px', color: '#64748B' }}>Run ID: {generationId.substring(0, 8)} • Verification Attempt #{attemptNumber}</span>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B', padding: '4px' }}>
            <X size={22} />
          </button>
        </div>

        {/* Audit Metadata Info Box */}
        <div style={{ backgroundColor: '#F8FAFC', padding: '14px 18px', borderRadius: '10px', border: '1px solid #E2E8F0', fontSize: '13px', marginBottom: '20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <div>Verifier Model: <strong>🤖 {verifierModelId}</strong></div>
          <div>Attempt Number: <strong>#{attemptNumber}</strong></div>
          <div>Log Timestamp: <strong>{new Date().toLocaleString()}</strong></div>
          <div>Total Parameters Evaluated: <strong>{results.length} parameters</strong></div>
        </div>

        {/* Tab Switcher Bar */}
        <div style={{ display: 'flex', borderBottom: '1px solid #E2E8F0', marginBottom: '16px' }}>
          <button
            className="btn-secondary"
            style={{ borderRadius: 0, border: 'none', borderBottom: activeTab === 'audit' ? '2px solid #2563EB' : 'none', color: activeTab === 'audit' ? '#2563EB' : '#64748B', fontWeight: activeTab === 'audit' ? 700 : 500 }}
            onClick={() => setActiveTab('audit')}
          >
            <FileText size={14} style={{ display: 'inline', marginRight: '6px' }} /> Parameter Audit Trail
          </button>
          <button
            className="btn-secondary"
            style={{ borderRadius: 0, border: 'none', borderBottom: activeTab === 'raw' ? '2px solid #2563EB' : 'none', color: activeTab === 'raw' ? '#2563EB' : '#64748B', fontWeight: activeTab === 'raw' ? 700 : 500 }}
            onClick={() => setActiveTab('raw')}
          >
            <Code size={14} style={{ display: 'inline', marginRight: '6px' }} /> Raw Log JSON
          </button>
        </div>

        {/* Content Body */}
        {activeTab === 'audit' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', overflowY: 'auto', maxHeight: '48vh' }}>
            {results.map((res, i) => (
              <div
                key={i}
                style={{
                  border: '1px solid',
                  borderColor: res.status === 'PASS' ? '#BBF7D0' : '#FECACA',
                  borderRadius: '10px',
                  padding: '16px',
                  backgroundColor: res.status === 'PASS' ? '#F0FDF4' : '#FEF2F2'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 800, fontSize: '14px', color: '#0F172A' }}>
                    {i + 1}. {res.parameter}
                  </span>
                  <span className={`badge badge-${res.status === 'PASS' ? 'verified' : 'failed'}`}>
                    {res.status === 'PASS' ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
                    {res.status}
                  </span>
                </div>
                <p style={{ fontSize: '13px', color: '#334155', lineHeight: '1.5', marginBottom: '8px' }}>
                  <strong>Evaluation Details:</strong> {res.reason}
                </p>
                {res.affected_fields && res.affected_fields.length > 0 && (
                  <div style={{ fontSize: '12px', color: '#DC2626', fontWeight: 600, backgroundColor: '#FFFFFF', padding: '6px 10px', borderRadius: '6px', border: '1px solid #FCA5A5' }}>
                    Target JSON Keys Affected: {res.affected_fields.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <pre style={{ backgroundColor: '#0F172A', color: '#E2E8F0', padding: '16px', borderRadius: '10px', fontSize: '12px', maxHeight: '48vh', overflowY: 'auto', fontFamily: 'monospace' }}>
            {JSON.stringify(fullAuditRecord, null, 2)}
          </pre>
        )}

        {/* Modal Footer */}
        <div style={{ marginTop: '24px', textAlign: 'right', paddingTop: '16px', borderTop: '1px solid #E2E8F0' }}>
          <button className="btn-primary" onClick={onClose} style={{ padding: '8px 20px', fontSize: '13px' }}>
            Close Audit Logs
          </button>
        </div>
      </div>
    </div>
  );
};
