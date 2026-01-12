import { useRef, useEffect } from 'react'

interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success'
  message: string
}

interface LogViewerProps {
  logs: LogEntry[]
}

function LogViewer({ logs }: LogViewerProps) {
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Auto-scroll to bottom when new logs arrive
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return (
    <div className="log-viewer">
      <div className="log-header">
        📋 Live Logs ({logs.length} entries)
      </div>
      <div className="log-content">
        {logs.length === 0 ? (
          <div className="empty-state">
            <div className="icon">📝</div>
            <p>No logs yet. Start mining to see activity.</p>
          </div>
        ) : (
          logs.map((log, index) => (
            <div key={index} className={`log-entry ${log.level}`}>
              <span className="timestamp">[{formatTimestamp(log.timestamp)}]</span>
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
