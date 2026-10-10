export function DashboardSkeleton() {
  return (
    <div className="dashboard-skeleton" aria-hidden="true">
      <div className="overview-grid">
        {[0, 1].map((i) => (
          <div className="skeleton-overview" key={i}>
            <span className="skeleton-line skeleton-short" />
            <span className="skeleton-line skeleton-title" />
            <span className="skeleton-line" />
            <div className="skeleton-values">
              {[0, 1, 2].map((j) => (
                <span className="skeleton-line" key={j} />
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="stat-grid stat-grid-strip">
        {[0, 1, 2, 3].map((i) => (
          <div className="skeleton-stat" key={i}>
            <span className="skeleton-line skeleton-short" />
            <span className="skeleton-line skeleton-title" />
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        {[0, 1].map((i) => (
          <div className="skeleton-panel" key={i} />
        ))}
      </div>
    </div>
  )
}
