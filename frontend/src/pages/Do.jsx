import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 29 Part 3.1 — the "Do" page. Reads caps.features and renders the 23
// features as cards grouped by agent. Live → POST /features/{key}/run (the exact
// tool, approval-aware). Schedule → POST /feature-schedules (same params).
const AGENT_ORDER = ['Scheduler', 'Scribe', 'Finder', 'Inbox', 'Aria']
const AGENT_ICON = { Scheduler: 'clock', Scribe: 'scroll', Finder: 'brain', Inbox: 'inbox', Aria: 'sparkles' }
const CADENCES = [['daily', 'Daily'], ['weekly', 'Weekly'], ['monthly', 'Monthly'], ['yearly', 'Yearly'], ['custom', 'Custom']]

export default function Do() {
  const [features, setFeatures] = useState(null)
  const [q, setQ] = useState('')
  useEffect(() => {
    api.get('/assistant/capabilities').then((c) => setFeatures(c.features || [])).catch(() => setFeatures([]))
  }, [])
  if (!features) return <Loading />

  const filtered = features.filter((f) => !q || `${f.label} ${f.key} ${f.agent}`.toLowerCase().includes(q.toLowerCase()))
  const groups = AGENT_ORDER.map((a) => [a, filtered.filter((f) => f.agent === a)]).filter(([, c]) => c.length)

  return (
    <>
      <PageHead title="Do" subtitle="Your features — run any one now, or schedule it to run on its own." />
      <input className="mb" value={q} onChange={(e) => setQ(e.target.value)}
        placeholder="Find a feature…" style={{ width: '100%' }} />
      {groups.map(([agent, cards]) => (
        <div key={agent} style={{ marginBottom: 20 }}>
          <h3 className="flex" style={{ gap: 8, alignItems: 'center', marginBottom: 8 }}>
            <Icon name={AGENT_ICON[agent]} size={16} /> {agent}
            <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>({cards.length})</span>
          </h3>
          <div className="grid cols-2" style={{ gap: 12, alignItems: 'start' }}>
            {cards.map((c) => <FeatureCard key={c.key} card={c} />)}
          </div>
        </div>
      ))}
      {groups.length === 0 && <div className="muted">No features match “{q}”.</div>}
    </>
  )
}

