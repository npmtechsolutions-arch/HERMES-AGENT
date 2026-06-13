import { useEffect, useRef, useState } from 'react'
import { api, IS_DESKTOP } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// The local models that power the agents ("the Hermes agent brains").
const HERMES_MODELS = [
  { name: 'llama3.2:3b', role: 'Fast reasoning — every agent, day to day', size: '~2 GB', required: true },
  { name: 'nomic-embed-text', role: 'Embeddings — Second Brain search & memory', size: '~280 MB', required: true },
  { name: 'qwen2.5:7b', role: 'Deeper reasoning (CEO Agent, planning)', size: '~4.7 GB', required: false },
]

export default function Runtime() {
  const [models, setModels] = useState(null)
  const [busy, setBusy] = useState(null)        // operation key in progress
  const [logLine, setLogLine] = useState('')
  const [msg, setMsg] = useState(null)
  const [purge, setPurge] = useState(false)     // also remove runtime+models on app uninstall
  const h = typeof window !== 'undefined' ? window.hermus : null
  const mounted = useRef(true)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 9000) }
  // In the desktop app, read the REAL local runtime directly (the Ollama server),
  // not the backend — so the list reflects this machine even if the backend/API
  // is offline. The browser preview falls back to the backend's /models.
  const load = async () => {
    try {
      if (h?.ollamaStatus) {
        const s = await h.ollamaStatus()
        setModels({ online: !!s.online, runtime: 'Ollama',
          models: (s.models || []).map((m) => (typeof m === 'string' ? { name: m } : m)) })
      } else {
        setModels(await api.get('/models'))
      }
    } catch { flash('err', 'Could not read the runtime status.') }
  }
  useEffect(() => { load(); return () => { mounted.current = false } }, []) // eslint-disable-line

  const installed = (name) => (models?.models || []).some((m) => m.name === name || m.name.startsWith(name.split(':')[0]))

  // Generic runner for a bridge op that streams progress + finishes.
  const runOp = (key, fn, confirmMsg) => {
    if (!h) { flash('err', 'Installing & removing runs in the HERMUS desktop app.'); return }
    if (confirmMsg && !window.confirm(confirmMsg)) return
    setBusy(key); setLogLine('Starting…')
    fn((line) => mounted.current && setLogLine(line),
       (res) => { if (!mounted.current) return; setBusy(null); flash(res.ok ? 'ok' : 'err', res.message || (res.ok ? 'Done.' : 'Failed.')); load() })
  }

  const installOllama = () => runOp('ollama', (p, d) => h.installOllama(p, d))
  const uninstallOllama = () => runOp('ollama', (p, d) => h.uninstallOllama(p, d),
    'Uninstall the Ollama runtime? Your agents won’t run until it’s reinstalled. (Your downloaded models stay on disk.)')
  const pull = (m) => runOp(m, (p, d) => h.pullModel(m, p, d))
  const remove = (m) => runOp(m, (p, d) => h.removeModel(m, p, d), `Remove the model “${m}”? You can reinstall it anytime.`)
  const uninstallApp = () => runOp('app', (p, d) => h.uninstallApp({ removeRuntime: purge }, p, d),
    `Uninstall HERMUS from this machine?\n\nThis removes the app and its local data${purge ? ', plus the AI runtime and all downloaded models' : ''}. This cannot be undone.`)

  if (!models) return <Loading />
  const online = models.online

  return (
    <>
      <PageHead title="Runtime & Models"
        sub="HERMUS runs a private AI runtime and local models on this machine — the brains of your agents. Install, update or remove them here." />

      {!IS_DESKTOP && <div className="card mb" style={{ borderColor: 'var(--amber)' }}>
        ⚠ You're in the browser. <strong>Installing & uninstalling</strong> the runtime and models happens in the <strong>HERMUS desktop app</strong>. This page still shows live status.</div>}
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}
      {busy && <div className="card mb" style={{ background: 'var(--panel-2)', boxShadow: 'none' }}>
        <div className="cite" style={{ fontSize: 12, fontFamily: 'monospace', wordBreak: 'break-all' }}>
          <Icon name="zap" size={12} /> {logLine}</div></div>}

      {/* Runtime */}
      <div className="card mb">
        <div className="between mb">
          <h3 style={{ margin: 0 }}><Icon name="cpu" size={17} /> Local AI runtime — Ollama</h3>
          <span className={'pill ' + (online ? 'st-online' : 'st-error')}><span className="dot" />
            {online ? `${models.runtime} running` : 'not running'}</span>
        </div>
        <p className="muted" style={{ fontSize: 13 }}>Runs the models locally — no cloud, no API keys, your data never leaves this machine.</p>
        <div className="row-actions">
          {!online && <button className="btn" disabled={busy === 'ollama' || !IS_DESKTOP} onClick={installOllama}>
            <Icon name="download" size={15} /> {busy === 'ollama' ? 'Installing…' : 'Install Ollama'}</button>}
          <button className="btn secondary" disabled={busy === 'ollama'} onClick={load}>Recheck</button>
          {IS_DESKTOP && online && <button className="btn danger" disabled={busy === 'ollama'} onClick={uninstallOllama}>
            Uninstall runtime</button>}
        </div>
      </div>

      {/* Hermes-agent models */}
      <div className="card">
        <h3><Icon name="brain" size={17} /> Hermes agent models</h3>
        <p className="muted" style={{ fontSize: 13 }}>These local models are your agents’ reasoning and memory. The required two are enough to run everything; the optional one improves quality.</p>
        {HERMES_MODELS.map((m) => {
          const have = installed(m.name)
          return (
            <div key={m.name} className="between" style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{m.name}
                  {m.required ? <span className="tag" style={{ marginLeft: 6, fontSize: 10 }}>required</span>
                    : <span className="tag" style={{ marginLeft: 6, fontSize: 10, color: 'var(--muted)' }}>optional</span>}</div>
                <div className="muted" style={{ fontSize: 12 }}>{m.role} · {m.size}</div>
              </div>
              <div className="flex" style={{ gap: 8 }}>
                {have && <span className="pill st-completed"><span className="dot" /> installed</span>}
                {!have && <button className="btn sm" disabled={busy === m.name || !IS_DESKTOP || !online} title={!online ? 'Install Ollama first' : ''}
                  onClick={() => pull(m.name)}><Icon name="download" size={13} /> {busy === m.name ? 'Installing…' : 'Install'}</button>}
                {have && IS_DESKTOP && <button className="btn ghost sm" disabled={busy === m.name} onClick={() => remove(m.name)}>Remove</button>}
              </div>
            </div>
          )
        })}
        {(models.models || []).filter((m) => !HERMES_MODELS.some((h) => m.name.startsWith(h.name.split(':')[0]))).length > 0 && <>
          <h4 className="mt">Other installed models</h4>
          {models.models.filter((m) => !HERMES_MODELS.some((h) => m.name.startsWith(h.name.split(':')[0]))).map((m) => (
            <div key={m.name} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
              <span>{m.name}{m.size ? ` · ${m.size}` : ''}</span>
              {IS_DESKTOP && <button className="btn ghost sm" disabled={busy === m.name} onClick={() => remove(m.name)}>Remove</button>}
            </div>
          ))}
        </>}
      </div>

      {/* Danger zone — uninstall the whole app */}
      {IS_DESKTOP && <div className="card mt" style={{ borderColor: 'var(--red)' }}>
        <h3 style={{ color: 'var(--red)', margin: 0 }}>⚠ Uninstall HERMUS</h3>
        <p className="muted" style={{ fontSize: 13 }}>Removes the HERMUS app and its local data from this machine. On macOS the app moves itself to the Trash; on Windows the uninstaller opens; on Linux you’ll be told the final step.</p>
        <label className="flex" style={{ gap: 8, alignItems: 'center', fontSize: 13, margin: '4px 0 12px' }}>
          <input type="checkbox" checked={purge} onChange={(e) => setPurge(e.target.checked)} />
          Also remove the AI runtime (Ollama) and all downloaded models
        </label>
        <button className="btn danger" disabled={busy === 'app'} onClick={uninstallApp}>
          {busy === 'app' ? 'Uninstalling…' : 'Uninstall HERMUS…'}</button>
      </div>}
    </>
  )
}
