'use client';

import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import LeadCard from '../components/LeadCard';
import StatsBar from '../components/StatsBar';
import ServiceChart from '../components/ServiceChart';
import FilterBar from '../components/FilterBar';
import { DEMO_STATS, DEMO_LEADS } from '../lib/demo-data';

export default function Dashboard() {
  const [stats, setStats] = useState(DEMO_STATS);
  const [leads, setLeads] = useState(DEMO_LEADS);
  const [isLive, setIsLive] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [minConfidence, setMinConfidence] = useState(0);
  const [isScraping, setIsScraping] = useState(false);
  const [loading, setLoading] = useState(true);

  // Connect to backend on mount
  useEffect(() => {
    async function init() {
      try {
        const [statsData, leadsData] = await Promise.all([
          api.getStats(),
          api.getLeads({ page_size: 50, sort_by: 'confidence_score', sort_order: 'desc' }),
        ]);
        setStats(statsData);
        setLeads(leadsData.leads);
        setIsLive(true);
      } catch {
        // Backend not available — stay in demo mode
        setIsLive(false);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  const handleStatusChange = useCallback(
    async (leadId, newStatus) => {
      // Optimistic update
      setLeads((prev) => prev.map((l) => (l.id === leadId ? { ...l, status: newStatus } : l)));
      if (isLive) {
        try {
          await api.updateLead(leadId, { status: newStatus });
        } catch (e) {
          console.error('Failed to update lead:', e);
        }
      }
    },
    [isLive]
  );

  const handleScrape = async () => {
    if (!isLive) return;
    setIsScraping(true);
    try {
      await api.triggerScrape();
      const [statsData, leadsData] = await Promise.all([
        api.getStats(),
        api.getLeads({ page_size: 50, sort_by: 'confidence_score', sort_order: 'desc' }),
      ]);
      setStats(statsData);
      setLeads(leadsData.leads);
    } catch (e) {
      console.error('Scrape failed:', e);
    } finally {
      setIsScraping(false);
    }
  };

  // Client-side filtering
  const filtered = leads.filter((l) => {
    if (statusFilter !== 'all' && l.status !== statusFilter) return false;
    if (minConfidence > 0 && (l.confidence_score || 0) < minConfidence / 100) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const fields = [l.title, l.org_name, l.summary || ''].join(' ').toLowerCase();
      return fields.includes(q);
    }
    return true;
  });

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-cc-charcoal text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-cc-green flex items-center justify-center text-sm">⚡</div>
            <div>
              <h1 className="text-base font-semibold tracking-tight font-serif">BD Pipeline</h1>
              <p className="text-xs text-gray-400">Citizen Codex · Filter 1: Broad Market Scan</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div
              className={`text-xs px-2.5 py-1 rounded-full ${
                isLive ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
              }`}
            >
              {isLive ? '● Live' : '○ Demo Mode'}
            </div>
            {isLive && (
              <button
                onClick={handleScrape}
                disabled={isScraping}
                className="text-xs px-3 py-1.5 rounded-lg bg-cc-green text-white hover:bg-cc-green-light transition-colors disabled:opacity-50"
              >
                {isScraping ? '⟳ Scanning...' : '↻ Run Scan'}
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* Stats */}
        <StatsBar stats={stats} />

        {/* Charts */}
        <ServiceChart stats={stats} />

        {/* Filters */}
        <FilterBar
          statusFilter={statusFilter}
          onStatusChange={setStatusFilter}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          minConfidence={minConfidence}
          onConfidenceChange={setMinConfidence}
        />

        {/* Lead List */}
        <div className="text-sm font-semibold text-gray-500 mb-3">
          {filtered.length} lead{filtered.length !== 1 ? 's' : ''}
        </div>
        <div className="space-y-3">
          {filtered.map((lead) => (
            <LeadCard
              key={lead.id}
              lead={lead}
              isExpanded={expandedId === lead.id}
              onToggle={() => setExpandedId(expandedId === lead.id ? null : lead.id)}
              onStatusChange={handleStatusChange}
            />
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-12 text-gray-400 text-sm">No leads match your filters.</div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="max-w-7xl mx-auto px-4 sm:px-6 py-6 mt-8 border-t border-gray-200">
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>Citizen Codex BD Pipeline v0.1</span>
          <span>Sources: PND · RFPMart · Grants.gov · ProPublica</span>
        </div>
      </footer>
    </div>
  );
}
