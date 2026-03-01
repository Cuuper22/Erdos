import { useState, useRef, useEffect, useMemo } from 'react'

interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success' | 'debug'
  message: string
}

interface LogViewerProps {
  logs: LogEntry[]
}

type LevelFilter = 'all' | 'info' | 'warning' | 'error' | 'success' | 'debug'

function LogViewer({ logs }: LogViewerProps) {
  const logEndRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [search, setSearch] = useState('')
  const [levelFilter, setLevelFilter] = useState<LevelFilter>('all')

  useEffect(() => {
    if (autoScroll) {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      if (levelFilter !== 'all' && log.level !== levelFilter) return false
      if (search && !log.message.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [logs, levelFilter, search])

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const levelCounts = useMemo(() => {
    const counts: Record<string, number> = { info: 0, warning: 0, error: 0, success: 0, debug: 0 }
    logs.forEach(l => { counts[l.level] = (counts[l.level] || 0) + 1 })
    return counts
  }, [logs])

  return (
    <div className="log-viewer">
      <div className="log-header">
        <div className="log-header-top">
          <span>Live Logs ({filteredLogs.length}/{logs.length})</span>
          <label className="auto-scroll-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            Auto-scroll
          </label>
        </div>
        <div className="log-filters">
          <input
            type="text"
            className="log-search"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="level-filters">
            <button
              className={`level-btn ${levelFilter === 'all' ? 'active' : ''}`}
              onClick={() => setLevelFilter('all')}
            >
              All
            </button>
            {(['error', 'warning', 'success', 'info', 'debug'] as LevelFilter[]).map(level => (
              <button
                key={level}
                className={`level-btn level-${level} ${levelFilter === level ? 'active' : ''}`}
                onClick={() => setLevelFilter(level)}
              >
                {level} ({levelCounts[level] || 0})
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="log-content">
        {filteredLogs.length === 0 ? (
          <div className="empty-state">
            <p>{logs.length === 0 ? 'No logs yet. Start mining to see activity.' : 'No logs match your filters.'}</p>
          </div>
        ) : (
          filteredLogs.map((log, index) => (
            <div key={index} className={`log-entry ${log.level}`}>
              <span className="timestamp">[{formatTimestamp(log.timestamp)}]</span>
              <span className={`level-badge ${log.level}`}>{log.level.toUpperCase()}</span>
              <span className="message">{log.message}</span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  )
}

export default LogViewer
