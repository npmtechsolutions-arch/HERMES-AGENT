import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 27 Part 4 — full picture of every agent: status, what it's doing now,
// what's scheduled, recent actions, and this week's stats. One screen.
const ICON = { Aria: 'sparkles', Scheduler: 'clock', Inbox: 'inbox', Scribe: 'scroll', Finder: 'brain' }
const SCLS = { working: 'green', idle: 'grey', paused: 'grey', waiting: 'amber', error: 'red', escalated: 'red' }

export default function AgentActionSummary() {
  const [data, setData] = useState(null)
  useEffect(() => { api.get('/team/overview').then(setData).catch(() => setData({ agents: [] })) }, [])
  if (!data) return <Loading />

  return (
    <>
      <PageHead title="Agent Actions" subtitle="What every agent is doing now, what's scheduled, and what it's done." />
      <div className="flex wrap mb" style={{ gap: 10 }}>
        <Pill n={data.totals?.agents} l="agents" />
        <Pill n={data.totals?.working} l="working now" />
        <Pill n={data.totals?.scheduled} l="scheduled" />
      </div>
      <div className="grid" style={{ gap: 12 }}>
        {data.agents.map((a) => (
          <div key={a.id} className="card">
            <div className="between" style={{ alignItems: 'flex-start' }}>
              <div className="flex" style={{ gap: 10, alignItems: 'center' }}>
                <Icon name={ICON[a.name] || 'bot'} size={18} />
                <div>
                  <Link to={'/my-agents/' + a.id} style={{ fontWeight: 700, fontSize: 14.5, textDecoration: 'none' }}>
                    {a.name}{a.is_ceo ? ' · Chief of Staff' : ''}</Link>
                  <div className="muted" style={{ fontSize: 11.5 }}>{a.role}</div>
                </div>
              </div>
              <span className={'pill ' + (SCLS[a.status] || 'grey')}><span className="dot" />{a.status}</span>
            </div>

            <div className="grid cols-2" style={{ gap: 10, marginTop: 10 }}>
              <Box label="Doing now">
                {a.doing_now ? <span style={{ color: 'var(--primary)' }}>🟢 {a.doing_now}</span>
                  : <span className="muted">Idle</span>}
              </Box>
              <Box label={`Scheduled (${a.scheduled_count})`}>
                {a.scheduled.length ? a.scheduled.map((s, i) => <div key={i} style={{ fontSize: 12 }}>• {s}</div>)
                  : <span className="muted">{a.scheduled_count ? `${a.scheduled_count} upcoming` : 'Nothing queued'}</span>}
              </Box>
            </div>

            <div style={{ marginTop: 10 }}>
              <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: .5 }}>This week</div>
              <div style={{ fontSize: 13 }}>{a.this_week.phrase}</div>
            </div>

            {a.recent.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: .5 }}>Recent actions</div>
                {a.recent.map((r, i) => (
                  <div key={i} className="flex between" style={{ fontSize: 12, padding: '3px 0' }}>
                    <span>{r.summary}</span><span className="muted">{r.tool}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {data.agents.length === 0 && <div className="muted">Your team appears here once the product is active.</div>}
      </div>
    </>
  )
}

function Pill({ n, l }) { return <div className="card" style={{ padding: '8px 14px', minWidth: 90, textAlign: 'center' }}><div style={{ fontSize: 20, fontWeight: 800 }}>{n ?? 0}</div><div className="muted" style={{ fontSize: 11 }}>{l}</div></div> }
function Box({ label, children }) { return <div style={{ background: 'var(--bg-2)', borderRadius: 10, padding: 10 }}><div className="muted" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: .5, marginBottom: 4 }}>{label}</div>{children}</div> }
