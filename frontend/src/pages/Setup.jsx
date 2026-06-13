import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { IS_DESKTOP } from '../api'
import Icon from '../components/Icon'

const REQUIRED_MODELS = [
  { name: 'llama3.2:3b', role: 'Reasoning model (CEO Agent, agents)', size: '~2 GB' },
  { name: 'nomic-embed-text', role: 'Embeddings (Second Brain search)', size: '~280 MB' },
]
const OPTIONAL_MODELS = [
  { name: 'qwen2.5:7b', role: 'Higher-quality reasoning (slower)', size: '~4.7 GB' },
]

export default function Setup() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [step, setStep] = useState(Number(params.get('step')) || 0)
  const h = typeof window !== 'undefined' ? window.hermus : null

  const finish = async () => { if (h?.markOnboarded) await h.markOnboarded(); nav('/login') }

  const steps = [
    { id: 'welcome', title: 'Welcome', icon: 'sparkles' },
    { id: 'system', title: 'Your machine', icon: 'cpu' },
    { id: 'runtime', title: 'Local AI runtime', icon: 'zap' },
    { id: 'models', title: 'AI models', icon: 'brain' },
    { id: 'core', title: 'Core service', icon: 'shield' },
    { id: 'done', title: 'Ready', icon: 'check' },
  ]

  return (
    <div className="auth-wrap" style={{ alignItems: 'flex-start', paddingTop: 40 }}>
      <div style={{ width: '100%', maxWidth: 760 }}>
        <div className="brand" style={{ justifyContent: 'center', marginBottom: 8 }}>
          <div className="logo" /><h1>HERMUS Setup</h1>
        </div>
        <p className="tagline" style={{ textAlign: 'center' }}>
          Let's get your private AI workforce running locally on this machine.</p>

        <div className="flex" style={{ justifyContent: 'center', gap: 6, marginBottom: 20, flexWrap: 'wrap' }}>
          {steps.map((s, i) => (
            <div key={s.id} className="flex" style={{ gap: 6, opacity: i <= step ? 1 : 0.4 }}>
              <span className="stat-ico" style={{ width: 30, height: 30, borderRadius: 9,
                background: i < step ? 'linear-gradient(135deg,#10b981,#34d399)' : 'var(--grad)' }}>
                <Icon name={i < step ? 'check' : s.icon} size={15} /></span>
              {i < steps.length - 1 && <span className="muted">·</span>}
            </div>
          ))}
        </div>

        <div className="card">
          {step === 0 && <Welcome desktop={IS_DESKTOP} />}
          {step === 1 && <SystemStep h={h} />}
          {step === 2 && <RuntimeStep h={h} />}
          {step === 3 && <ModelsStep h={h} />}
          {step === 4 && <CoreStep h={h} />}
          {step === 5 && <DoneStep />}

          <div className="between mt" style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <button className="btn ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
            {step < steps.length - 1
              ? <button className="btn" onClick={() => setStep(step + 1)}>Continue</button>
              : <button className="btn green" onClick={finish}><Icon name="check" size={16} /> Enter HERMUS</button>}
          </div>
        </div>
      </div>
    </div>
  )
}

function Welcome({ desktop }) {
  return (
    <>
      <h3><Icon name="sparkles" size={18} /> Run an entire AI company on your own machine</h3>
      <p className="muted">HERMUS installs a private AI workforce that runs <strong>100% locally</strong> using
        open local LLMs — your business data never leaves this computer. This wizard checks the few
        dependencies you need and helps you install them.</p>
      <ul style={{ fontSize: 14, lineHeight: 2 }}>
        <li><strong>Ollama</strong> — the local AI runtime that runs the models</li>
        <li><strong>AI models</strong> — a small reasoning model + an embeddings model</li>
        <li><strong>HERMUS core service</strong> — your local agents, tasks & memory</li>
      </ul>
      {!desktop && <div className="error-box" style={{ background: 'var(--grad-soft)', color: 'var(--text)', borderColor: 'transparent' }}>
        You're viewing this in a browser. The full local experience runs in the <strong>HERMUS desktop app</strong> —
        but you can preview the wizard here.</div>}
    </>
  )
}

