import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 29 Part 3.2 — the Scheduled-tasks view. Everything you've set to run on its
// own: what it does, which agent, status, next run, last result — with pause /
// resume / skip-next / edit cadence / cancel, and expandable run history (#3).
const CADENCES = [['daily', 'Daily'], ['weekly', 'Weekly'], ['monthly', 'Monthly'], ['yearly', 'Yearly'], ['custom', 'Custom']]
const RUN_MARK = { success: '✓', failed: '✕', needs_approval: '⚠' }

export default function Scheduled() {
  const [rows, setRows] = useState(null)
  const load = () => api.get('/feature-schedules').then(setRows).catch(() => setRows([]))
  useEffect(() => { load() }, [])
  if (!rows) return <Loading />

  return (
    <>
      <PageHead title="Scheduled" subtitle="Tasks your agents run on their own — on time, forever." />
      <div className="muted mb" style={{ fontSize: 12 }}>
        Set these up from <Link to="/do">Do</Link> → Schedule. {rows.length} scheduled task{rows.length === 1 ? '' : 's'}.
      </div>
      {rows.length === 0 && <div className="card muted" style={{ fontSize: 13 }}>Nothing scheduled yet. Open <Link to="/do">Do</Link>, pick a feature, and tap “Schedule”.</div>}
      <div className="grid" style={{ gap: 10 }}>
        {rows.map((s) => <SchedRow key={s.id} s={s} reload={load} />)}
      </div>
    </>
  )
}

function SchedRow({ s, reload }) {
  const [open, setOpen] = useState(false)
  const [runs, setRuns] = useState(null)
  const [editing, setEditing] = useState(false)
  const [cad, setCad] = useState({ type: s.cadence || 'daily', time: s.cadence_spec?.time || '09:00', cron: s.cadence_spec?.cron || '' })
  const [instr, setInstr] = useState(s.instructions || '')

  const act = async (verb) => { await api.post(`/feature-schedules/${s.id}/${verb}`, {}); reload() }
  const cancel = async () => { if (confirm(`Cancel “${s.label}” for good?`)) { await api.del(`/feature-schedules/${s.id}`); reload() } }
  const expand = async () => {
    setOpen((o) => !o)
    if (!runs) setRuns(await api.get(`/feature-schedules/${s.id}/runs`).catch(() => []))
  }
  const saveEdit = async () => {
    const cadence = cad.type === 'custom' ? { type: 'custom', cron: cad.cron || '0 9 * * 1' } : { type: cad.type, time: cad.time }
    await api.patch(`/feature-schedules/${s.id}`, { cadence, instructions: instr })
    setEditing(false); reload()
  }

  const paused = s.status === 'paused'
  return (
    <div className="card" style={{ borderLeft: `3px solid ${paused ? 'var(--muted)' : 'var(--green)'}` }}>
      <div className="between" style={{ alignItems: 'flex-start' }}>
        <div>
          <div className="flex" style={{ gap: 8, alignItems: 'center' }}>
            <strong style={{ fontSize: 14 }}>{s.label || s.feature_key}</strong>
            <span className="tag" style={{ fontSize: 10 }}>{s.agent}</span>
            <span className={'pill ' + (paused ? '' : 'st-online')} style={{ fontSize: 10 }}><span className="dot" />{s.status}</span>
          </div>
          <div className="muted" style={{ fontSize: 11.5, marginTop: 3 }}>
            {s.cadence}{s.cadence === 'custom' ? ` (${s.expression})` : ''} · next {fmt(s.next_run_at)}
            {s.last_status ? ` · last: ${RUN_MARK[s.last_status] || ''} ${s.last_status}` : ''}
            {s.consecutive_failures ? ` · ${s.consecutive_failures} fails` : ''}
          </div>
        </div>
        <div className="flex" style={{ gap: 5 }}>
          <button className="btn sm ghost" onClick={() => act(paused ? 'resume' : 'pause')}>{paused ? 'Resume' : 'Pause'}</button>
          <button className="btn sm ghost" onClick={() => act('skip-next')} title="Skip the next run">Skip</button>
          <button className="btn sm ghost" onClick={() => setEditing((e) => !e)}>Edit</button>
          <button className="btn sm ghost" onClick={cancel} style={{ color: 'var(--red)' }}>Cancel</button>
        </div>
      </div>

      {editing && (
        <div className="card mt" style={{ background: 'var(--bg-2)', padding: 10 }}>
          <div className="flex wrap" style={{ gap: 6, marginBottom: 6 }}>
            {CADENCES.map(([k, l]) => <button key={k} className={'tag' + (cad.type === k ? ' active' : '')} style={{ cursor: 'pointer', borderColor: cad.type === k ? 'var(--primary)' : '' }} onClick={() => setCad({ ...cad, type: k })}>{l}</button>)}
          </div>
          {cad.type === 'custom'
            ? <input placeholder="cron e.g. 0 9 * * 1" value={cad.cron} onChange={(e) => setCad({ ...cad, cron: e.target.value })} style={{ width: '100%', marginBottom: 6, fontSize: 12 }} />
            : <input type="time" value={cad.time} onChange={(e) => setCad({ ...cad, time: e.target.value })} style={{ width: '100%', marginBottom: 6 }} />}
          <textarea rows={2} placeholder="How to do it (optional) — e.g. keep it under 5 lines" value={instr} onChange={(e) => setInstr(e.target.value)} style={{ width: '100%', marginBottom: 6 }} />
          <div className="flex" style={{ gap: 6 }}>
            <button className="btn sm" onClick={saveEdit}>Save</button>
            <button className="btn sm ghost" onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </div>
      )}

      <button className="btn sm ghost mt" onClick={expand}>{open ? 'Hide' : 'Run history'}</button>
      {open && (
        <div className="mt">
          {!runs ? <span className="muted" style={{ fontSize: 12 }}>Loading…</span>
            : runs.length === 0 ? <span className="muted" style={{ fontSize: 12 }}>No runs yet — it hasn’t fired.</span>
              : runs.map((r) => (
                <div key={r.id} className="flex between" style={{ fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                  <span>{RUN_MARK[r.status] || '•'} {r.summary || r.status}{r.retries ? ` (${r.retries} retries)` : ''}</span>
                  <span className="muted" style={{ whiteSpace: 'nowrap' }}>{fmt(r.at)}</span>
                </div>
              ))}
        </div>
      )}
    </div>
  )
}

function fmt(iso) { if (!iso) return '—'; try { return new Date(iso).toLocaleString() } catch { return iso } }
