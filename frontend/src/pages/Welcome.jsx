import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, IS_DESKTOP } from '../api'
import Icon from '../components/Icon'

// Overview shown while the local AI brains install — keeps the wait productive.
const SLIDES = [
  { icon: 'sparkles', title: 'Your private AI office', body: 'An entire company of AI agents — a CEO Agent and specialists for your business — running 100% on this machine.' },
  { icon: 'shield', title: 'Private by design', body: 'No cloud, no API keys. Your business data never leaves this computer. The agents think locally.' },
  { icon: 'mic', title: 'Run it by voice', body: 'Hire agents, chain them into workflows, and command the whole office hands-free — “what’s pending?”, “staff my team”.' },
  { icon: 'rocket', title: 'Almost there', body: 'We’re installing the local AI brains now — a one-time download. Then HERMUS guides you through building your company.' },
]
const PLAN = [
  { key: 'runtime', label: 'Local AI runtime (Ollama)', kind: 'ollama' },
  { key: 'llama3.2:3b', label: 'Reasoning model — llama3.2:3b (~2 GB)', kind: 'model' },
  { key: 'nomic-embed-text', label: 'Memory model — nomic-embed-text (~280 MB)', kind: 'model' },
]

export default function Welcome() {
  const nav = useNavigate()
  const h = typeof window !== 'undefined' ? window.hermus : null
  const [slide, setSlide] = useState(0)
  const [status, setStatus] = useState({})       // key -> pending|running|done|fail
  const [prog, setProg] = useState({})            // key -> 0..100
  const [logs, setLogs] = useState([])            // streamed lines
  const [phase, setPhase] = useState('idle')      // idle|installing|done|error
  const [paths, setPaths] = useState(null)
  const logRef = useRef(null)
  const mounted = useRef(true)

  useEffect(() => {
    if (h?.runtimePaths) h.runtimePaths().then(setPaths).catch(() => {})
    const t = setInterval(() => setSlide((s) => (s + 1) % SLIDES.length), 3800)
    return () => { mounted.current = false; clearInterval(t) }
  }, []) // eslint-disable-line
  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [logs])

  const pushLog = (line, key) => {
    if (!mounted.current) return
    const clean = String(line).replace(/\r/g, '\n').split('\n').map((l) => l.trim()).filter(Boolean)
    if (clean.length) setLogs((L) => [...L, ...clean].slice(-200))
    const m = String(line).match(/(\d{1,3})\s?%/)            // parse a percentage if present
    if (m && key) setProg((p) => ({ ...p, [key]: Math.min(100, Number(m[1])) }))
  }

  const done = (to) => { try { localStorage.setItem('hermus_firstrun_done', '1') } catch {} nav(to) }

  const installEverything = async () => {
    if (!h) { done('/guided-setup'); return }
    setPhase('installing'); setLogs(['Starting setup…'])
    const mark = (k, s) => setStatus((x) => ({ ...x, [k]: s }))
    // What's already on this machine — so we skip re-downloading.
    let have = []
    try { const s = h.ollamaStatus ? await h.ollamaStatus() : null; have = (s?.models || []).map((m) => (typeof m === 'string' ? m : m.name)) } catch {}
    const installed = (name) => have.some((n) => n === name || n.startsWith(name.split(':')[0]))
    try {
      for (const step of PLAN) {
        mark(step.key, 'running'); setProg((p) => ({ ...p, [step.key]: 0 }))
        pushLog(`▶ ${step.label}`)
        const ok = await new Promise((resolve) => {
          const onProg = (line) => pushLog(line, step.key)
          const onDone = (r) => { pushLog(r?.message || (r?.ok ? 'done' : 'failed')); resolve(!!(r && r.ok)) }
          if (step.kind === 'ollama') {
            // Live check — if the runtime is already up, this step is instant.
            (h.ollamaStatus ? h.ollamaStatus() : Promise.resolve({ online: false })).then((s) => {
              if (s && s.online) { pushLog('Ollama already running.'); resolve(true) }
              else h.installOllama(onProg, onDone)
            })
          } else if (installed(step.key)) {
            pushLog(`${step.key} already installed.`); resolve(true)
          } else {
            h.pullModel(step.key, onProg, onDone)
          }
        })
        if (!mounted.current) return
        setProg((p) => ({ ...p, [step.key]: 100 }))
        mark(step.key, ok ? 'done' : 'fail')
        if (!ok) { setPhase('error'); pushLog(`✕ Could not finish ${step.label}. Retry, or skip and do it later in Runtime & Models.`); return }
      }
      setPhase('done'); pushLog('✓ Your AI office is ready.')
    } catch (e) { setPhase('error'); pushLog('Install error: ' + (e?.message || e)) }
  }

  const s = SLIDES[slide]
  const completed = PLAN.filter((p) => status[p.key] === 'done').length
  const cur = PLAN.find((p) => status[p.key] === 'running')
  const overall = phase === 'done' ? 100
    : Math.min(99, Math.round((completed + (cur ? (prog[cur.key] || 0) / 100 : 0)) / PLAN.length * 100))

  return (
    <div className="auth-wrap" style={{ alignItems: 'center' }}>
      <div style={{ width: '100%', maxWidth: 860 }}>
        <div className="brand" style={{ justifyContent: 'center', marginBottom: 16 }}>
          <div className="logo" /><h1>HERMUS</h1>
        </div>

        <div className="grid" style={{ gridTemplateColumns: '1fr 1.1fr', gap: 16, alignItems: 'stretch' }}>
          {/* Overview carousel */}
          <div className="card" style={{ background: 'var(--grad)', color: '#fff', border: 'none', minHeight: 320, display: 'flex', flexDirection: 'column' }}>
            <div style={{ flex: 1 }}>
              <div className="stat-ico" style={{ width: 44, height: 44, borderRadius: 12, background: 'rgba(255,255,255,.18)', marginBottom: 14 }}>
                <Icon name={s.icon} size={22} /></div>
              <h2 style={{ color: '#fff', margin: '0 0 8px' }}>{s.title}</h2>
              <p style={{ color: 'rgba(255,255,255,.92)', fontSize: 14, lineHeight: 1.6 }}>{s.body}</p>
            </div>
            <div className="flex" style={{ gap: 6 }}>
              {SLIDES.map((_, i) => <span key={i} onClick={() => setSlide(i)} style={{ cursor: 'pointer',
                width: i === slide ? 22 : 7, height: 7, borderRadius: 7, transition: 'all .3s',
                background: i === slide ? '#fff' : 'rgba(255,255,255,.45)' }} />)}
            </div>
          </div>

          {/* Install everything */}
          <div className="card" style={{ minHeight: 320, display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ marginTop: 0 }}>{phase === 'done' ? '✓ You’re ready' : 'Set up your AI office'}</h3>

            {/* Overall progress bar */}
            {phase !== 'idle' && <>
              <div className="between" style={{ fontSize: 12 }}>
                <span className="muted">{phase === 'done' ? 'Complete' : phase === 'error' ? 'Needs attention' : `Installing… ${cur ? cur.label.split(' — ')[0] : ''}`}</span>
                <strong>{overall}%</strong></div>
              <div className="bar mb" style={{ marginTop: 4 }}>
                <span style={{ width: `${overall}%`, background: phase === 'error' ? 'var(--red)' : phase === 'done' ? 'var(--green)' : undefined, transition: 'width .4s' }} /></div>
            </>}
            {phase === 'idle' && <p className="muted" style={{ fontSize: 13 }}>
              {IS_DESKTOP ? 'One click installs everything HERMUS needs — privately, no API keys.'
                : 'In the desktop app, HERMUS installs the local runtime & models here. In the browser preview, continue straight on.'}</p>}

            {/* Per-item status + percent */}
            <div>
              {PLAN.map((p) => {
                const st = status[p.key] || 'pending'
                return (
                  <div key={p.key} className="between" style={{ padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                    <div className="flex" style={{ gap: 10 }}>
                      <span className="stat-ico" style={{ width: 22, height: 22, borderRadius: 7, flexShrink: 0,
                        background: st === 'done' ? 'linear-gradient(135deg,#10b981,#34d399)' : st === 'fail' ? 'var(--red)' : st === 'running' ? 'var(--grad)' : 'var(--panel-2)',
                        color: st === 'pending' ? 'var(--muted)' : '#fff' }}>
                        {st === 'done' ? <Icon name="check" size={12} /> : st === 'running' ? <Icon name="zap" size={11} /> : st === 'fail' ? '✕' : ''}</span>
                      <span style={{ fontSize: 12.5, fontWeight: 500 }}>{p.label}</span>
                    </div>
                    {st === 'running' && <span className="muted" style={{ fontSize: 11 }}>{prog[p.key] ? `${prog[p.key]}%` : '…'}</span>}
                    {st === 'done' && <span className="tag" style={{ color: 'var(--green)', fontSize: 10 }}>done</span>}
                  </div>
                )
              })}
            </div>

            {/* Install paths */}
            {paths && <div className="muted" style={{ fontSize: 10.5, fontFamily: 'monospace', marginTop: 8 }}>
              runtime: {paths.ollama_bin}<br />models: {paths.models_dir}</div>}

            {/* Live log */}
            {logs.length > 0 && <div ref={logRef} style={{ marginTop: 8, maxHeight: 92, overflowY: 'auto',
              background: 'var(--panel-2)', borderRadius: 8, padding: '6px 8px', fontFamily: 'monospace', fontSize: 10.5, lineHeight: 1.5 }}>
              {logs.slice(-40).map((l, i) => <div key={i} className="muted" style={{ wordBreak: 'break-all' }}>{l}</div>)}
            </div>}

            <div className="row-actions" style={{ marginTop: 'auto', paddingTop: 12 }}>
              {phase === 'idle' && IS_DESKTOP && <>
                <button className="btn" onClick={installEverything}><Icon name="download" size={15} /> Install everything</button>
                <button className="btn ghost" onClick={() => done('/')}>Skip for now</button>
              </>}
              {phase === 'idle' && !IS_DESKTOP &&
                <button className="btn" onClick={() => done('/guided-setup')}>Continue</button>}
              {phase === 'installing' && <button className="btn" disabled>Installing… {overall}%</button>}
              {phase === 'error' && <>
                <button className="btn" onClick={installEverything}>Retry</button>
                <button className="btn ghost" onClick={() => done('/')}>Skip — do it later</button>
              </>}
              {phase === 'done' && <button className="btn green" onClick={() => done('/guided-setup')}>
                <Icon name="rocket" size={15} /> Continue to setup</button>}
            </div>
          </div>
        </div>
        <p className="muted" style={{ textAlign: 'center', fontSize: 12, marginTop: 14 }}>
          You can change or remove these anytime in <strong>Runtime &amp; Models</strong>.</p>
      </div>
    </div>
  )
}
