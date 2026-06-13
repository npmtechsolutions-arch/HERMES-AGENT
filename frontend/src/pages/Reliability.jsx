import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead, Stat } from '../components/ui'

const VALIDATORS = [
  ['Figures match a source record', 'Prices/budgets/dates must equal a property or lead value (CC-03 in code, not convention).'],
  ['Template variables resolved', 'No unresolved {placeholders} ever go out.'],
  ['Opt-out honored', 'Opted-out recipients are blocked (CC-04).'],
  ['Approval gate', 'First message to a new contact, or anything mentioning money, holds for human review.'],
]

export default function Reliability() {
  const [data, setData] = useState(null)
  const [history, setHistory] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const [running, setRunning] = useState(false)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([
    api.get('/evals').then(setData),
    api.get('/evals/history').then(setHistory).catch(() => {}),
  ]).catch(() => flash('err', 'Could not load reliability data.'))
  useEffect(() => { load() }, [])

  const run = async () => {
    setRunning(true)
    try { const r = await api.post('/evals/run'); flash(r.gate === 'PASS' ? 'ok' : 'err', r.message); speak(r.message); await load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run the release gate.') }
    finally { setRunning(false) }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/evals/resolve', { transcript: phrase })
      switch (r.action) {
        case 'run': await run(); break
        case 'history': setShowHistory(true); flash('ok', r.message); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__reliabilityVoice = (t) => { runCommand(t); return true }; return () => { if (window.__reliabilityVoice) delete window.__reliabilityVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!data) return <Loading />
  const lr = data.last_run
  // per-kind breakdown parsed from result details ("golden: …" / "adversarial: …")
  const kinds = {}
  if (lr) for (const r of lr.results) {
    const k = (r.detail || '').split(':')[0] || 'case'
    kinds[k] = kinds[k] || { pass: 0, total: 0 }
    kinds[k].total++; if (r.passed) kinds[k].pass++
  }

  return (
    <>
      <PageHead title="Agent Reliability"
        sub="Golden-task suite + send-time validators — nothing ships with a factually-wrong message.">
        <div className="flex" style={{ gap: 8 }}>
          {history.length > 0 && <button className="btn ghost sm" onClick={() => setShowHistory((v) => !v)}>
            <Icon name="refresh" size={14} /> History ({history.length})</button>}
          <button className="btn" onClick={run} disabled={running}>
            <Icon name="check" size={16} /> {running ? 'Running…' : 'Run release gate'}</button>
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "run the release gate", "show the run history"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="grid cols-3 mb">
        <Stat icon="tasks" label="Golden cases" value={data.cases.length} />
        <Stat icon="check" tint="green" label="Last gate" value={lr ? `${lr.passed}/${lr.total}` : '—'} />
        <Stat icon="shield" tint={lr && lr.gate === 'PASS' ? 'green' : 'amber'} label="Status"
          value={lr ? lr.gate : 'not run'} />
      </div>

      {showHistory && (
        <div className="card mb">
          <h3 style={{ marginTop: 0 }}>Run history · {history.length}</h3>
          {history.map((h) => (
            <div key={h.suite_run_id} className="between" style={{ padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12.5 }}>
              <span className="muted">{h.at ? new Date(h.at).toLocaleString() : '—'}</span>
              <span><strong>{h.passed}/{h.total}</strong> <span className="tag" style={{ color: h.gate === 'PASS' ? 'var(--green)' : 'var(--red)' }}>{h.gate}</span></span>
            </div>
          ))}
          {history.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No runs yet.</div>}
        </div>
      )}

      <div className="grid cols-2">
        <div className="card">
          <h3><Icon name="shield" size={17} /> Send-time validators (every outbound)</h3>
          <p className="muted" style={{ fontSize: 13 }}>Deterministic checks run in code before any message sends.
            A failure holds the message for a human — it is never sent.</p>
          {VALIDATORS.map(([t, d]) => (
            <div key={t} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div className="flex"><Icon name="check" size={14} style={{ color: 'var(--green)' }} /><strong style={{ fontSize: 13 }}>{t}</strong></div>
              <div className="muted" style={{ fontSize: 12, marginLeft: 22 }}>{d}</div>
            </div>
          ))}
        </div>

        <div className="card">
          <h3><Icon name="tasks" size={17} /> Golden-task results</h3>
          {!lr ? <div className="muted" style={{ fontSize: 13 }}>Run the release gate to evaluate the canonical scenarios
            (lead variants, edge phrasings, adversarial cases).</div>
            : <>
              <div className={'card mb'} style={{ background: lr.gate === 'PASS' ? 'var(--success-bg)' : 'var(--danger-bg)',
                border: `1px solid ${lr.gate === 'PASS' ? 'var(--success-border)' : 'var(--danger-border)'}` }}>
                <strong style={{ color: lr.gate === 'PASS' ? 'var(--success-fg)' : 'var(--danger-fg)' }}>
                  {lr.gate === 'PASS' ? `✓ Gate PASS — ${lr.passed}/${lr.total}, zero bad sends` : `✕ Gate FAIL — ${lr.total - lr.passed} failing`}</strong>
                {Object.keys(kinds).length > 0 && <div className="flex mt" style={{ gap: 12, fontSize: 12 }}>
                  {Object.entries(kinds).map(([k, v]) => (
                    <span key={k} style={{ textTransform: 'capitalize' }}>{k}: <strong>{v.pass}/{v.total}</strong></span>))}
                </div>}
              </div>
              {lr.results.map((r, i) => (
                <div key={i} className="between" style={{ padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12.5 }}>
                  <span>{r.detail}</span>
                  <span className="tag" style={{ color: r.passed ? 'var(--green)' : 'var(--red)' }}>{r.passed ? 'pass' : 'fail'}</span>
                </div>
              ))}
            </>}
        </div>
      </div>
    </>
  )
}