function SystemStep({ h }) {
  const [sys, setSys] = useState(null)
  useEffect(() => { h?.systemInfo ? h.systemInfo().then(setSys) : setSys(null) }, [])
  const tier = sys ? (sys.ramGB >= 16 ? 'Great — you can run 7B–14B models' :
    sys.ramGB >= 8 ? 'Good — small/medium models recommended' : 'Limited — use the smallest models') : ''
  return (
    <>
      <h3><Icon name="cpu" size={18} /> Hardware check</h3>
      {!sys && <p className="muted">Hardware detection runs in the desktop app. (Browser preview.)</p>}
      {sys && <div className="grid cols-2" style={{ gap: 10 }}>
        <Row k="Platform" v={`${sys.platform} (${sys.arch})`} />
        <Row k="CPU" v={`${sys.cpus} cores`} />
        <Row k="Memory" v={`${sys.ramGB} GB (${sys.freeGB} GB free)`} />
        <Row k="Recommendation" v={tier} />
      </div>}
    </>
  )
}

function RuntimeStep({ h }) {
  const [st, setSt] = useState(null)
  const [installing, setInstalling] = useState(false)
  const [log, setLog] = useState('')
  const [result, setResult] = useState(null)
  const check = () => h?.ollamaStatus ? h.ollamaStatus().then(setSt) : setSt({ online: false, web: true })
  useEffect(() => { check() }, [])
  const open = (url) => h?.openExternal ? h.openExternal(url) : window.open(url, '_blank')

  const install = () => {
    if (!h?.installOllama) { open('https://ollama.com/download'); return }
    setInstalling(true); setResult(null); setLog('Starting…')
    h.installOllama(
      (line) => setLog(line),
      (res) => { setInstalling(false); setResult(res); check() })
  }

  return (
    <>
      <h3><Icon name="zap" size={18} /> Local AI runtime — Ollama</h3>
      {st?.online ? (
        <div className="card" style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)' }}>
          <strong style={{ color: 'var(--success-fg)' }}>✓ Ollama is installed and running.</strong>
          <div className="muted mt" style={{ fontSize: 13 }}>{(st.models || []).length} model(s) installed.</div>
        </div>
      ) : (
        <>
          <p className="muted">Ollama runs the AI models privately on your machine. HERMUS can install it for you — one click.</p>
          <div className="row-actions">
            <button className="btn" disabled={installing} onClick={install}>
              <Icon name="download" size={15} /> {installing ? 'Installing…' : 'Install Ollama for me'}</button>
            <button className="btn secondary" disabled={installing} onClick={check}><Icon name="zap" size={15} /> Recheck</button>
          </div>
          {(installing || log) && <div className="card mt" style={{ background: 'var(--panel-2)', boxShadow: 'none' }}>
            <div className="cite" style={{ fontSize: 12, fontFamily: 'monospace', wordBreak: 'break-all' }}>
              {installing && <Icon name="zap" size={12} />} {log}</div></div>}
          {result && <div className="card mt" style={{ background: result.ok ? 'var(--success-bg)' : 'var(--danger-bg)',
            border: `1px solid ${result.ok ? 'var(--success-border)' : 'var(--danger-border)'}` }}>
            <strong style={{ color: result.ok ? 'var(--success-fg)' : 'var(--danger-fg)' }}>
              {result.ok ? '✓ ' : '✕ '}{result.message}</strong></div>}
          <div className="muted mt" style={{ fontSize: 12 }}>Prefer to do it yourself? Install from{' '}
            <a onClick={() => open('https://ollama.com/download')} style={{ cursor: 'pointer' }}>ollama.com/download</a> and click Recheck.</div>
        </>
      )}
    </>
  )
}

