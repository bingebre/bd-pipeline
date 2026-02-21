/**
 * API client for the BD Pipeline backend (Railway).
 * Uses Next.js rewrites to proxy /api/* to the backend.
 */
const BASE = '/api';

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Dashboard
  getStats: () => request('/dashboard/stats'),

  // Leads
  getLeads: (params = {}) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') query.set(k, String(v));
    });
    return request(`/leads?${query}`);
  },

  getLead: (id) => request(`/leads/${id}`),

  updateLead: (id, data) =>
    request(`/leads/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Scraping
  triggerScrape: () => request('/scrape/run', { method: 'POST' }),
  getScrapeHistory: (limit = 20) => request(`/scrape/history?limit=${limit}`),
};
