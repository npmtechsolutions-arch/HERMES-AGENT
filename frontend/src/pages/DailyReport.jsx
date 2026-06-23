import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 29 Part 3.5 — the daily per-agent report. What every assistant did today,
// what needs you, hours saved — with day navigation and a spoken briefing.
const AGENT_ICON = { Aria: 'sparkles', Scheduler: 'clock', Scribe: 'scroll', Finder: 'brain', Inbox: 'inbox' }
const STATUS = { ok: { i: '✓', c: 'var(--green)', t: 'all good' }, pending: { i: '⚠', c: 'var(--amber)', t: 'needs you' }, failed: { i: '✕', c: 'var(--red)', t: 'failed' } }

function ymd(d) { return d.toISOString().slice(0, 10) }

export default function DailyReport() {
  const [date, setDate] = useState(ymd(new Date()))
  const [rep, setRep] = useState(null)
  useEffect(() => { setRep(null); api.get(`/reports/daily?date=${date}`).then(setRep).catch(() => setRep(null)) }, [date])

  const shift = (days) => { const d = new Date(date); d.setDate(d.getDate() + days); setDate(ymd(d)) }
  const speak = () => { if (rep) try { const u = new SpeechSynthesisUtterance(rep.narrative); u.lang = 'en-IN'; speechSynthesis.speak(u) } catch {} }
  const isToday = date === ymd(new Date())

  return (
    <>
      <PageHead title="Daily Report" subtitle="What your team did — per agent, every day." />
      <div className="between mb">
        <div className="flex" style={{ gap: 6, alignItems: 'center' }}>
          <button className="btn sm ghost" onClick={() => shift(-1)}>◂</button>
          <strong style={{ fontSize: 13 }}>{rep?.label || date}</strong>
          <button className="btn sm ghost" disabled={isToday} onClick={() => shift(1)}>▸</button>
        </div>
        {rep && <button className="btn sm ghost" onClick={speak}><Icon name="play" size={13} /> Read it to me</button>}
      </div>

      {!rep ? <Loading /> : (
        <>
          <div className="card mb" style={{ background: 'var(--grad)', color: '#fff', border: 'none' }}>
            <div style={{ fontSize: 15 }}>{rep.narrative}</div>
            <div className="flex wrap" style={{ gap: 18, marginTop: 8 }}>
              <Big n={rep.totals.actions} l="things done" />
              <Big n={`~${rep.totals.hours_saved}h`} l="saved" />
              <Big n={rep.totals.needed_you} l="needed you" />
            </div>
          </div>

          <div className="card">
            {rep.agents.map((a) => {
              const st = STATUS[a.status] || STATUS.ok
              return (
                <div key={a.agent} className="flex between" style={{ padding: '11px 2px', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
                  <div className="flex" style={{ gap: 10, alignItems: 'center' }}>
                    <Icon name={AGENT_ICON[a.agent] || 'bot'} size={17} />
                    <div>
                      <Link to="/my-agents" style={{ fontWeight: 600, fontSize: 13.5, textDecoration: 'none' }}>{a.agent}</Link>
                      <div className="muted" style={{ fontSize: 11.5 }}>
                        {a.actions} action{a.actions === 1 ? '' : 's'} · {a.summary}
                        {a.pending ? ` · ${a.pending} waiting` : ''}{a.failures ? ` · ${a.failures} failed` : ''}
                      </div>
                    </div>
                  </div>
                  <span style={{ color: st.c, fontSize: 12.5, fontWeight: 600, whiteSpace: 'nowrap' }}>{st.i} {st.t}</span>
                </div>
              )
            })}
          </div>

          {rep.totals.needed_you > 0 && (
            <div className="card mt" style={{ borderColor: 'var(--amber)' }}>
              <strong style={{ fontSize: 13 }}>⚠ {rep.totals.needed_you} need{rep.totals.needed_you === 1 ? 's' : ''} you</strong>
              <div className="muted mt" style={{ fontSize: 12 }}>
                Resolve in <Link to="/approvals">Approvals</Link> or check <Link to="/agent-activity">Agent Activity</Link>.
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}

function Big({ n, l }) { return <div><div style={{ fontSize: 24, fontWeight: 800 }}>{n}</div><div style={{ fontSize: 11, opacity: .9 }}>{l}</div></div> }