function ModelsStep({ h }) {
  const [installed, setInstalled] = useState([])
  const [logs, setLogs] = useState({})
  const [pulling, setPulling] = useState({})
  const refresh = () => h?.ollamaStatus ? h.ollamaStatus().then((s) => setInstalled(s.models || [])) : null
  useEffect(() => { refresh() }, [])

  const has = (n) => installed.some((m) => m === n || m.startsWith(n.split(':')[0]))
  const pull = (name) => {
    if (!h?.pullModel) { window.open('https://ollama.com/library', '_blank'); return }
    setPulling((p) => ({ ...p, [name]: true }))
    h.pullModel(name,
      (line) => setLogs((l) => ({ ...l, [name]: line.trim().slice(-90) })),
      (res) => { setPulling((p) => ({ ...p, [name]: false })); refresh() })
  }

  const ModelRow = ({ m, required }) => (
    <div className="between" style={{ padding: '11px 0', borderBottom: '1px solid var(--border)' }}>
      <div>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{m.name} {required && <span className="tag">required</span>}</div>
        <div className="muted" style={{ fontSize: 12 }}>{m.role} · {m.size}</div>
        {pulling[m.name] && <div className="cite" style={{ fontSize: 11 }}>downloading… {logs[m.name]}</div>}
      </div>
      {has(m.name)
        ? <span className="pill st-completed"><span className="dot" /> installed</span>
        : <button className="btn sm" disabled={pulling[m.name]} onClick={() => pull(m.name)}>
            <Icon name="download" size={14} /> {pulling[m.name] ? 'Pulling…' : 'Download'}</button>}
    </div>
  )
  return (
    <>
      <h3><Icon name="brain" size={18} /> AI models</h3>
      <p className="muted">Download the models HERMUS needs. They run locally — no cloud, no API keys.</p>
      {REQUIRED_MODELS.map((m) => <ModelRow key={m.name} m={m} required />)}
      <h4>Optional</h4>
      {OPTIONAL_MODELS.map((m) => <ModelRow key={m.name} m={m} />)}
      <button className="btn ghost sm mt" onClick={refresh}>Refresh</button>
    </>
  )
}

function CoreStep({ h }) {
  const [ok, setOk] = useState(null)
  const check = () => h?.backendStatus ? h.backendStatus().then(setOk)
    : fetch('/api/v1/health').then((r) => setOk(r.ok)).catch(() => setOk(false))
  useEffect(() => { check() }, [])
  return (
    <>
      <h3><Icon name="shield" size={18} /> HERMUS core service</h3>
      <p className="muted">This is the local engine running your agents, tasks, pipelines and memory.</p>
      <div className="card" style={{ background: ok ? 'var(--success-bg)' : 'var(--danger-bg)',
        border: `1px solid ${ok ? 'var(--success-border)' : 'var(--danger-border)'}` }}>
        <strong style={{ color: ok ? 'var(--success-fg)' : 'var(--danger-fg)' }}>
          {ok === null ? 'Checking…' : ok ? '✓ Core service is running locally' : '✕ Core service not reachable'}</strong>
      </div>
      {ok === false && <button className="btn secondary mt" onClick={check}>Recheck</button>}
    </>
  )
}

function DoneStep() {
  return (
    <>
      <h3><Icon name="check" size={18} /> You're all set</h3>
      <p className="muted">Everything runs on this machine. When you sign in, HERMUS greets you with a quick
        <strong> product tour</strong>, then <strong>Guided Setup</strong> walks you through building your AI
        company — no manuals, no guesswork.</p>
      <ul style={{ fontSize: 14, lineHeight: 2 }}>
        <li>🚀 <strong>Guided Setup</strong> picks your industry, hires your AI team & switches on automations</li>
        <li>🎙️ Press <strong>Ctrl/Cmd + Shift + Space</strong> anytime to talk to HERMUS</li>
        <li>❓ Tap the <strong>tour button</strong> in the top bar to revisit the walkthrough anytime</li>
      </ul>
    </>
  )
}

function Row({ k, v }) {
  return <div className="card" style={{ background: 'var(--panel-2)', boxShadow: 'none', padding: 12 }}>
    <div className="muted" style={{ fontSize: 12 }}>{k}</div>
    <div style={{ fontWeight: 600 }}>{v}</div></div>
}
