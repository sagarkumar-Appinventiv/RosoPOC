import React, { useEffect, useState } from 'react';
import { fetchModels, fetchTranslationSources, generateTranslation } from '../services/api';
import type { ModelInfo, TranslationRun, TranslationSource } from '../types';
import { Languages, Loader2, ArrowRight } from 'lucide-react';

const LANGUAGES = ['Spanish', 'French', 'German', 'Italian', 'Portuguese', 'Dutch', 'Russian', 'Polish', 'Swedish', 'Danish', 'Finnish', 'Greek', 'Czech', 'Romanian', 'Hungarian'];

export const TranslationPage: React.FC = () => {
  const [sources, setSources] = useState<TranslationSource[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [sourceId, setSourceId] = useState('');
  const [targetLanguage, setTargetLanguage] = useState('German');
  const [modelId, setModelId] = useState('');
  const [additionalPrompt, setAdditionalPrompt] = useState('');
  const [result, setResult] = useState<TranslationRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [translating, setTranslating] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let sourcesLoaded = false;
    let modelsLoaded = false;
    const finishLoading = () => {
      if (sourcesLoaded && modelsLoaded) setLoading(false);
    };

    fetchTranslationSources()
      .then((sourceData) => {
        setSources(sourceData);
        if (sourceData[0]) setSourceId(sourceData[0].source_batch_id || sourceData[0].source_generation_id || '');
      })
      .catch((e) => setError(e.message || 'Failed to fetch translation sources.'))
      .finally(() => { sourcesLoaded = true; finishLoading(); });

    fetchModels()
      .then((modelData) => {
        if (modelData?.length) {
          setModels(modelData);
          setModelId(modelData[0].id);
        }
      })
      .catch((e) => setError((current) => current || e.message || 'Failed to fetch OpenRouter models.'))
      .finally(() => { modelsLoaded = true; finishLoading(); });
  }, []);

  const source = sources.find((item) => item.source_batch_id === sourceId || item.source_generation_id === sourceId);

  const handleTranslate = async () => {
    if (!source || !modelId) return;
    setTranslating(true);
    setError('');
    try {
      const payload = source.source_batch_id
        ? { source_batch_id: source.source_batch_id, target_language: targetLanguage, model_id: modelId, additional_prompt: additionalPrompt }
        : { source_generation_id: source.source_generation_id || undefined, target_language: targetLanguage, model_id: modelId, additional_prompt: additionalPrompt };
      setResult(await generateTranslation(payload));
    } catch (e: any) {
      setError(e.message || 'Translation failed.');
    } finally {
      setTranslating(false);
    }
  };

  if (loading) return <div className="workspace-container"><Loader2 className="animate-spin" color="#2563EB" /></div>;

  return (
    <div className="workspace-container">
      <div className="card" style={{ padding: '24px', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
          <Languages size={22} color="#2563EB" />
          <h2 style={{ margin: 0, fontSize: '20px' }}>Translate Generated Content</h2>
        </div>
        {error && <div style={{ color: '#B91C1C', background: '#FEF2F2', padding: '10px', marginBottom: '16px' }}>{error}</div>}
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: '16px' }}>
          <label className="form-label">English source
            <select className="select-input" value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
              <option value="">Select completed English output</option>
              {sources.map((item) => {
                const id = item.source_batch_id || item.source_generation_id || '';
                return <option key={id} value={id}>{item.city}, {item.country} · {item.model_name} · {item.source_type} · {new Date(item.created_at).toLocaleDateString()}</option>;
              })}
            </select>
          </label>
          <label className="form-label">Target language
            <select className="select-input" value={targetLanguage} onChange={(e) => setTargetLanguage(e.target.value)}>
              {LANGUAGES.map((language) => <option key={language}>{language}</option>)}
            </select>
          </label>
          <label className="form-label">Model
            <select className="select-input" value={modelId} onChange={(e) => setModelId(e.target.value)}>
              {models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
            </select>
          </label>
        </div>
        <label className="form-label" style={{ display: 'block', marginTop: '16px' }}>Additional instruction
          <textarea className="input-text" rows={3} value={additionalPrompt} onChange={(e) => setAdditionalPrompt(e.target.value)} placeholder="Optional translation instruction" />
        </label>
        <button className="btn-primary" onClick={handleTranslate} disabled={!source || !modelId || translating} style={{ marginTop: '16px' }}>
          {translating ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />} {translating ? 'Translating...' : 'Translate JSON'}
        </button>
      </div>

      {source && <div className="card" style={{ padding: '20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          <div><h3 style={{ fontSize: '15px' }}>Original English</h3><pre style={{ whiteSpace: 'pre-wrap', maxHeight: '500px', overflow: 'auto' }}>{JSON.stringify(source.source_content, null, 2)}</pre></div>
          <div><h3 style={{ fontSize: '15px' }}>Translated output</h3><pre style={{ whiteSpace: 'pre-wrap', maxHeight: '500px', overflow: 'auto' }}>{result ? JSON.stringify(result.output_json, null, 2) : 'Translation output will appear here.'}</pre></div>
        </div>
      </div>}
    </div>
  );
};

export default TranslationPage;