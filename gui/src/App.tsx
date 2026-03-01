import { useState, useEffect, useCallback, useRef } from 'react'
import { invoke } from '@tauri-apps/api/tauri'
import { listen } from '@tauri-apps/api/event'
import SettingsPanel from './components/SettingsPanel'
import LogViewer from './components/LogViewer'
import SolutionsGallery from './components/SolutionsGallery'

interface Settings {
  apiKey: string
  provider: 'openai' | 'anthropic' | 'google' | 'ollama'
  model: string
  maxCost: number
  ollamaUrl: string
}

interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success' | 'debug'
  message: string
}

interface Solution {
  problemId: string
  timestamp: string
  attempts: number
  status: 'success' | 'failed'
  proofPreview?: string
  isElegant?: boolean
}

interface AttemptResult {
  problem_id: string
  attempt: number
  status: string
  message: string
}

interface CostUpdate {
  cost_usd: number
  total_spent_usd: number
  remaining_usd: number
  input_tokens: number
  output_tokens: number
}

interface MiningStatus {
  status: 'started' | 'stopped' | 'crashed' | 'completed'
  message: string
  exit_code: number | null
}

const DEFAULT_SETTINGS: Settings = {
  apiKey: '',
  provider: 'google',
  model: 'gemini-3-flash',
  maxCost: 5.0,
  ollamaUrl: 'http://localhost:11434',
}

function App() {
  const [activeTab, setActiveTab] = useState<'mining' | 'settings' | 'solutions'>('mining')
  const [isRunning, setIsRunning] = useState(false)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [solutions, setSolutions] = useState<Solution[]>([])
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS)
  const [currentCost, setCurrentCost] = useState(0)
  const [totalTokens, setTotalTokens] = useState({ input: 0, output: 0 })
  const [currentProblem, setCurrentProblem] = useState<string | null>(null)
  const [attemptCount, setAttemptCount] = useState(0)
  const [environmentReady, setEnvironmentReady] = useState(false)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load settings and check environment on startup
  useEffect(() => {
    loadSettings()
    checkEnvironment()
  }, [])

  // Event listeners
  useEffect(() => {
    const unlisteners = [
      listen<LogEntry>('log-event', (event) => {
        setLogs(prev => [...prev, event.payload].slice(-500))
      }),
      listen<Solution>('solution-found', (event) => {
        const solution: Solution = {
          problemId: event.payload.problemId || (event.payload as any).problem_id || '',
          timestamp: event.payload.timestamp || new Date().toISOString(),
          attempts: event.payload.attempts || 0,
          status: 'success',
          proofPreview: event.payload.proofPreview || (event.payload as any).proof_preview,
          isElegant: event.payload.isElegant || (event.payload as any).is_elegant,
        }
        setSolutions(prev => [solution, ...prev])
      }),
      listen<CostUpdate>('cost-update', (event) => {
        setCurrentCost(event.payload.total_spent_usd)
        setTotalTokens({ input: event.payload.input_tokens, output: event.payload.output_tokens })
      }),
      listen<AttemptResult>('attempt-result', (event) => {
        setCurrentProblem(event.payload.problem_id)
        setAttemptCount(event.payload.attempt)
        if (event.payload.status === 'failed') {
          const failSolution: Solution = {
            problemId: event.payload.problem_id,
            timestamp: new Date().toISOString(),
            attempts: event.payload.attempt,
            status: 'failed',
          }
          setSolutions(prev => [failSolution, ...prev.filter(s =>
            !(s.problemId === event.payload.problem_id && s.status === 'failed')
          )])
        }
      }),
      listen<MiningStatus>('mining-status', (event) => {
        const { status } = event.payload
        if (status === 'stopped' || status === 'crashed' || status === 'completed') {
          setIsRunning(false)
        }
      }),
    ]

    return () => {
      unlisteners.forEach(p => p.then(fn => fn()))
    }
  }, [])

  // Auto-save settings on change (debounced 1s)
  const handleSettingsChange = useCallback((newSettings: Settings) => {
    setSettings(newSettings)

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
    }
    saveTimerRef.current = setTimeout(() => {
      saveSettings(newSettings)
    }, 1000)
  }, [])

  const loadSettings = async () => {
    try {
      const loaded = await invoke<Settings | null>('load_settings')
      if (loaded) {
        setSettings(loaded)
      }
    } catch (e) {
      console.log('No saved settings found, using defaults')
    }
  }

  const saveSettings = async (s: Settings) => {
    try {
      // Don't persist the API key in the settings file
      const toSave = { ...s, apiKey: '' }
      await invoke('save_settings', { settings: toSave })
    } catch (e) {
      console.error('Failed to save settings:', e)
    }
  }

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
      message,
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
    setCurrentCost(0)
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
        <h1>Erdos Proof Miner</h1>
        <div className="header-stats">
          <span className="stat">
            Cost: ${currentCost.toFixed(4)} / ${settings.maxCost.toFixed(2)}
          </span>
          <span className="stat">
            Solutions: {solutions.filter(s => s.status === 'success').length}
          </span>
          <span className={`status ${environmentReady ? 'ready' : 'not-ready'}`}>
            {environmentReady ? 'Ready' : 'Setup Required'}
          </span>
        </div>
      </header>

      <nav className="tab-nav">
        <button
          className={activeTab === 'mining' ? 'active' : ''}
          onClick={() => setActiveTab('mining')}
        >
          Mining
        </button>
        <button
          className={activeTab === 'settings' ? 'active' : ''}
          onClick={() => setActiveTab('settings')}
        >
          Settings
        </button>
        <button
          className={activeTab === 'solutions' ? 'active' : ''}
          onClick={() => setActiveTab('solutions')}
        >
          Solutions ({solutions.filter(s => s.status === 'success').length})
        </button>
      </nav>

      <main className="main-content">
        {activeTab === 'mining' && (
          <div className="mining-panel">
            <div className="controls">
              {!environmentReady && (
                <button className="btn btn-setup" onClick={setupEnvironment}>
                  Setup Environment
                </button>
              )}
              <button
                className={`btn ${isRunning ? 'btn-stop' : 'btn-start'}`}
                onClick={isRunning ? stopMining : startMining}
                disabled={!environmentReady}
              >
                {isRunning ? 'Stop Mining' : 'Start Mining'}
              </button>
              <button className="btn btn-clear" onClick={clearLogs}>
                Clear Logs
              </button>
            </div>

            {isRunning && (
              <div className="mining-progress">
                <div className="progress-row">
                  <span className="progress-label">Budget</span>
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: `${Math.min((currentCost / settings.maxCost) * 100, 100)}%` }}
                    />
                  </div>
                  <span className="progress-value">
                    ${currentCost.toFixed(4)} / ${settings.maxCost.toFixed(2)}
                  </span>
                </div>
                {currentProblem && (
                  <div className="progress-row">
                    <span className="progress-label">Working on</span>
                    <span className="progress-value current-problem">{currentProblem}</span>
                    <span className="progress-value">Attempt #{attemptCount}</span>
                  </div>
                )}
                <div className="progress-row">
                  <span className="progress-label">Tokens</span>
                  <span className="progress-value">
                    {totalTokens.input.toLocaleString()} in / {totalTokens.output.toLocaleString()} out
                  </span>
                </div>
              </div>
            )}

            <LogViewer logs={logs} />
          </div>
        )}

        {activeTab === 'settings' && (
          <SettingsPanel
            settings={settings}
            onSettingsChange={handleSettingsChange}
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
