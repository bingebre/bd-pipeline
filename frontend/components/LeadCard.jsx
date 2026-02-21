import { SERVICE_LABELS, SERVICE_COLORS, STATUS_CONFIG } from '../lib/constants';

function ConfidenceMeter({ score }) {
  if (score == null) return <span className="text-xs text-gray-400">—</span>;
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-500' : pct >= 40 ? 'bg-orange-500' : 'bg-red-400';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums" style={{ minWidth: '2rem' }}>{pct}%</span>
    </div>
  );
}

export default function LeadCard({ lead, isExpanded, onToggle, onStatusChange }) {
  const sc = STATUS_CONFIG[lead.status] || STATUS_CONFIG.new;
  const confPct = lead.confidence_score ? Math.round(lead.confidence_score * 100) : null;

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden transition-all hover:shadow-md">
      {/* Collapsed header */}
      <div className="p-4 cursor-pointer" onClick={onToggle}>
        <div className="flex items-start gap-3">
          {/* Confidence badge */}
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-sm flex-shrink-0 ${
              (lead.confidence_score || 0) >= 0.8 ? 'bg-emerald-500' :
              (lead.confidence_score || 0) >= 0.6 ? 'bg-amber-500' : 'bg-gray-400'
            }`}
          >
            {confPct ?? '?'}
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-cc-charcoal leading-tight">{lead.title}</h3>
            <div className="flex items-center gap-1.5 mt-1 flex-wrap text-xs">
              <span className="font-medium text-cc-green">{lead.org_name}</span>
              <span className="text-gray-300">·</span>
              <span className="text-gray-400">{lead.source_name}</span>
              <span className="text-gray-300">·</span>
              <span className={`px-1.5 py-0.5 rounded-full ring-1 ${sc.cls}`}>{sc.label}</span>
            </div>
          </div>

          <span className="text-gray-300 text-lg flex-shrink-0 pt-0.5">{isExpanded ? '−' : '+'}</span>
        </div>
      </div>

      {/* Expanded detail */}
      {isExpanded && (
        <div className="border-t border-gray-100 px-4 pb-4 pt-3 space-y-3">
          {lead.summary && <p className="text-sm text-gray-600 leading-relaxed">{lead.summary}</p>}

          {lead.relevance_reasoning && (
            <div className="text-xs text-gray-500 bg-cc-cream rounded-lg p-2.5 italic">
              &ldquo;{lead.relevance_reasoning}&rdquo;
            </div>
          )}

          {/* Service matches */}
          {lead.service_matches?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Service Match</div>
              <div className="flex flex-wrap gap-1.5">
                {lead.service_matches.map((svc) => (
                  <span key={svc} className={`text-xs px-2 py-0.5 rounded-full font-medium ${SERVICE_COLORS[svc] || 'bg-gray-100 text-gray-600'}`}>
                    {SERVICE_LABELS[svc] || svc}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Intent signals */}
          {lead.intent_signals?.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5">Intent Signals</div>
              <div className="flex flex-wrap gap-1.5">
                {lead.intent_signals.map((sig, i) => (
                  <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-gray-50 text-gray-600 ring-1 ring-gray-200">{sig}</span>
                ))}
              </div>
            </div>
          )}

          {/* Confidence */}
          <div>
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1">Confidence</div>
            <ConfidenceMeter score={lead.confidence_score} />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
            {lead.source_url && lead.source_url !== '#' && (
              <a href={lead.source_url} target="_blank" rel="noopener noreferrer"
                className="text-xs text-cc-green hover:underline">
                View source ↗
              </a>
            )}
            <div className="flex-1" />
            {['new', 'reviewing'].includes(lead.status) && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); onStatusChange(lead.id, 'qualified'); }}
                  className="text-xs px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 hover:bg-emerald-100 font-medium"
                >
                  Qualify
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onStatusChange(lead.id, 'disqualified'); }}
                  className="text-xs px-3 py-1.5 rounded-lg bg-gray-50 text-gray-500 hover:bg-gray-100"
                >
                  Disqualify
                </button>
              </>
            )}
            {lead.status === 'qualified' && (
              <button
                onClick={(e) => { e.stopPropagation(); onStatusChange(lead.id, 'contacted'); }}
                className="text-xs px-3 py-1.5 rounded-lg bg-purple-50 text-purple-700 hover:bg-purple-100 font-medium"
              >
                Mark Contacted
              </button>
            )}
          </div>

          {/* Notes */}
          {lead.notes && (
            <div className="text-xs text-gray-500 bg-yellow-50 rounded-lg p-2.5 border border-yellow-100">
              <span className="font-semibold">Note:</span> {lead.notes}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
