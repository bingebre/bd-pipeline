export default function FilterBar({
  statusFilter, onStatusChange,
  searchQuery, onSearchChange,
  minConfidence, onConfidenceChange,
}) {
  const statuses = ['all', 'new', 'reviewing', 'qualified', 'contacted'];

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-3 shadow-sm mb-4">
      <div className="flex flex-wrap items-center gap-2">
        {/* Search */}
        <input
          type="text"
          placeholder="Search leads..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="flex-1 min-w-48 text-sm pl-3 pr-3 py-1.5 rounded-lg border border-gray-200 focus:outline-none focus:ring-1 focus:ring-cc-green/30 focus:border-cc-green bg-cc-cream/50"
        />

        {/* Status pills */}
        <div className="flex gap-1">
          {statuses.map((s) => (
            <button
              key={s}
              onClick={() => onStatusChange(s)}
              className={`text-xs px-2.5 py-1.5 rounded-lg transition-colors capitalize ${
                statusFilter === s
                  ? 'bg-cc-charcoal text-white'
                  : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Confidence slider */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Min:</span>
          <input
            type="range"
            min="0" max="90" step="10"
            value={minConfidence}
            onChange={(e) => onConfidenceChange(Number(e.target.value))}
            className="w-20 h-1 accent-cc-green"
          />
          <span className="text-xs font-mono text-gray-500 w-8 tabular-nums">{minConfidence}%</span>
        </div>
      </div>
    </div>
  );
}
