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
          <button className="btn secondary" disabled={!text.trim()} onClick={copy}>Copy</button>
          <button className="btn secondary" disabled={!text.trim()} onClick={save}>
            <Icon name="brain" size={15} /> Save to Second Brain</button>
          <button className="btn ghost" disabled={!text} onClick={() => { setText(''); setEngine('') }}>
            <Icon name="x" size={15} /> Clear</button>
        </div>
      </div>

      <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
        {status?.llm
          ? `Polish uses your local model (${status.model}) — fully offline.`
          : 'Polish uses on-device punctuation rules now; install the local AI model for smarter cleanup.'}
        {' '}A system-wide overlay (dictate into any app) is coming next.
      </p>
    </>
  )
}
