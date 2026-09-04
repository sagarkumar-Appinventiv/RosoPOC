import React, { useState, useEffect } from 'react';
import { fetchHistory } from '../services/api';
import type { HistoryRun } from '../types';
import { Search } from 'lucide-react';
import { RunDetailDrawer } from '../components/RunDetailDrawer';

export const HistoryPage: React.FC = () => {
  const [history, setHistory] = useState<HistoryRun[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [modelFilter, setModelFilter] = useState('All Models');
  const [statusFilter, setStatusFilter] = useState('All Status');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  useEffect(() => {
    fetchHistory()
      .then((data) => setHistory(data))
      .catch((e) => console.error(e));
  }, []);

  const uniqueModels = Array.from(new Set(history.map((h) => h.model || h.model_id))).filter(Boolean);

  const filteredHistory = history.filter((run) => {
    const matchesSearch =
      (run.run_id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (run.city || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (run.country || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (run.model || '').toLowerCase().includes(searchTerm.toLowerCase());

    const matchesModel = modelFilter === 'All Models' || run.model === modelFilter || run.model_id === modelFilter;
    const matchesStatus = statusFilter === 'All Status' || (run.status || '').toLowerCase() === statusFilter.toLowerCase();
    return matchesSearch && matchesModel && matchesStatus;
  });

  return (
    <div className="workspace-container">
      {/* Filter Toolbar */}
      <div className="card" style={{ padding: '16px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
          {/* Search Box */}
          <div style={{ position: 'relative', flex: 1, minWidth: '240px' }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
            <input
              type="text"
              className="input-text"
              placeholder="Search by run ID, city, country, model..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ paddingLeft: '36px' }}
            />
          </div>

          {/* Model Filter */}
          <select className="select-input" value={modelFilter} onChange={(e) => setModelFilter(e.target.value)} style={{ width: '180px' }}>
            <option value="All Models">All Models ({history.length})</option>
            {uniqueModels.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>

          {/* Status Filter */}
          <select className="select-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: '140px' }}>
            <option value="All Status">All Status</option>
            <option value="Verified">Verified</option>
            <option value="Regenerated">Regenerated</option>
            <option value="Failed">Failed</option>
          </select>
        </div>
      </div>

      {/* History Data Table */}
      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Country</th>
                <th>City</th>
                <th>Language</th>
                <th>Model</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Date & Time</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.length > 0 ? (
                filteredHistory.map((run, idx) => {
                  const dateStr = run.created_at || run.date;
                  return (
                    <tr key={idx}>
                      <td style={{ fontWeight: 700, color: '#2563EB', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                        {run.run_id ? run.run_id.substring(0, 8) : `RUN-${idx + 1}`}
                      </td>
                      <td>{run.country || 'France'}</td>
                      <td>{run.city || 'Paris'}</td>
                      <td>{run.language || 'English'}</td>
                      <td style={{ fontWeight: 600, color: '#0F172A' }}>{run.model || run.model_id}</td>
                      <td>
                        <span className={`badge badge-${(run.status || 'Verified').toLowerCase()}`}>
                          {run.batch_status || run.status || 'Verified'}
                        </span>
                      </td>
                      <td style={{ textAlign: 'center', fontWeight: 600 }}>
                        {run.fields_passed != null ? `${run.fields_passed}/${run.fields_total} passed` : (run.attempt_number || run.attempts || 1)}
                      </td>
                      <td style={{ fontSize: '12px', color: '#64748B' }}>
                        {dateStr ? new Date(dateStr).toLocaleString() : 'Just now'}
                      </td>
                      <td>
                        <button
                          className="btn-secondary"
                          style={{ padding: '4px 12px', fontSize: '12px', color: '#2563EB', fontWeight: 700 }}
                          onClick={() => setSelectedRunId(run.run_id)}
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '32px', color: '#64748B', fontSize: '13px' }}>
                    {history.length === 0
                      ? "No content generation runs logged yet. Generate content to populate history!"
                      : "No runs match your search filters."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Real Live Runs Counter Footer */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '16px', paddingTop: '14px', borderTop: '1px solid #E2E8F0', fontSize: '13px', color: '#64748B', fontWeight: 600 }}>
          <div>Showing <strong>{filteredHistory.length}</strong> of <strong>{history.length}</strong> total logged runs</div>
        </div>
      </div>

      {selectedRunId && (
        <RunDetailDrawer runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
      )}
    </div>
  );
};
