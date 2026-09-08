import type { ModelInfo, AppSettings, HistoryRun, RunDetailsPayload } from '../types';

const API_BASE_URL = '/api';
function getAuthHeader() {
  const token = sessionStorage.getItem('roso_session_token') || '9090';
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  };
}

// -----------------------------------------------------------------------
// Tab-level cache (stale-while-revalidate): pages render previously fetched
// data instantly on remount while a fresh request runs in the background.
// Concurrent requests for the same key share one in-flight promise.
// -----------------------------------------------------------------------
const responseCache = new Map<string, { data: any; promise: Promise<any> | null }>();

function cachedFetch<T>(key: string, doFetch: () => Promise<T>): Promise<T> {
  const entry = responseCache.get(key);
  if (entry?.promise) return entry.promise as Promise<T>;
  const promise = doFetch()
    .then((data) => {
      responseCache.set(key, { data, promise: null });
      return data;
    })
    .catch((err) => {
      const e = responseCache.get(key);
      if (e) e.promise = null;
      throw err;
    });
  responseCache.set(key, { data: entry?.data, promise });
  return promise;
}

export function getCachedHistory(): HistoryRun[] | null {
  return responseCache.get('history')?.data ?? null;
}

export function invalidateHistoryCache() {
  responseCache.delete('history');
}

export function getCachedComparisonRuns(testRunId: string): any[] | null {
  return responseCache.get(`comparison-runs:${testRunId}`)?.data ?? null;
}

export function getCachedComparisonLanguages(): string[] | null {
  return responseCache.get('comparison-languages')?.data ?? null;
}

export async function verifyAuth(apiKey: string): Promise<{ success: boolean; token: string }> {
  const res = await fetch(`${API_BASE_URL}/auth/verify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Invalid API key');
  }
  return res.json();
}

export async function fetchModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE_URL}/models`, {
    headers: getAuthHeader()
  });
  if (!res.ok) throw new Error('Failed to fetch models');
  return res.json();
}

export async function generateContent(payload: any) {
  const res = await fetch(`${API_BASE_URL}/content/generate`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Generation failed');
  }
  return res.json();
}

export async function verifyContent(generationId: string) {
  const res = await fetch(`${API_BASE_URL}/content/verify`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify({ generation_id: generationId })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Verification failed');
  }
  return res.json();
}

export async function regenerateContent(generationId: string) {
  const res = await fetch(`${API_BASE_URL}/content/regenerate`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify({ generation_id: generationId })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Regeneration failed');
  }
  return res.json();
}

export async function fetchTestRunUsedModels(testRunId: string): Promise<string[]> {
  if (!testRunId) return [];
  const res = await fetch(`${API_BASE_URL}/test-runs/${testRunId}/models`, {
    headers: getAuthHeader()
  });
  if (!res.ok) return [];
  return res.json();
}

export async function fetchDashboardStats() {
  const res = await fetch(`${API_BASE_URL}/dashboard/stats`, {
    headers: getAuthHeader()
  });
  if (!res.ok) throw new Error('Failed to fetch dashboard metrics');
  return res.json();
}

export async function fetchHistory(): Promise<HistoryRun[]> {
  return cachedFetch('history', async () => {
    const res = await fetch(`${API_BASE_URL}/history`, {
      headers: getAuthHeader()
    });
    if (!res.ok) throw new Error('Failed to fetch history');
    return res.json();
  });
}

export async function fetchRunDetails(runId: string): Promise<RunDetailsPayload> {
  const res = await fetch(`${API_BASE_URL}/history/${runId}`, {
    headers: getAuthHeader()
  });
  if (!res.ok) throw new Error('Failed to fetch run details');
  return res.json();
}

export async function fetchComparisonRuns(testRunId: string): Promise<any[]> {
  return cachedFetch(`comparison-runs:${testRunId}`, async () => {
    const res = await fetch(`${API_BASE_URL}/comparison/${testRunId || 'default'}`, {
      headers: getAuthHeader()
    });
    if (!res.ok) throw new Error('Failed to fetch comparison data');
    return res.json();
  });
}

export async function fetchComparisonLanguages(): Promise<string[]> {
  return cachedFetch('comparison-languages', async () => {
    const res = await fetch(`${API_BASE_URL}/comparison/languages`, {
      headers: getAuthHeader()
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.languages || [];
  });
}

export async function fetchSettings(): Promise<AppSettings> {
  const res = await fetch(`${API_BASE_URL}/settings`, {
    headers: getAuthHeader()
  });
  if (!res.ok) throw new Error('Failed to fetch settings');
  return res.json();
}

export async function updateSettings(settingsData: Partial<AppSettings>): Promise<AppSettings> {
  const res = await fetch(`${API_BASE_URL}/settings`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(settingsData)
  });
  if (!res.ok) throw new Error('Failed to update settings');
  return res.json();
}

export async function fetchFieldSchema() {
  const res = await fetch(`${API_BASE_URL}/fields/schema`, {
    headers: getAuthHeader()
  });
  if (!res.ok) throw new Error('Failed to fetch field schema');
  return res.json();
}

export async function getOrCreateTestRun(payload: any) {
  const res = await fetch(`${API_BASE_URL}/test-runs/get-or-create`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to create test run');
  }
  return res.json();
}

export async function compileBatch(testRunId: string, fieldKeys: string[]) {
  const res = await fetch(`${API_BASE_URL}/content/compile-batch`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify({ test_run_id: testRunId, field_keys: fieldKeys })
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to compile batch prompts');
  }
  return res.json();
}

export async function generateBatch(payload: any) {
  const res = await fetch(`${API_BASE_URL}/content/generate-batch`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to start batch');
  }
  invalidateHistoryCache();
  return res.json();
}

export async function pollBatchStatus(batchId: string) {
  const res = await fetch(`${API_BASE_URL}/content/batch/${batchId}/status`, {
    headers: getAuthHeader()
  });
  if (!res.ok) throw new Error('Failed to fetch batch status');
  return res.json();
}

export async function rerunField(batchId: string, fieldKey: string) {
  const res = await fetch(`${API_BASE_URL}/content/batch/${batchId}/field/${fieldKey}/rerun`, {
    method: 'POST',
    headers: getAuthHeader()
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to re-run field');
  }
  return res.json();
}

export async function regenerateField(batchId: string, fieldKey: string) {
  const res = await fetch(`${API_BASE_URL}/content/batch/${batchId}/field/${fieldKey}/regenerate`, {
    method: 'POST',
    headers: getAuthHeader()
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Failed to regenerate field');
  }
  return res.json();
}
