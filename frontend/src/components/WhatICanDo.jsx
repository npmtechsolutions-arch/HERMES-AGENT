import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Icon from './Icon'

// Doc 27 Part 2.1 — capabilities as tappable example commands. Users learn what
// to SAY by doing. Tapping a command runs it through the real /assistant spine.
// `compact` = the Home teaser (first example per group); full = the Capabilities page.
export default function WhatICanDo({ compact = false }) {
  const [caps, setCaps] = useState(null)
  const [running, setRunning] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => { api.get('/assistant/capabilities').then(setCaps).catch(() => setCaps({ groups: [] })) }, [])

  const run = async (text) => {
    setRunning(text); setResult(null)
    try {
      const r = await api.post('/assistant', { text })
      setResult({ text, ok: r.ok, summary: r.summary, needs: r.needs_approval, note: r.note })
      try { const u = new SpeechSynthesisUtterance(r.summary); u.lang = 'en-IN'; speechSynthesis.cancel(); speechSynthesis.speak(u) } catch {}
      window.dispatchEvent(new Event('hermus-activity'))
    } catch (e) {
      setResult({ text, ok: false, summary: e?.message || 'Could not run that.' })
    } finally { setRunning(null) }
  }

  if (!caps) return null
  const groups = compact ? caps.groups.slice(0, 6) : caps.groups

  return (
    <div className={compact ? '' : 'card'}>
      {!compact && caps.product_line && <p className="muted" style={{ marginTop: 0 }}>{caps.product_line}</p>}
      {result && (
        <div className="card mb" style={{ background: 'var(--bg-2)', borderColor: result.ok ? 'var(--green)' : 'var(--red)' }}>
          <div className="muted" style={{ fontSize: 11 }}>You ran: “{result.text}”</div>
          <div style={{ fontSize: 13.5, marginTop: 4 }}>🔊 {result.summary}</div>
          {result.needs && <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>⚠️ Needs your approval — say or tap “approve”.</div>}
        </div>
      )}
      <div className={compact ? 'grid' : 'grid'} style={{ gridTemplateColumns: compact ? '1fr 1fr' : '1fr', gap: 10 }}>
        {groups.map((g) => (
          <div key={g.key} className={compact ? '' : 'card'} style={compact ? {} : { background: 'var(--bg-2)' }}>
            <div className="flex" style={{ gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <Icon name={g.icon} size={15} />
              <strong style={{ fontSize: 13 }}>{g.label}</strong>
              {!compact && g.agent && <span className="tag" style={{ fontSize: 10 }}>{g.agent}</span>}
            </div>
            {!compact && <div className="muted" style={{ fontSize: 11.5, marginBottom: 6 }}>{g.blurb}</div>}
            <div className="flex wrap" style={{ gap: 6 }}>
              {(compact ? g.examples.slice(0, 1) : g.examples).map((ex) => (
                <button key={ex} className="tag" style={{ cursor: 'pointer', textAlign: 'left', whiteSpace: 'normal' }}
                  disabled={running === ex} onClick={() => run(ex)} title="Tap to run">
                  {running === ex ? '…' : <>“{ex}” <span style={{ opacity: .6 }}>▸</span></>}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      {compact && <Link className="muted" style={{ fontSize: 12, display: 'inline-block', marginTop: 8 }} to="/capabilities">See all I can do →</Link>}
    </div>
  )
}
