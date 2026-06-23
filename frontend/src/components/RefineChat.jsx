import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from './Icon'

// Doc 30 Phase 1 — refine-with-chat. Anchored to a result_id: shows the current
// version, the version history (with revert), and a chat box to refine. Each
// instruction → /assistant/refine → a new version. Guardrails still apply (a
// fabricated figure is blocked, not saved).
export default function RefineChat({ resultId, onClose }) {
  const [versions, setVersions] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const bodyRef = useRef(null)

  const load = () => api.get(`/results/${resultId}/versions`).then((r) => setVersions(r.versions || [])).catch(() => setVersions([]))
  useEffect(() => { load() }, [resultId])
  useEffect(() => { bodyRef.current?.scrollTo(0, bodyRef.current.scrollHeight) }, [versions])

  const current = versions?.find((v) => v.is_current) || versions?.[versions.length - 1]

  async function submit(e) {
    e.preventDefault()
    if (!text.trim()) return
    setBusy(true); setNote('')
    try {
      const r = await api.post('/assistant/refine', { result_id: resultId, instruction: text })
      if (r.ok) { setText(''); await load() }
      else setNote(r.summary || 'Could not refine that.')
      window.dispatchEvent(new Event('hermus-activity'))
    } catch (err) { setNote(err?.detail?.message || 'Could not refine that.') }
    finally { setBusy(false) }
  }
  async function revert(version) {
    await api.post(`/results/${resultId}/revert`, { version }); load()
  }

  return (
    <div style={OVERLAY} onClick={onClose}>
      <div className="card" style={PANEL} onClick={(e) => e.stopPropagation()}>
        <div className="between" style={{ alignItems: 'center' }}>
          <strong className="flex" style={{ gap: 6, alignItems: 'center' }}><Icon name="sparkles" size={16} /> Refine</strong>
          <button className="icon-btn" onClick={onClose} style={{ width: 28, height: 28 }}><Icon name="x" size={15} /></button>
        </div>

        {versions && versions.length > 0 && (
          <div className="flex wrap" style={{ gap: 5, margin: '8px 0' }}>
            {versions.map((v) => (
              <button key={v.version} className={'tag' + (v.is_current ? ' active' : '')}
                title={v.instruction || 'original'} style={{ cursor: 'pointer', borderColor: v.is_current ? 'var(--primary)' : '' }}
                onClick={() => revert(v.version)}>
                v{v.version}{v.is_current ? ' •' : ''}
              </button>
            ))}
            <span className="muted" style={{ fontSize: 11, alignSelf: 'center' }}>tap a version to revert</span>
          </div>
        )}

        <div ref={bodyRef} className="card" style={{ background: 'var(--bg-2)', maxHeight: 280, overflowY: 'auto', whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.5 }}>
          {!versions ? 'Loading…' : (current?.output || '(empty)')}
        </div>
        {current?.instruction && <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>v{current.version} — “{current.instruction}”</div>}
        {note && <div className="card mt" style={{ borderColor: 'var(--red)', fontSize: 12, padding: '6px 10px' }}>⚠ {note}</div>}

        <form onSubmit={submit} className="flex mt" style={{ gap: 6 }}>
          <input value={text} onChange={(e) => setText(e.target.value)} disabled={busy}
            placeholder='e.g. "make it shorter and more formal"' style={{ flex: 1 }} />
          <button className="btn sm" type="submit" disabled={busy || !text.trim()}>{busy ? '…' : 'Refine'}</button>
        </form>
        <div className="muted" style={{ fontSize: 10.5, marginTop: 6 }}>Edits content only — facts and figures are protected, and any send still asks you first.</div>
      </div>
    </div>
  )
}

const OVERLAY = { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.4)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }
const PANEL = { width: 'min(540px, 96vw)', maxHeight: '88vh', overflowY: 'auto' }
