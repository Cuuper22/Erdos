import { useState } from 'react'

interface Solution {
  problemId: string
  timestamp: string
  attempts: number
  status: 'success' | 'failed'
  proofPreview?: string
  isElegant?: boolean
}

interface SolutionsGalleryProps {
  solutions: Solution[]
}

function ProofViewer({ proof, onClose }: { proof: string; onClose: () => void }) {
  const highlightLean = (code: string): string => {
    // Basic Lean 4 syntax highlighting via spans
    // SECURITY: Input is HTML-escaped first, then only our own span tags are inserted.
    // The proof text comes from our Rust backend (not user input), and is escaped below.
    const keywords = ['theorem', 'lemma', 'def', 'where', 'by', 'have', 'let', 'in',
      'fun', 'match', 'with', 'if', 'then', 'else', 'sorry', 'exact', 'apply',
      'intro', 'intros', 'rw', 'simp', 'ring', 'omega', 'linarith', 'norm_num',
      'constructor', 'cases', 'induction', 'rcases', 'obtain', 'use', 'refine',
      'calc', 'show', 'suffices', 'at', 'assumption']
    const types = ['Nat', 'Int', 'Bool', 'Prop', 'Type', 'True', 'False', 'List', 'Option']

    // Escape HTML entities first to prevent XSS
    let result = code
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')

    // Comments
    result = result.replace(/(--.*$)/gm, '<span class="hl-comment">$1</span>')

    // Strings
    result = result.replace(/(&quot;(?:[^&]|&(?!quot;))*&quot;)/g, '<span class="hl-string">$1</span>')

    // Keywords (whole word)
    keywords.forEach(kw => {
      result = result.replace(
        new RegExp(`\\b(${kw})\\b`, 'g'),
        '<span class="hl-keyword">$1</span>'
      )
    })

    // Types
    types.forEach(t => {
      result = result.replace(
        new RegExp(`\\b(${t})\\b`, 'g'),
        '<span class="hl-type">$1</span>'
      )
    })

    return result
  }

  const copyToClipboard = () => {
    navigator.clipboard.writeText(proof).catch(() => {
      const ta = document.createElement('textarea')
      ta.value = proof
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    })
  }

  const exportProof = () => {
    const blob = new Blob([proof], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'proof.lean'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="proof-overlay" onClick={onClose}>
      <div className="proof-modal" onClick={(e) => e.stopPropagation()}>
        <div className="proof-modal-header">
          <h3>Proof</h3>
          <div className="proof-actions">
            <button className="btn btn-clear btn-sm" onClick={copyToClipboard}>
              Copy
            </button>
            <button className="btn btn-clear btn-sm" onClick={exportProof}>
              Export .lean
            </button>
            <button className="btn btn-clear btn-sm" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
        <pre
          className="proof-code"
          dangerouslySetInnerHTML={{ __html: highlightLean(proof) }}
        />
      </div>
    </div>
  )
}

function SolutionsGallery({ solutions }: SolutionsGalleryProps) {
  const [viewingProof, setViewingProof] = useState<string | null>(null)

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

  const exportAllAsJson = () => {
    const data = JSON.stringify(successfulSolutions, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'erdos-solutions.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  if (solutions.length === 0) {
    return (
      <div className="empty-state">
        <h3>No Solutions Yet</h3>
        <p>Start mining to discover proof solutions!</p>
      </div>
    )
  }

  return (
    <div className="solutions-container">
      {viewingProof && (
        <ProofViewer proof={viewingProof} onClose={() => setViewingProof(null)} />
      )}

      <div className="solutions-summary">
        <div className="summary-stat">
          <span className="summary-number" style={{ color: 'var(--success)' }}>
            {successfulSolutions.length}
          </span>
          <span className="summary-label">Solved</span>
        </div>
        <div className="summary-stat">
          <span className="summary-number" style={{ color: 'var(--error)' }}>
            {failedAttempts.length}
          </span>
          <span className="summary-label">Failed</span>
        </div>
        <div className="summary-stat">
          <span className="summary-number" style={{ color: 'var(--accent-secondary)' }}>
            {successfulSolutions.filter(s => s.isElegant).length}
          </span>
          <span className="summary-label">Elegant</span>
        </div>
        {successfulSolutions.length > 0 && (
          <button className="btn btn-clear btn-sm" onClick={exportAllAsJson}>
            Export All (JSON)
          </button>
        )}
      </div>

      {successfulSolutions.length > 0 && (
        <>
          <h2 style={{ marginBottom: '1rem', color: 'var(--success)' }}>
            Successful Proofs ({successfulSolutions.length})
          </h2>
          <div className="solutions-gallery">
            {successfulSolutions.map((solution, index) => (
              <div key={index} className={`solution-card ${solution.isElegant ? 'elegant' : ''}`}>
                <div className="card-header">
                  <h4>{solution.problemId}</h4>
                  {solution.isElegant && <span className="elegant-badge">Elegant</span>}
                </div>
                <div className="meta">
                  <p>{formatDate(solution.timestamp)}</p>
                  <p>{solution.attempts} attempt{solution.attempts !== 1 ? 's' : ''}</p>
                </div>
                {solution.proofPreview && (
                  <pre className="proof-preview">{solution.proofPreview.slice(0, 200)}{solution.proofPreview.length > 200 ? '...' : ''}</pre>
                )}
                <div className="actions">
                  {solution.proofPreview && (
                    <button
                      className="btn btn-clear btn-sm"
                      onClick={() => setViewingProof(solution.proofPreview!)}
                    >
                      View Proof
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {failedAttempts.length > 0 && (
        <>
          <h2 style={{ marginTop: '2rem', marginBottom: '1rem', color: 'var(--text-secondary)' }}>
            Failed Attempts ({failedAttempts.length})
          </h2>
          <div className="solutions-gallery">
            {failedAttempts.map((solution, index) => (
              <div key={index} className="solution-card failed">
                <h4>{solution.problemId}</h4>
                <div className="meta">
                  <p>{formatDate(solution.timestamp)}</p>
                  <p>{solution.attempts} attempt{solution.attempts !== 1 ? 's' : ''}</p>
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
