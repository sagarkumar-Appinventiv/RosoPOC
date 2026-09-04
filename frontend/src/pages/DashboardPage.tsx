import React, { useState, useEffect } from 'react';
import { fetchDashboardStats } from '../services/api';
import { Calendar, ArrowRight, Activity, CheckCircle2, RefreshCw, Clock, Cpu, DollarSign, Eye } from 'lucide-react';
import { RunDetailDrawer } from '../components/RunDetailDrawer';

export const DashboardPage: React.FC<{ onNavigateToHistory?: () => void }> = ({ onNavigateToHistory }) => {
  const [stats, setStats] = useState<any>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('All');

  useEffect(() => {
    fetchDashboardStats()
      .then((data) => setStats(data))
      .catch((e) => console.error(e));
  }, []);

  const runsList = stats?.recent_runs || [];

  const filteredRuns = statusFilter === 'All'
    ? runsList
    : runsList.filter((r: any) => (r.status || '').toLowerCase() === statusFilter.toLowerCase());

  return (
    <div className="workspace-container">
      {/* Header bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#0F172A', letterSpacing: '-0.3px' }}>Dashboard Overview</h2>
          <p style={{ fontSize: '13px', color: '#64748B' }}>Monitor execution metrics and recent model content generation runs</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: '#FFFFFF', border: '1px solid #E2E8F0', padding: '8px 16px', borderRadius: '8px', fontSize: '13px', color: '#334155', boxShadow: 'var(--shadow-sm)' }}>
          <Calendar size={15} color="#2563EB" />
          <span style={{ fontWeight: 600 }}>Live Session</span>
        </div>
      </div>

      {/* 6 KPI Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <div style={{ backgroundColor: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Total Runs</span>
            <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: '#EFF6FF', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#2563EB' }}>
              <Activity size={16} />
            </div>
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>{stats?.total_runs ?? 0}</div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#10B981' }}>Live Logged Runs</div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Successful Runs</span>
            <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: '#ECFDF5', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10B981' }}>
              <CheckCircle2 size={16} />
            </div>
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>{stats?.successful_runs ?? 0}</div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#10B981' }}>Verified + Regenerated</div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Regenerated Runs</span>
            <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: '#FFFBEB', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#D97706' }}>
              <RefreshCw size={16} />
            </div>
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>{stats?.regenerated_runs ?? 0}</div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#D97706' }}>Targeted Fix Attempts</div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Avg. Latency</span>
            <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: '#F3E8FF', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8B5CF6' }}>
              <Clock size={16} />
            </div>
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>{stats?.avg_latency_sec ?? '0.00'}s</div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#8B5CF6' }}>Avg Model Speed</div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Total Tokens</span>
            <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: '#E0F2FE', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0284C7' }}>
              <Cpu size={16} />
            </div>
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>{stats?.total_tokens ?? 0}</div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#0284C7' }}>Consumed Tokens</div>
        </div>

        <div style={{ backgroundColor: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '12px', padding: '18px', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>Total Cost</span>
            <div style={{ width: '28px', height: '28px', borderRadius: '6px', backgroundColor: '#DCFCE7', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#16A34A' }}>
              <DollarSign size={16} />
            </div>
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: '#0F172A', marginBottom: '4px' }}>${(stats?.total_cost ?? 0).toFixed(4)}</div>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#16A34A' }}>OpenRouter Spend</div>
        </div>
      </div>

      {/* Recent Runs Table */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <div>
            <span style={{ fontSize: '15px', fontWeight: 800 }}>Recent Runs</span>
            <span style={{ fontSize: '12px', color: '#64748B', marginLeft: '12px' }}>Showing latest model execution records</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '4px', backgroundColor: '#F1F5F9', padding: '3px', borderRadius: '8px' }}>
              {['All', 'Verified', 'Regenerated', 'Failed'].map((st) => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: '6px',
                    border: 'none',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    backgroundColor: statusFilter === st ? '#FFFFFF' : 'transparent',
                    color: statusFilter === st ? '#2563EB' : '#64748B',
                    boxShadow: statusFilter === st ? 'var(--shadow-sm)' : 'none',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {st}
                </button>
              ))}
            </div>
            {onNavigateToHistory && (
              <button
                className="btn-secondary"
                onClick={onNavigateToHistory}
                style={{ fontSize: '12px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
              >
                <span>View Full History</span>
                <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Country / City</th>
                <th>Model</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Latency</th>
                <th>Total Tokens</th>
                <th>Cost</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.length > 0 ? (
                filteredRuns.map((r: any, idx: number) => {
                  const runIdStr = r.run_id || r.id || `RUN-${idx + 1}`;
                  return (
                    <tr key={idx}>
                      <td style={{ fontWeight: 700, color: '#2563EB', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                        {runIdStr.length > 12 ? runIdStr.substring(0, 8) : runIdStr}
                      </td>
                      <td>
                        <strong style={{ color: '#0F172A' }}>{r.city || 'Paris'}</strong>, {r.country || 'France'}
                      </td>
                      <td style={{ fontWeight: 600 }}>{r.model || r.model_id}</td>
                      <td>
                        <span className={`badge badge-${(r.status || 'Verified').toLowerCase()}`}>
                          {r.status || 'Verified'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center', fontWeight: 600 }}>{r.attempt_number || r.attempts || 1}</td>
                      <td style={{ fontSize: '13px' }}>{((r.latency_ms || 0) / 1000).toFixed(1)}s</td>
                      <td style={{ fontSize: '13px', fontFamily: 'var(--font-mono)' }}>{r.total_tokens || 0}</td>
                      <td style={{ fontSize: '13px', fontWeight: 700, color: '#16A34A' }}>${(r.cost || 0).toFixed(4)}</td>
                      <td>
                        <button
                          className="btn-secondary"
                          style={{ padding: '4px 10px', fontSize: '11px', color: '#2563EB', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          onClick={() => setSelectedRunId(runIdStr)}
                        >
                          <Eye size={12} /> View
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '32px', color: '#64748B', fontSize: '13px' }}>
                    No generation runs logged yet. Generate content to populate the dashboard!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {selectedRunId && (
        <RunDetailDrawer runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
      )}
    </div>
  );
};