function FeatureCard({ card }) {
  const [vals, setVals] = useState({})
  const [state, setState] = useState('idle')   // idle | working | done | approval | error
  const [result, setResult] = useState(null)
  const [schedOpen, setSchedOpen] = useState(false)
  const set = (n, v) => setVals((p) => ({ ...p, [n]: v }))

  // tool params from field values (datetime → tz-aware ISO so reminder.create &c
  // compare cleanly; tags → array; number → number). __time/__cron are scheduler-
  // only and never leak into params (loop is over card.fields).
  const params = useMemo(() => {
    const out = {}
    for (const f of card.fields) {
      let v = vals[f.name]
      if (v === undefined || v === '') continue
      if (f.type === 'datetime') { try { v = new Date(v).toISOString() } catch { /* keep raw */ } }
      else if (f.type === 'tags') v = String(v).split(',').map((s) => s.trim()).filter(Boolean)
      else if (f.type === 'number') v = Number(v)
      out[f.name] = v
    }
    return out
  }, [vals, card])

  const preview = useMemo(() => {
    let t = card.template
    for (const f of card.fields) t = t.replace(`{${f.name}}`, vals[f.name] || `{${f.label.toLowerCase()}}`)
    return t
  }, [vals, card])

  const missing = card.fields.filter((f) => f.required && !vals[f.name]).map((f) => f.label)
  const canSchedule = card.modes.includes('schedule')

  const speak = (t) => { try { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; speechSynthesis.speak(u) } catch {} }

  async function run(approved = false) {
    setState('working'); setResult(null)
    try {
      const r = await api.post(`/features/${card.key}/run`, { params, approved })
      window.dispatchEvent(new Event('hermus-activity'))
      setResult(r)
      setState(r.needs_approval ? 'approval' : r.ok ? 'done' : 'error')
      if (r.summary) speak(r.summary)
    } catch (e) {
      setState('error'); setResult({ summary: e?.detail?.message || e?.message || 'Could not run that.' })
    }
  }

  async function schedule(type) {
    const time = vals.__time || '09:00'
    const cadence = type === 'custom' ? { type, cron: vals.__cron || '0 9 * * 1' } : { type, time }
    try {
      const r = await api.post('/feature-schedules', { feature_key: card.key, params, cadence, label: card.label })
      setSchedOpen(false); setState('done')
      setResult({ summary: `Scheduled “${card.label}” — ${type}. Next run ${fmt(r.next_run_at)}.`, scheduled: true })
      speak(`Scheduled. ${card.label}, ${type}.`)
    } catch (e) {
      setSchedOpen(false); setState('error')
      setResult({ summary: e?.detail?.message || 'Could not schedule.' })
    }
  }

  const border = state === 'working' ? 'var(--amber)' : state === 'approval' ? 'var(--amber)'
    : state === 'error' ? 'var(--red)' : state === 'done' ? 'var(--green)' : undefined
  return (
    <div className="card" style={{ borderTop: border ? `3px solid ${border}` : undefined }}>
      <div className="between" style={{ alignItems: 'center' }}>
        <strong style={{ fontSize: 14 }}>{card.label}</strong>
        <span className={'pill ' + (state === 'working' ? 'st-online' : state === 'done' ? 'st-completed' : '')}
          style={{ fontSize: 11 }}><span className="dot" />{card.agent}{state === 'working' ? ' · working' : ''}</span>
      </div>
      {card.approval === 'required' && <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>🔒 Asks for your approval first</div>}

      <div style={{ margin: '8px 0' }}>
        {card.fields.map((f) => <FieldInput key={f.name} f={f} value={vals[f.name] || ''} onChange={(v) => set(f.name, v)} />)}
      </div>
      <div className="muted" style={{ fontSize: 11.5, fontStyle: 'italic', marginBottom: 8 }}>▸ {preview}</div>

      {result && state !== 'working' && (
        <div className="card mb" style={{ background: 'var(--bg-2)', padding: '8px 10px', borderColor: border }}>
          <div style={{ fontSize: 13 }}>
            {state === 'approval' ? '⚠ ' : state === 'error' ? '✕ ' : '✓ '}{result.summary}
          </div>
          {state === 'approval' && <Link className="btn sm mt" to="/approvals">Review in Approvals</Link>}
          {state === 'done' && !result.scheduled && <Link className="muted" style={{ fontSize: 11, display: 'inline-block', marginTop: 4 }} to="/activity">View in Activity →</Link>}
        </div>
      )}

      <div className="flex" style={{ gap: 8, position: 'relative' }}>
        <button className="btn sm" disabled={state === 'working' || missing.length > 0}
          title={missing.length ? `Fill: ${missing.join(', ')}` : ''} onClick={() => run(false)}>
          {state === 'working' ? '…' : '▸ Do it now'}
        </button>
        {canSchedule && (
          <button className="btn sm ghost" disabled={missing.length > 0} onClick={() => setSchedOpen((o) => !o)}>🗓 Schedule ▾</button>
        )}
        {schedOpen && (
          <div className="card" style={{ position: 'absolute', top: '112%', left: 0, zIndex: 5, padding: 10, minWidth: 240 }}>
            <div className="muted" style={{ fontSize: 11, marginBottom: 6 }}>Run it automatically at:</div>
            <input type="time" value={vals.__time || '09:00'} onChange={(e) => set('__time', e.target.value)} style={{ width: '100%', marginBottom: 6 }} />
            <input placeholder="Custom cron, e.g. 0 9 * * 1" value={vals.__cron || ''} onChange={(e) => set('__cron', e.target.value)} style={{ width: '100%', fontSize: 12, marginBottom: 8 }} />
            <div className="flex wrap" style={{ gap: 6 }}>
              {CADENCES.map(([k, l]) => <button key={k} className="tag" style={{ cursor: 'pointer' }} onClick={() => schedule(k)}>{l}</button>)}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function FieldInput({ f, value, onChange }) {
  const common = { value, onChange: (e) => onChange(e.target.value), placeholder: f.placeholder || '', style: { width: '100%' } }
  return (
    <div style={{ marginBottom: 6 }}>
      <label className="muted" style={{ fontSize: 11 }}>{f.label}{f.required ? ' *' : ''}</label>
      {f.type === 'textarea' ? <textarea rows={2} {...common} />
        : f.type === 'select' && f.enum ? <select {...common}><option value="">—</option>{f.enum.map((o) => <option key={o} value={o}>{o}</option>)}</select>
        : f.type === 'datetime' ? <input type="datetime-local" {...common} />
        : f.type === 'number' ? <input type="number" {...common} />
        : <input type="text" {...common} />}
    </div>
  )
}

function fmt(iso) {
  if (!iso) return 'soon'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}
