import { SERVICE_LABELS, SERVICE_COLORS } from '../lib/constants';

export default function ServiceChart({ stats }) {
  const maxSvc = stats.top_services[0]?.count || 1;
  const maxSrc = stats.source_breakdown[0]?.count || 1;

  return (
    <div className="grid md:grid-cols-2 gap-3 mb-6">
      {/* Service matches */}
      <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Top Service Matches
        </h3>
        <div className="space-y-2">
          {stats.top_services.map((s) => (
            <div key={s.service} className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium w-32 text-center ${SERVICE_COLORS[s.service] || 'bg-gray-100'}`}>
                {SERVICE_LABELS[s.service] || s.service}
              </span>
              <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-cc-green rounded-full transition-all" style={{ width: `${(s.count / maxSvc) * 100}%` }} />
              </div>
              <span className="text-xs text-gray-500 tabular-nums w-6 text-right">{s.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Source breakdown */}
      <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Source Breakdown
        </h3>
        <div className="space-y-2">
          {stats.source_breakdown.map((s) => (
            <div key={s.source} className="flex items-center gap-2">
              <span className="text-xs text-gray-600 w-40 truncate">{s.source}</span>
              <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full bg-cc-gold rounded-full transition-all" style={{ width: `${(s.count / maxSrc) * 100}%` }} />
              </div>
              <span className="text-xs text-gray-500 tabular-nums w-6 text-right">{s.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
