interface Settings {
  apiKey: string
  provider: 'openai' | 'anthropic' | 'ollama'
  model: string
  maxCost: number
  ollamaUrl: string
}

interface SettingsPanelProps {
  settings: Settings
  onSettingsChange: (settings: Settings) => void
}

function SettingsPanel({ settings, onSettingsChange }: SettingsPanelProps) {
  const handleChange = (field: keyof Settings, value: string | number) => {
    onSettingsChange({
      ...settings,
      [field]: value
    })
  }

  const models = {
    openai: ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
    anthropic: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'],
    ollama: ['llama2', 'codellama', 'mistral', 'mixtral']
  }

  return (
    <div className="settings-panel">
      <div className="settings-group">
        <h3>🤖 LLM Provider</h3>
        
        <div className="form-field">
          <label>Provider</label>
          <select
            value={settings.provider}
            onChange={(e) => handleChange('provider', e.target.value as Settings['provider'])}
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="ollama">Ollama (Local)</option>
          </select>
        </div>

        {settings.provider !== 'ollama' && (
          <div className="form-field">
            <label>API Key</label>
            <input
              type="password"
              value={settings.apiKey}
              onChange={(e) => handleChange('apiKey', e.target.value)}
              placeholder={`Enter your ${settings.provider === 'openai' ? 'OpenAI' : 'Anthropic'} API key`}
            />
          </div>
        )}

        {settings.provider === 'ollama' && (
          <div className="form-field">
            <label>Ollama URL</label>
            <input
              type="text"
              value={settings.ollamaUrl}
              onChange={(e) => handleChange('ollamaUrl', e.target.value)}
              placeholder="http://localhost:11434"
            />
          </div>
        )}

        <div className="form-field">
          <label>Model</label>
          <select
            value={settings.model}
            onChange={(e) => handleChange('model', e.target.value)}
          >
            {models[settings.provider].map(model => (
              <option key={model} value={model}>{model}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="settings-group">
        <h3>💰 Budget Control</h3>
        
        <div className="form-field">
          <label>Maximum Cost (USD)</label>
          <input
            type="number"
            min="0.5"
            max="100"
            step="0.5"
            value={settings.maxCost}
            onChange={(e) => handleChange('maxCost', parseFloat(e.target.value))}
          />
          <p style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Mining will automatically stop when this limit is reached.
          </p>
        </div>
      </div>

      <div className="settings-group">
        <h3>ℹ️ About</h3>
        <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          The Erdos Proof Mining System uses AI to help solve formalized mathematical 
          conjectures in Lean 4. Your proofs are validated locally before submission 
          to ensure correctness.
        </p>
        <p style={{ marginTop: '1rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          <strong>Core Philosophy:</strong> "Trust the Compiler, Verify the Intent."
        </p>
      </div>
    </div>
  )
}

export default SettingsPanel
