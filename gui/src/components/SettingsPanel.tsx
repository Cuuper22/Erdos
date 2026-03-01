import { useState } from 'react'

interface Settings {
  apiKey: string
  provider: 'openai' | 'anthropic' | 'google' | 'ollama'
  model: string
  maxCost: number
  ollamaUrl: string
}

interface SettingsPanelProps {
  settings: Settings
  onSettingsChange: (settings: Settings) => void
}

const PROVIDER_MODELS: Record<Settings['provider'], string[]> = {
  google: ['gemini-3-flash', 'gemini-3-pro', 'gemini-2.5-flash'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
  anthropic: ['claude-sonnet-4-6', 'claude-haiku-4-5'],
  ollama: ['llama3.3', 'codellama', 'mistral', 'qwen2.5-coder'],
}

const PROVIDER_LABELS: Record<Settings['provider'], string> = {
  google: 'Google (Gemini)',
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  ollama: 'Ollama (Local)',
}

function SettingsPanel({ settings, onSettingsChange }: SettingsPanelProps) {
  const [customModel, setCustomModel] = useState('')
  const [useCustomModel, setUseCustomModel] = useState(false)

  const handleChange = (field: keyof Settings, value: string | number) => {
    const updated = { ...settings, [field]: value }

    // Auto-select first model when switching provider
    if (field === 'provider') {
      const provider = value as Settings['provider']
      updated.model = PROVIDER_MODELS[provider][0]
      setUseCustomModel(false)
    }

    onSettingsChange(updated)
  }

  const handleModelChange = (value: string) => {
    if (value === '__custom__') {
      setUseCustomModel(true)
    } else {
      setUseCustomModel(false)
      handleChange('model', value)
    }
  }

  const handleCustomModelChange = (value: string) => {
    setCustomModel(value)
    handleChange('model', value)
  }

  const providerModels = PROVIDER_MODELS[settings.provider]
  const isCloudProvider = settings.provider !== 'ollama'

  return (
    <div className="settings-panel">
      <div className="settings-group">
        <h3>LLM Provider</h3>

        <div className="form-field">
          <label>Provider</label>
          <select
            value={settings.provider}
            onChange={(e) => handleChange('provider', e.target.value as Settings['provider'])}
          >
            {Object.entries(PROVIDER_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        {isCloudProvider && (
          <div className="form-field">
            <label>API Key</label>
            <input
              type="password"
              value={settings.apiKey}
              onChange={(e) => handleChange('apiKey', e.target.value)}
              placeholder={`Enter your ${PROVIDER_LABELS[settings.provider]} API key`}
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
            value={useCustomModel ? '__custom__' : settings.model}
            onChange={(e) => handleModelChange(e.target.value)}
          >
            {providerModels.map(model => (
              <option key={model} value={model}>{model}</option>
            ))}
            <option value="__custom__">Custom model...</option>
          </select>
        </div>

        {useCustomModel && (
          <div className="form-field">
            <label>Custom Model Name</label>
            <input
              type="text"
              value={customModel}
              onChange={(e) => handleCustomModelChange(e.target.value)}
              placeholder="e.g. my-custom-model"
            />
          </div>
        )}
      </div>

      <div className="settings-group">
        <h3>Budget Control</h3>

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
        <h3>About</h3>
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
