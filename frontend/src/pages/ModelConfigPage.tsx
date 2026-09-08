import React, { useEffect, useMemo, useState } from 'react';
import { Check, Loader2, Save, Search, SlidersHorizontal } from 'lucide-react';
import { fetchModelConfig, saveModelConfig } from '../services/api';
import type { ModelConfig } from '../types';

export const ModelConfigPage: React.FC = () => {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    fetchModelConfig()
      .then(setModels)
      .catch((err) => setError(err.message || 'Failed to load available models.'))
      .finally(() => setLoading(false));
  }, []);

  const filteredModels = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return models;
    return models.filter((model) => `${model.name} ${model.id}`.toLowerCase().includes(normalized));
  }, [models, query]);

  const updateModel = (id: string, patch: Partial<ModelConfig>) => {
    setModels((current) => current.map((model) => model.id === id ? { ...model, ...patch } : model));
    setMessage('');
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const saved = await saveModelConfig(models.map((model) => ({
        model_id: model.id,
        generation_enabled: model.generation_enabled,
        translation_enabled: model.translation_enabled,
      })));
      const savedById = new Map(saved.map((model) => [model.id, model]));
      setModels((current) => current.map((model) => savedById.get(model.id) || model));
      setMessage('Model configuration saved for all clients.');
    } catch (err: any) {
      setError(err.message || 'Failed to save model configuration.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="workspace-container"><Loader2 className="animate-spin" color="#2563EB" /></div>;
  }

  return (
    <div className="workspace-container">
      <div className="card" style={{ padding: '24px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '20px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          <div>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <SlidersHorizontal size={20} color="#2563EB" /> Model Configuration
            </div>
            <p style={{ color: '#64748B', fontSize: '13px', marginTop: '6px', maxWidth: '680px' }}>
              Every current OpenRouter model is listed here. New models remain disabled until explicitly enabled for Generation or Translation.
            </p>
          </div>
          <button className="btn-primary" onClick={handleSave} disabled={saving || models.length === 0}>
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
        {message && <div style={{ marginTop: '16px', color: '#047857', background: '#ECFDF5', padding: '10px 12px', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}><Check size={16} />{message}</div>}
        {error && <div style={{ marginTop: '16px', color: '#B91C1C', background: '#FEF2F2', padding: '10px 12px', borderRadius: '8px' }}>{error}</div>}
      </div>

      <div className="card" style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}>
          <strong>{models.length} available models</strong>
          <label style={{ position: 'relative', minWidth: '260px', flex: '0 1 360px' }}>
            <Search size={16} color="#64748B" style={{ position: 'absolute', left: '10px', top: '11px' }} />
            <input className="input-text" style={{ paddingLeft: '34px' }} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by model name or ID" />
          </label>
        </div>

        {models.length === 0 ? (
          <div style={{ padding: '36px 16px', textAlign: 'center', color: '#64748B' }}>No models were returned by OpenRouter.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '720px' }}>
              <thead><tr style={{ borderBottom: '1px solid #E2E8F0', textAlign: 'left' }}><th style={{ padding: '12px 10px' }}>Model</th><th style={{ padding: '12px 10px' }}>Context</th><th style={{ padding: '12px 10px' }}>Generation</th><th style={{ padding: '12px 10px' }}>Translation</th></tr></thead>
              <tbody>{filteredModels.map((model) => <tr key={model.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                <td style={{ padding: '14px 10px' }}><div style={{ fontWeight: 700 }}>{model.name}</div><div style={{ color: '#64748B', fontSize: '12px', marginTop: '3px' }}>{model.id}</div></td>
                <td style={{ padding: '14px 10px', color: '#475569', fontSize: '13px' }}>{model.context_length.toLocaleString()}</td>
                <td style={{ padding: '14px 10px' }}><label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}><input type="checkbox" checked={model.generation_enabled} onChange={(event) => updateModel(model.id, { generation_enabled: event.target.checked })} /> Enabled</label></td>
                <td style={{ padding: '14px 10px' }}><label style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}><input type="checkbox" checked={model.translation_enabled} onChange={(event) => updateModel(model.id, { translation_enabled: event.target.checked })} /> Enabled</label></td>
              </tr>)}</tbody>
            </table>
            {filteredModels.length === 0 && <div style={{ padding: '28px', textAlign: 'center', color: '#64748B' }}>No models match this search.</div>}
          </div>
        )}
      </div>
    </div>
  );
};

export default ModelConfigPage;