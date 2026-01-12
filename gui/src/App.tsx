import { useState, useEffect, useCallback } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { listen } from '@tauri-apps/api/event'
import SettingsPanel from './components/SettingsPanel'
import LogViewer from './components/LogViewer'
import SolutionsGallery from './components/SolutionsGallery'

interface Settings {
  apiKey: string
  provider: 'openai' | 'anthropic' | 'ollama'
  model: string
  maxCost: number
  ollamaUrl: string
}

interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success'
  message: string
}

interface Solution {
  problemId: string
  timestamp: string
  attempts: number
  status: 'success' | 'failed'
}

function App() {
  const [activeTab, setActiveTab] = useState<'mining' | 'settings' | 'solutions'>('mining')
  const [isRunning, setIsRunning] = useState(false)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [solutions, setSolutions] = useState<Solution[]>([])
  const [settings, setSettings] = useState<Settings>({
    apiKey: '',
    provider: 'openai',
    model: 'gpt-4',
    maxCost: 5.0,
    ollamaUrl: 'http://localhost:11434'
  })
  const [currentCost, setCurrentCost] = useState(0)
  const [environmentReady, setEnvironmentReady] = useState(false)

  useEffect(() => {
    // Listen for log events from backend
    const unlisten = listen<LogEntry>('log-event', (event) => {
      setLogs(prev => [...prev, event.payload].slice(-500)) // Keep last 500 logs
    })

    // Listen for solution events
    const unlistenSolution = listen<Solution>('solution-found', (event) => {
      setSolutions(prev => [event.payload, ...prev])
    })

    // Listen for cost updates
    const unlistenCost = listen<number>('cost-update', (event) => {
      setCurrentCost(event.payload)
    })

    // Check environment status
    checkEnvironment()

    return () => {
      unlisten.then(fn => fn())
      unlistenSolution.then(fn => fn())
      unlistenCost.then(fn => fn())
    }
  }, [])

  const checkEnvironment = async () => {
    try {
      const ready = await invoke<boolean>('check_environment')
      setEnvironmentReady(ready)
    } catch (e) {
      console.error('Failed to check environment:', e)
      setEnvironmentReady(false)
    }
  }

  const setupEnvironment = async () => {
    addLog('info', 'Setting up Lean environment...')
    try {
      await invoke('setup_environment')
      setEnvironmentReady(true)
      addLog('success', 'Environment setup complete!')
    } catch (e) {
      addLog('error', `Failed to setup environment: ${e}`)
    }
  }

  const addLog = useCallback((level: LogEntry['level'], message: string) => {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message
    }
    setLogs(prev => [...prev, entry].slice(-500))
  }, [])

  const startMining = async () => {
    if (!settings.apiKey && settings.provider !== 'ollama') {
      addLog('error', 'Please configure your API key in Settings')
      return
    }

    if (!environmentReady) {
      addLog('error', 'Please setup the Lean environment first')
      return
    }

    setIsRunning(true)
    addLog('info', 'Starting proof mining...')

    try {
      await invoke('start_mining', { settings })
    } catch (e) {
      addLog('error', `Mining failed: ${e}`)
      setIsRunning(false)
    }
  }

  const stopMining = async () => {
    try {
      await invoke('stop_mining')
      addLog('info', 'Mining stopped')
    } catch (e) {
      addLog('error', `Failed to stop mining: ${e}`)
    }
    setIsRunning(false)
  }

  const clearLogs = () => {
    setLogs([])
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🔢 Erdos Proof Miner</h1>
        <div className="header-stats">
          <span className="stat">
            💰 Cost: ${currentCost.toFixed(2)} / ${settings.maxCost.toFixed(2)}
          </span>
          <span className="stat">
            ✅ Solutions: {solutions.filter(s => s.status === 'success').length}
          </span>
          <span className={`status ${environmentReady ? 'ready' : 'not-ready'}`}>
            {environmentReady ? '🟢 Ready' : '🔴 Setup Required'}
          </span>
        </div>
      </header>

      <nav className="tab-nav">
        <button
          className={activeTab === 'mining' ? 'active' : ''}
          onClick={() => setActiveTab('mining')}
        >
          ⛏️ Mining
        </button>
        <button
          className={activeTab === 'settings' ? 'active' : ''}
          onClick={() => setActiveTab('settings')}
        >
          ⚙️ Settings
        </button>
        <button
          className={activeTab === 'solutions' ? 'active' : ''}
          onClick={() => setActiveTab('solutions')}
        >
          🏆 Solutions ({solutions.filter(s => s.status === 'success').length})
        </button>
      </nav>

      <main className="main-content">
        {activeTab === 'mining' && (
          <div className="mining-panel">
            <div className="controls">
              {!environmentReady && (
                <button className="btn btn-setup" onClick={setupEnvironment}>
                  🔧 Setup Environment
                </button>
              )}
              <button
                className={`btn ${isRunning ? 'btn-stop' : 'btn-start'}`}
                onClick={isRunning ? stopMining : startMining}
                disabled={!environmentReady}
              >
                {isRunning ? '⏹️ Stop Mining' : '▶️ Start Mining'}
              </button>
              <button className="btn btn-clear" onClick={clearLogs}>
                🗑️ Clear Logs
              </button>
            </div>
            <LogViewer logs={logs} />
          </div>
        )}

        {activeTab === 'settings' && (
          <SettingsPanel
            settings={settings}
            onSettingsChange={setSettings}
          />
        )}

        {activeTab === 'solutions' && (
          <SolutionsGallery solutions={solutions} />
        )}
      </main>

      <footer className="app-footer">
        <span>Erdos Proof Mining System v1.0.0</span>
        <span>Trust the Compiler, Verify the Intent</span>
      </footer>
    </div>
  )
}

export default App
