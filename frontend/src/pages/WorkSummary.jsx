import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 27 Part 8 — the value/renewal view. What the agents got done, hours saved,
// and trends. The user SEES the value, which is why they keep paying.
const RANGES = [['week', 'This week'], ['month', 'This month'], ['all', 'All time']]

export default function WorkSummary() {
  const [range, setRange] = useState('week')
  const [s, setS] = useState(null)

  useEffect(() => { setS(null); api.get(`/work-summary?range=${range}`).then(setS).catch(() => setS(null)) }, [range])

  const speak = () => { if (s) try { const u = new SpeechSynthesisUtterance(s.headline); u.lang = 'en-IN'; speechSynthesis.speak(u) } catch {} }

  return (
    <>
      <PageHead title="Work Summary" subtitle="Everything your assistant got done — and the time it saved you." />
      <div className="between mb">
        <div className="tabs" style={{ margin: 0, maxWidth: 280 }}>
          {RANGES.map(([k, l]) => <button key={k} className={range === k ? 'active' : ''} onClick={() => setRange(k)}>{l}</button>)}
        </div>
        {s && <button className="btn sm ghost" onClick={speak}><Icon name="play" size={13} /> Read it to me</button>}
      </div>

      {!s ? <Loading /> : (
        <>
          <div className="card mb" style={{ background: 'var(--grad)', color: '#fff', border: 'none' }}>
            <div style={{ fontSize: 12, opacity: .9, textTransform: 'uppercase', letterSpacing: 1 }}>{range}</div>
            <div style={{ fontSize: 22, fontWeight: 700, margin: '4px 0' }}>{s.headline}</div>
            <div className="flex wrap" style={{ gap: 18, marginTop: 8 }}>
              <Big n={s.total_actions} l="things handled" />
              <Big n={`~${s.value.hours_saved}h`} l="time saved" />
              <Big n={`₹${s.value.money_value_inr.toLocaleString('en-IN')}`} l="value" />
              <Big n={s.value.after_hours} l="after-hours" />
            </div>
          </div>

          <div className="grid cols-2">
            <div className="card">
              <h3 style={{ marginTop: 0 }}><Icon name="users" size={16} /> By agent</h3>
              <Bars data={s.by_agent} />
            </div>
            <div className="card">
              <h3 style={{ marginTop: 0 }}><Icon name="layers" size={16} /> By area</h3>
              <Bars data={s.by_area} />
            </div>
          </div>

          <div className="card mt">
            <h3 style={{ marginTop: 0 }}><Icon name="chart" size={16} /> Trends</h3>
            <div className="flex wrap" style={{ gap: 24, fontSize: 13 }}>
              <div>Direction: <strong>{trendIcon(s.trends.direction)} {s.trends.direction}</strong> <span className="muted">({s.trends.this_period} vs {s.trends.last_period} last)</span></div>
              {s.trends.most_active_agent && <div>Most active: <strong>{s.trends.most_active_agent}</strong></div>}
              {s.trends.busiest_area && <div>Busiest area: <strong>{s.trends.busiest_area}</strong></div>}
            </div>
          </div>
        </>
      )}
    </>
  )
}

function trendIcon(d) { return d === 'up' ? '↑' : d === 'down' ? '↓' : '→' }
function Big({ n, l }) { return <div><div style={{ fontSize: 24, fontWeight: 800 }}>{n}</div><div style={{ fontSize: 11, opacity: .9 }}>{l}</div></div> }
function Bars({ data }) {
  const entries = Object.entries(data || {}).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...entries.map(([, v]) => v))
  if (!entries.length) return <div className="muted" style={{ fontSize: 13 }}>Nothing yet.</div>
  return entries.map(([k, v]) => (
    <div key={k} style={{ marginBottom: 8 }}>
      <div className="between" style={{ fontSize: 12.5 }}><span>{k}</span><span className="muted">{v}</span></div>
      <div style={{ height: 7, background: 'var(--bg-2)', borderRadius: 4 }}>
        <div style={{ width: `${(v / max) * 100}%`, height: '100%', background: 'var(--primary)', borderRadius: 4 }} />
      </div>
    </div>
  ))
}
