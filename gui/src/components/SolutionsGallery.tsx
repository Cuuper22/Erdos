interface Solution {
  problemId: string
  timestamp: string
  attempts: number
  status: 'success' | 'failed'
}

interface SolutionsGalleryProps {
  solutions: Solution[]
}

function SolutionsGallery({ solutions }: SolutionsGalleryProps) {
  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const successfulSolutions = solutions.filter(s => s.status === 'success')
  const failedAttempts = solutions.filter(s => s.status === 'failed')

  if (solutions.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">🏆</div>
        <h3>No Solutions Yet</h3>
        <p>Start mining to discover proof solutions!</p>
      </div>
    )
  }

  return (
    <div>
      {successfulSolutions.length > 0 && (
        <>
          <h2 style={{ marginBottom: '1rem', color: 'var(--success)' }}>
            ✅ Successful Proofs ({successfulSolutions.length})
          </h2>
          <div className="solutions-gallery">
            {successfulSolutions.map((solution, index) => (
              <div key={index} className="solution-card">
                <h4>🎯 {solution.problemId}</h4>
                <div className="meta">
                  <p>📅 {formatDate(solution.timestamp)}</p>
                  <p>🔄 {solution.attempts} attempt{solution.attempts !== 1 ? 's' : ''}</p>
                </div>
                <div className="actions">
                  <button className="btn btn-clear" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
                    📋 View Proof
                  </button>
                  <button className="btn btn-clear" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
                    📤 Export
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {failedAttempts.length > 0 && (
        <>
          <h2 style={{ marginTop: '2rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>
            ❌ Failed Attempts ({failedAttempts.length})
          </h2>
          <div className="solutions-gallery">
            {failedAttempts.map((solution, index) => (
              <div key={index} className="solution-card failed">
                <h4>❌ {solution.problemId}</h4>
                <div className="meta">
                  <p>📅 {formatDate(solution.timestamp)}</p>
                  <p>🔄 {solution.attempts} attempt{solution.attempts !== 1 ? 's' : ''}</p>
                </div>
                <div className="actions">
                  <button className="btn btn-clear" style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
                    📋 View Logs
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export default SolutionsGallery
