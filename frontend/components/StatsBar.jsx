export default function StatsBar({ stats }) {
  const cards = [
    { label: 'Total Leads', value: stats.total_leads },
    { label: 'New This Week', value: stats.leads_this_week },
    { label: 'Qualified', value: stats.qualified_leads },
    { label: 'Avg. Confidence', value: stats.avg_confidence ? `${Math.round(stats.avg_confidence * 100)}%` : '—' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      {cards.map((c, i) => (
        <div key={i} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
          <div className="text-2xl font-bold text-cc-charcoal font-serif">{c.value}</div>
          <div className="text-xs font-medium text-gray-500 mt-0.5">{c.label}</div>
        </div>
      ))}
    </div>
  );
}
