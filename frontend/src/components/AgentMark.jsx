// Agent mark: a hub node routing to three tool nodes (mirrors the LangGraph agent).
export function AgentMark({ size = 20, active = false, className = '' }) {
  const satellites = [
    [12, 3.5],
    [19.4, 16.25],
    [4.6, 16.25],
  ]
  return (
    <svg
      className={`agent-mark${active ? ' is-active' : ''} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      {satellites.map(([x, y]) => (
        <line key={`l${x}`} x1="12" y1="12" x2={x} y2={y} className="agent-edge" />
      ))}
      <circle cx="12" cy="12" r="3.4" className="agent-hub" />
      {satellites.map(([x, y], index) => (
        <circle
          key={`n${x}`}
          cx={x}
          cy={y}
          r="2.3"
          className="agent-node"
          style={{ animationDelay: `${index * 0.2}s` }}
        />
      ))}
    </svg>
  )
}

export function greeting(date = new Date()) {
  const hour = date.getHours()
  if (hour < 5) return 'Working late'
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}
