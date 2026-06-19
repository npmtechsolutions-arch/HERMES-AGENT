import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Icon from '../components/Icon'
import { Loading, Pill, Stat } from '../components/ui'
import PersonalHome from './PersonalHome'

export default function Home() {
  const nav = useNavigate()
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [ent, setEnt] = useState(null)
  const [demoBusy, setDemoBusy] = useState(false)

  const loadData = () =>
    Promise.all([
      api.get('/analytics/summary'), api.get('/tasks'),
      api.get('/approvals?state=pending'), api.get('/comms/threads?category=urgent'),
      api.get('/agents'), api.get('/roi/summary').catch(() => null),
      api.get('/backup/status').catch(() => null),
      api.get('/health/plain').catch(() => null),
      api.get('/briefing/daily').catch(() => null),
    ]).then(([summary, tasks, approvals, urgent, agents, roi, backup, health, briefing]) =>
      setData({ summary, tasks, approvals, urgent, agents, roi, backup, health, briefing }))

  const loadDemo = async () => {
    setDemoBusy(true)
    try { await api.post('/demo/bootstrap', {}); window.dispatchEvent(new Event('hermus:skin-changed')); nav('/guided-setup?from=demo') }
    finally { setDemoBusy(false) }
  }

  useEffect(() => { loadData(); api.get('/me/entitlements').then(setEnt).catch(() => {}) }, [])

  if (!data) return <Loading />
  // HERMUS Personal (and any edition shipping the simplified shell) gets the
  // Doc-21 personal dashboard instead of the business home.
  if (ent?.skin?.nav) return <PersonalHome data={data} user={user} brand={ent.skin.brand} />
  const { summary, tasks, approvals, urgent, agents, roi, backup, health, briefing } = data
  const busy = agents.filter((a) => a.status === 'working')
  const playBriefing = () => {
    if (!briefing || !window.speechSynthesis) return
    const u = new SpeechSynthesisUtterance(briefing.summary); u.lang = 'en-IN'
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(u)
  }

  return (
    <>
      <div className="hero">
        <h1>Welcome{user?.full_name && user.full_name !== 'User' ? `, ${user.full_name}` : ''} 👋</h1>
        {summary.agents === 0
          ? <p>Your company is ready to build. Start by setting up your company and letting
              AI staff your org — then create agents, pipelines and chatbots. Tap the orb or
              say “hire an employee”.</p>
          : <p>Your AI workforce is running. {approvals.length} approval{approvals.length !== 1 ? 's' : ''} await you,
              {' '}{busy.length} agent{busy.length !== 1 ? 's are' : ' is'} working now, and {summary.hours_saved} hours
              were saved this period. Tap the orb or say “give me my briefing”.</p>}
        <div className="hero-actions">
          {summary.agents === 0
            ? <>
                <button className="btn btn-glass" onClick={() => nav('/guided-setup')}>
                  <Icon name="rocket" size={16} /> Guide me step by step</button>
                <button className="btn btn-glass" onClick={loadDemo} disabled={demoBusy}>
                  <Icon name="sparkles" size={16} /> {demoBusy ? 'Setting up…' : 'Load a demo workspace'}</button>
                <button className="btn btn-glass" onClick={() => nav('/org')}>
                  <Icon name="plus" size={16} /> Hire an agent</button>
              </>
            : <>
                <button className="btn btn-glass" onClick={() => nav('/tasks')}>
                  <Icon name="plus" size={16} /> New task</button>
                <button className="btn btn-glass" onClick={() => nav('/approvals')}>
                  <Icon name="shield" size={16} /> Review approvals</button>
              </>}
        </div>
      </div>

      <div className="grid cols-4 mb">
        <Stat icon="users" label="Active agents" value={summary.agents} delta={`${busy.length} working now`} />
        <Stat icon="tasks" tint="blue" label="Tasks completed" value={summary.tasks_completed}
          delta={`${summary.success_rate}% success`} />
        <Stat icon="clock" tint="green" label="Hours saved" value={summary.hours_saved}
          delta={`≈ ₹${summary.cost_savings_inr.toLocaleString()} value`} />
        <Stat icon="workflow" tint="amber" label="Active workflows" value={summary.active_workflows} />
      </div>

      {summary.agents === 0 && (
        <div className="card mb">
          <h3><Icon name="check" size={17} /> Get started in 3 steps</h3>
          {[['Set up your company & industry', '/company', 'building'],
            ['Staff your AI org (or load a demo)', '/company?tab=suggest', 'users'],
            ['Build a pipeline and run your crew', '/pipelines', 'zap']].map(([label, to, ic], i) => (
            <div key={i} className="between" style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
              <div className="flex"><span className="stat-ico" style={{ width: 30, height: 30, borderRadius: 9 }}>
                <Icon name={ic} size={15} /></span><span style={{ fontSize: 14 }}>{label}</span></div>
              <button className="btn ghost sm" onClick={() => nav(to)}>Open →</button>
            </div>
          ))}
        </div>
      )}

      {health && (
        <div className="card mb" style={{ borderColor: health.ok ? 'var(--green)' : 'var(--amber)' }}>
          <div className="between">
            <div className="flex">
              <Icon name="shield" size={18} style={{ color: health.ok ? 'var(--green)' : 'var(--amber)' }} />
              <div><div style={{ fontWeight: 600, fontSize: 14 }}>Is everything okay? {health.ok ? '✅' : '⚠️'}</div>
                <div className="muted" style={{ fontSize: 13 }}>{health.simple}</div></div>
            </div>
            <div className="row-actions">
              {(health.actions || []).map((a) => <button key={a.to} className="btn secondary sm" onClick={() => nav(a.to)}>{a.text}</button>)}
            </div>
          </div>
        </div>
      )}

      {roi && roi.cumulative.minutes_saved > 0 && (
        <div className="card mb" style={{ background: 'var(--grad)', color: '#fff', border: 'none' }}>
          <div className="between">
            <div>
              <h3 style={{ color: '#fff', margin: 0 }}><Icon name="card" size={17} /> Your ROI this week</h3>
              <p style={{ color: 'rgba(255,255,255,.92)', fontSize: 14, margin: '8px 0 0', maxWidth: 720 }}>{roi.weekly_note}</p>
            </div>
            <Link to="/leads" className="btn btn-glass">View pipeline</Link>
          </div>
        </div>
      )}

      {backup && (
        <div className="card mb" style={{ borderColor: backup.stale_48h ? 'var(--red)' : 'var(--border)' }}>
          <div className="between">
            <div className="flex">
              <Icon name="shield" size={17} style={{ color: backup.stale_48h ? 'var(--red)' : 'var(--green)' }} />
              <span style={{ fontSize: 14 }}>{backup.stale_48h
                ? '⚠ Backup is stale — your business data is at risk. Set up a backup now.'
                : backup.summary} {backup.recovery_phrase_set ? '' : '· no recovery phrase set'}</span>
            </div>
            <Link to="/backup" className="btn secondary sm">Backup & Restore</Link>
          </div>
        </div>
      )}

      <div className="grid cols-2">
        <div className="card">
          <div className="between mb">
            <h3><Icon name="mic" size={17} /> Daily briefing</h3>
            <button className="btn secondary sm" onClick={playBriefing}><Icon name="play" size={13} /> Play</button>
          </div>
          {briefing
            ? <>
                <div style={{ fontSize: 14, lineHeight: 1.6 }}>🔊 {briefing.summary}</div>
                {briefing.anomalies.length > 0 && <div className="flex wrap mt" style={{ gap: 4 }}>
                  {briefing.anomalies.map((a, i) => <span key={i} className="tag" style={{ color: 'var(--amber)' }}>⚠ {a}</span>)}</div>}
                <div className="muted mt" style={{ fontSize: 11 }}>Delivered {briefing.schedule} · voice / WhatsApp / text</div>
              </>
            : <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.9, fontSize: 14 }}>
                <li>{approvals.length} approval(s) awaiting you</li>
                <li>{busy.length ? `${busy.map(a => a.name).join(', ')} working` : 'All agents idle'}</li>
              </ul>}
        </div>

        <div className="card">
          <div className="between mb"><h3><Icon name="shield" size={17} /> Pending approvals</h3>
            <Link to="/approvals" className="muted" style={{ fontSize: 12 }}>All →</Link></div>
          {approvals.length === 0 && <div className="muted">Nothing needs your sign-off.</div>}
          {approvals.map((a) => (
            <div key={a.id} className="between" style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize: 14 }}>{a.summary}</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  Tier: {a.current_tier} · Rule {a.rule_id}
                </div>
              </div>
              <Link to="/approvals" className="btn sm secondary">Review</Link>
            </div>
          ))}
        </div>

        <div className="card">
          <div className="between mb"><h3><Icon name="tasks" size={17} /> Recent tasks</h3>
            <Link to="/tasks" className="muted" style={{ fontSize: 12 }}>Board →</Link></div>
          {tasks.slice(0, 5).map((t) => (
            <div key={t.id} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 13 }}>{t.title}</div>
              <Pill status={t.status} />
            </div>
          ))}
        </div>

        <div className="card">
          <div className="between mb"><h3><Icon name="users" size={17} /> Live agent activity</h3>
            <Link to="/org" className="muted" style={{ fontSize: 12 }}>Org chart →</Link></div>
          {agents.map((a) => (
            <div key={a.id} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div className="flex">
                <div className="avatar" style={{ width: 28, height: 28, fontSize: 12 }}>
                  {a.name[0]}</div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{a.name}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{a.designation}</div>
                </div>
              </div>
              <Pill status={a.status} />
            </div>
          ))}
        </div>
      </div>
    </>
  )
}
