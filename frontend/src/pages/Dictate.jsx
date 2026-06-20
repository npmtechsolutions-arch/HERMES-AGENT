import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import DictateMic from '../components/DictateMic'
import { PageHead } from '../components/ui'

const MODES = [
  ['clean', 'Clean up'], ['formal', 'Make formal'], ['notes', 'Bullet notes'], ['raw', 'Punctuation only'],
]

// HERMUS Dictate (M36) — voice-to-text. Speak, get polished text. On-device
// transcription (browser STT); polish runs on the local LLM when present.
export default function Dictate() {
  const [text, setText] = useState('')
  const [mode, setMode] = useState('clean')
  const [busy, setBusy] = useState(false)
  const [engine, setEngine] = useState('')
  const [status, setStatus] = useState(null)
  const [msg, setMsg] = useState(null)
  const baseRef = useRef('')

  const flash = (kind, t) => { setMsg({ kind, t }); setTimeout(() => setMsg(null), 6000) }
  useEffect(() => { api.get('/dictate/status').then(setStatus).catch(() => {}) }, [])

  const onStart = () => { baseRef.current = text ? text.replace(/\s+$/, '') + ' ' : '' }
  const onText = (session) => setText(baseRef.current + session)

  const polish = async () => {
    if (!text.trim()) return
    setBusy(true)
    try {
      const r = await api.post('/dictate/polish', { raw: text, mode })
      setText(r.text); setEngine(r.engine)
      flash('ok', r.engine === 'rule-based'
        ? 'Polished on-device (local AI offline — used punctuation rules).'
        : `Polished with ${r.engine}.`)
    } catch { flash('err', 'Could not polish the text.') }
    finally { setBusy(false) }
  }
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); flash('ok', 'Copied to clipboard.') }
    catch { flash('err', 'Copy failed — select and copy manually.') }
  }
  // Voice → action: send the dictated text to the assistant, which routes it to
  // the right agent/tool and does the work (reminder, note, search, …).
  const runCommand = async () => {
    if (!text.trim()) return
    setBusy(true)
    try {
      const r = await api.post('/assistant', { text })
      flash(r.ok ? 'ok' : 'err', '🔊 ' + (r.summary || 'Done.'))
      try { const u = new SpeechSynthesisUtterance(r.summary); u.lang = 'en-IN'; speechSynthesis.speak(u) } catch {}
      window.dispatchEvent(new Event('hermus-activity'))
    } catch { flash('err', 'Could not run that command.') }
    finally { setBusy(false) }
  }
  // Type the text straight into whatever desktop app you're using. The desktop
  // bridge injects keystrokes into the focused app (needs Accessibility perms);
  // in the browser it falls back to clipboard.
  const insertIntoApp = async () => {
    if (!text.trim()) return
    if (window.hermus?.typeText) {
      flash('ok', 'Switch to your app — typing in 2s…')
      setTimeout(async () => {
        try { const r = await window.hermus.typeText(text); flash('ok', `Typed into your active app (${r?.method || 'keystrokes'}).`) }
        catch { flash('err', 'Could not type into the app — grant Accessibility permission.') }
      }, 2000)
    } else {
      try { await navigator.clipboard.writeText(text); flash('ok', 'Copied — switch to your app and press ⌘V / Ctrl+V.') }
      catch { flash('err', 'Copy failed.') }
    }
  }
  const save = async () => {
    if (!text.trim()) return
    try {
      await api.post('/memory/ingest', {
        title: 'Dictation — ' + new Date().toLocaleString(), body: text,
        memory_class: 'personal', source_type: 'dictation',
      })
      flash('ok', 'Saved to your Second Brain.')
    } catch { flash('err', 'Could not save.') }
  }
  const words = text.trim() ? text.trim().split(/\s+/).length : 0

  return (
    <>
      <PageHead title="Voice Type" sub="Dictate anything — speak and get clean, punctuated text you can use anywhere.">
        <span className="pill st-completed" title="Transcription runs on this device; your voice is never sent to a cloud service">
          <span className="dot" /> On-device · private</span>
      </PageHead>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.t}</div>}

      <div className="card" style={{ textAlign: 'center', paddingTop: 24 }}>
        <DictateMic big onStart={onStart} onText={onText} />
        <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>
          Tap the mic and speak. Say “new line”, “comma”, “period”, “question mark” for punctuation.
        </p>
      </div>

      <div className="card mt">
        <div className="between mb">
          <div className="flex wrap" style={{ gap: 6 }}>
            {MODES.map(([k, label]) => (
              <button key={k} className={'btn sm ' + (mode === k ? '' : 'ghost')} onClick={() => setMode(k)}>{label}</button>
            ))}
          </div>
          <span className="muted" style={{ fontSize: 12 }}>{words} words{engine ? ` · ${engine}` : ''}</span>
        </div>
        <textarea rows={10} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Your dictation appears here. Edit freely, then Polish, Copy or Save…"
          style={{ width: '100%', fontSize: 15, lineHeight: 1.6 }} />
        <div className="row-actions" style={{ marginTop: 12 }}>
          <button className="btn" disabled={busy || !text.trim()} onClick={polish}>
            <Icon name="sparkles" size={15} /> {busy ? 'Polishing…' : 'Polish'}</button>
          <button className="btn secondary" disabled={!text.trim()} onClick={insertIntoApp}>
            <Icon name="monitor" size={15} /> Insert into active app</button>
          <button className="btn secondary" disabled={!text.trim()} onClick={runCommand}>
            <Icon name="command" size={15} /> Run as command</button>
          <button className="btn secondary" disabled={!text.trim()} onClick={copy}>Copy</button>
          <button className="btn secondary" disabled={!text.trim()} onClick={save}>
            <Icon name="brain" size={15} /> Save</button>
          <button className="btn ghost" disabled={!text} onClick={() => { setText(''); setEngine('') }}>
            <Icon name="x" size={15} /> Clear</button>
        </div>
      </div>

      <div className="card mt" style={{ background: 'var(--bg-2)' }}>
        <h3 style={{ marginTop: 0, fontSize: 14 }}><Icon name="command" size={15} /> Two ways to use your voice</h3>
        <div className="grid cols-2" style={{ gap: 14 }}>
          <div>
            <strong style={{ fontSize: 13 }}>Dictate into any app</strong>
            <p className="muted" style={{ fontSize: 12, margin: '4px 0 0' }}>
              Speak → get clean text → <em>Insert into active app</em> types it straight into your email, doc, browser or
              chat. {window.hermus?.typeText ? 'The desktop app injects keystrokes into the focused window (grant Accessibility once).' : 'On the desktop app it types directly; in the browser it copies for you to paste.'}
            </p>
          </div>
          <div>
            <strong style={{ fontSize: 13 }}>Speak a command → it acts</strong>
            <p className="muted" style={{ fontSize: 12, margin: '4px 0 0' }}>
              Say something like “remind me to call the bank tomorrow” → <em>Run as command</em> sends it to Aria, who
              routes it to the right agent and does it. The same engine behind the 🎤 orb — your words become actions.
            </p>
          </div>
        </div>
        <p className="muted" style={{ fontSize: 11.5, marginTop: 10 }}>
          {status?.llm ? `Polish uses your local model (${status.model}) — fully offline.`
            : 'Polish uses on-device punctuation rules now; install the local AI model for smarter cleanup.'}
          {' '}Transcription is always on-device — your voice never leaves this computer.
        </p>
      </div>
    </>
  )
}
