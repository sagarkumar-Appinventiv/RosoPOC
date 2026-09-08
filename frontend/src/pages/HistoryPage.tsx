import React, { useState, useEffect } from 'react';
import { fetchHistory, getCachedHistory, fetchTranslationHistory, getCachedTranslationHistory } from '../services/api';
import type { HistoryRun, TranslationRun } from '../types';
import { Search, Loader2 } from 'lucide-react';
import { RunDetailDrawer } from '../components/RunDetailDrawer';

const normalizeStatus = (s: string) => (s || '').toLowerCase().replace(/_/g, ' ');

export const HistoryPage: React.FC = () => {
  // Seed from the tab-level cache so already-fetched data renders instantly
  // when switching back to this tab, while a refresh runs in the background.
  const cachedHistory = getCachedHistory();
  const cachedTranslations = getCachedTranslationHistory();
  const [viewMode, setViewMode] = useState<'generation' | 'translation'>('generation');
  const [history, setHistory] = useState<HistoryRun[]>(cachedHistory ?? []);
  const [translations, setTranslations] = useState<TranslationRun[]>(cachedTranslations ?? []);
  const [loading, setLoading] = useState(!cachedHistory);
  const [refreshing, setRefreshing] = useState(!!cachedHistory);
  const [searchTerm, setSearchTerm] = useState('');
  const [modelFilter, setModelFilter] = useState('All Models');
  const [statusFilter, setStatusFilter] = useState('All Status');
  const [languageFilter, setLanguageFilter] = useState('All Languages');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedTranslationId, setSelectedTranslationId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchHistory()
      .then((data) => { if (!cancelled) setHistory(data); })
      .catch((e) => console.error(e))
      .finally(() => { if (!cancelled) { setLoading(false); setRefreshing(false); } });
    fetchTranslationHistory().then((data) => { if (!cancelled) setTranslations(data); }).catch((e) => console.error(e));
    return () => { cancelled = true; };
  }, []);

  const uniqueModels = Array.from(new Set((viewMode === 'generation' ? history.map((h) => h.model || h.model_id) : translations.map((t) => t.model_name || t.model_id)))).filter(Boolean);
  const uniqueLanguages = Array.from(new Set(history.map((h) => h.language).filter(Boolean))).sort();

  const filteredHistory = history.filter((run) => {
    const matchesSearch =
      (run.run_id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (run.city || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (run.country || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (run.model || '').toLowerCase().includes(searchTerm.toLowerCase());

    const matchesModel = modelFilter === 'All Models' || run.model === modelFilter || run.model_id === modelFilter;
    
    const matchesStatus = statusFilter === 'All Status' || normalizeStatus(run.status) === normalizeStatus(statusFilter);
    
    const matchesLanguage = languageFilter === 'All Languages' || run.language === languageFilter;
    
    return matchesSearch && matchesModel && matchesStatus && matchesLanguage;
  });
  const translationLanguages = Array.from(new Set(translations.map((run) => run.target_language))).sort();
  const filteredTranslations = translations.filter((run) => {
    const term = searchTerm.toLowerCase();
    return (!term || run.id.toLowerCase().includes(term) || run.model_name.toLowerCase().includes(term) || (run.target_language || '').toLowerCase().includes(term))
      && (modelFilter === 'All Models' || run.model_name === modelFilter || run.model_id === modelFilter)
      && (statusFilter === 'All Status' || normalizeStatus(run.status) === normalizeStatus(statusFilter))
      && (languageFilter === 'All Languages' || run.target_language === languageFilter);
  });
  const displayedCount = viewMode === 'generation' ? filteredHistory.length : filteredTranslations.length;
  const totalCount = viewMode === 'generation' ? history.length : translations.length;

  return (
    <div className="workspace-container">
      <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
        <button className={viewMode === 'generation' ? 'btn-primary' : 'btn-secondary'} onClick={() => setViewMode('generation')}>Generation</button>
        <button className={viewMode === 'translation' ? 'btn-primary' : 'btn-secondary'} onClick={() => setViewMode('translation')}>Translation</button>
      </div>
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

          {/* Language Filter */}
          <select className="select-input" value={languageFilter} onChange={(e) => setLanguageFilter(e.target.value)} style={{ width: '160px' }}>
            <option value="All Languages">All Languages</option>
            {(viewMode === 'generation' ? uniqueLanguages : translationLanguages).map((lang) => (
              <option key={lang} value={lang}>{lang}</option>
            ))}
          </select>

          {/* Status Filter */}
          <select className="select-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: '140px' }}>
            <option value="All Status">All Status</option>
            <option value="Verified">Verified</option>
            <option value="Regenerated">Regenerated</option>
            <option value="Partial Failure">Partial Failure</option>
            <option value="Failed">Failed</option>
          </select>
        </div>
      </div>

      {/* History Data Table */}
      <div className="card">
        {(loading || refreshing) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', background: '#F0F9FF', borderBottom: '1px solid #BAE6FD', color: '#0369A1', fontSize: '12px', fontWeight: 600 }}>
            <Loader2 size={14} className="animate-spin" />
            {loading ? 'Loading history runs...' : 'Refreshing history...'}
          </div>
        )}
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              {viewMode === 'translation' ? <tr>
                <th>Translation ID</th><th>Source Run</th><th>Target Language</th><th>Model</th><th>Status</th><th>Tokens</th><th>Cost</th><th>Date & Time</th><th>Action</th>
              </tr> : <tr>
                <th>Run ID</th>
                <th>Country</th>
                <th>City</th>
                <th>Language</th>
                <th>Model</th>
                <th>Status</th>
                <th>Attempts</th>
                <th>Date & Time</th>
                <th>Action</th>
              </tr>}
            </thead>
            <tbody>
              {viewMode === 'translation' ? (filteredTranslations.length > 0 ? filteredTranslations.map((run) => (
                <tr key={run.id}>
                  <td style={{ fontWeight: 700, color: '#2563EB', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>{run.id.substring(0, 8)}</td>
                  <td>{(run.source_batch_id || run.source_generation_id || '').substring(0, 8)}</td><td>{run.target_language}</td><td>{run.model_name || run.model_id}</td>
                  <td><span className={`badge badge-${run.status.toLowerCase()}`}>{run.status}</span></td><td>{run.total_tokens}</td><td>${(run.cost || 0).toFixed(4)}</td>
                  <td style={{ fontSize: '12px', color: '#64748B' }}>{new Date(run.created_at).toLocaleString()}</td>
                  <td><button className="btn-secondary" style={{ padding: '4px 12px', fontSize: '12px', color: '#2563EB', fontWeight: 700 }} onClick={() => setSelectedTranslationId(run.id)}>View Details</button></td>
                </tr>
              )) : <tr><td colSpan={9} style={{ textAlign: 'center', padding: '32px', color: '#64748B' }}>{translations.length === 0 ? 'No translations generated yet.' : 'No translations match your filters.'}</td></tr>) : filteredHistory.length > 0 ? (
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
                          {run.status || 'Verified'}
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
              ) : loading ? (
                <tr>
                    <td colSpan={9} style={{ textAlign: 'center', padding: '48px', color: '#64748B', fontSize: '13px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
                      <Loader2 size={28} className="animate-spin" color="#2563EB" />
                      Loading history runs...
                    </div>
                  </td>
                </tr>
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
          <div>Showing <strong>{displayedCount}</strong> of <strong>{totalCount}</strong> total logged runs</div>
        </div>
      </div>

      {selectedRunId && (
        <RunDetailDrawer runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
      )}
      {selectedTranslationId && (
        <RunDetailDrawer runId={selectedTranslationId} kind="translation" onClose={() => setSelectedTranslationId(null)} />
      )}
    </div>
  );
};
