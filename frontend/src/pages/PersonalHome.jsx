import { Link } from 'react-router-dom'
import Icon from '../components/Icon'

// Doc 21 Part 13 — the HERMUS Personal home dashboard. "How is everything going?"
// at a glance: Needs you · In progress · Done today · Your agents · This week (ROI).
const DONE = ['done', 'completed', 'success', 'succeeded', 'sent']
const PROG = ['in_progress', 'running', 'active', 'executing', 'working', 'pending', 'queued', 'scheduled']
const dot = (s) => (DONE.includes(s) ? 'st-completed' : PROG.includes(s) ? 'st-online' : 'st-error')

export default function PersonalHome({ data, user, brand }) {
  const tasks = data?.tasks || []
  const agents = data?.agents || []
  const approvals = data?.approvals || []
  const roi = data?.roi?.week || data?.roi || {}
  const briefing = data?.briefing

  const isToday = (iso) => iso && new Date(iso).toDateString() === new Date().toDateString()
  const needs = tasks.filter((t) => ['waiting', 'needs_you', 'blocked', 'failed', 'needs_input'].includes(t.status))
  const inProg = tasks.filter((t) => PROG.includes(t.status))
  const doneToday = tasks.filter((t) => DONE.includes(t.status) && isToday(t.created_at))
  const hours = roi.hours_saved ?? roi.hoursSaved ?? 0
  const doneCount = roi.tasks_done ?? doneToday.length
  const hour = new Date().getHours()
  const greet = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <>
      <div className="between mb">
        <div>
          <h2 style={{ margin: 0 }}>{greet}{user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''} 👋</h2>
          <p className="muted" style={{ margin: '4px 0 0', fontSize: 13 }}>
            {brand || 'HERMUS Personal'} — here's what's happening.</p>
        </div>
        {briefing?.text && <button className="btn" onClick={() => {
          try { const u = new SpeechSynthesisUtterance(briefing.text); u.lang = 'en-IN'; speechSynthesis.cancel(); speechSynthesis.speak(u) } catch {}
        }}><Icon name="play" size={15} /> Play your briefing</button>}
      </div>

      {/* NEEDS YOU */}
      <div className="card mb" style={{ borderColor: (needs.length || approvals.length) ? 'var(--amber)' : undefined }}>
        <h3 style={{ marginTop: 0 }}><Icon name="bell" size={16} /> Needs you ({needs.length + approvals.length})</h3>
        {needs.length + approvals.length === 0 && <p className="muted" style={{ fontSize: 13, margin: 0 }}>You're all caught up. Nothing needs you right now. ✅</p>}
        {approvals.slice(0, 4).map((a) => (
          <div key={a.id} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 13 }}>{a.summary || a.title || 'An action needs your approval'}</span>
            <Link className="btn sm" to="/approvals">Review</Link>
          </div>
        ))}
        {needs.slice(0, 4).map((t) => (
          <div key={t.id} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ fontSize: 13 }}>{t.title}</span>
            <Link className="btn sm ghost" to="/tasks">Open</Link>
          </div>
        ))}
      </div>

      {/* IN PROGRESS · DONE TODAY */}
      <div className="grid cols-2 mb">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>⟳ In progress ({inProg.length})</h3>
          {inProg.length === 0 && <p className="muted" style={{ fontSize: 13 }}>Nothing running.</p>}
          {inProg.slice(0, 6).map((t) => (
            <div key={t.id} className="flex" style={{ gap: 8, padding: '6px 0', fontSize: 13, alignItems: 'center' }}>
              <span className={'pill ' + dot(t.status)} style={{ flex: '0 0 auto' }}><span className="dot" /></span>{t.title}</div>
          ))}
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>✓ Done today ({doneToday.length})</h3>
          {doneToday.length === 0 && <p className="muted" style={{ fontSize: 13 }}>Nothing completed yet today.</p>}
          {doneToday.slice(0, 6).map((t) => (
            <div key={t.id} className="flex" style={{ gap: 8, padding: '6px 0', fontSize: 13, color: 'var(--muted)' }}>✓ {t.title}</div>
          ))}
        </div>
      </div>

      {/* YOUR AGENTS */}
      <div className="card mb">
        <div className="between"><h3 style={{ marginTop: 0 }}><Icon name="users" size={16} /> Your agents</h3>
          <Link className="muted" style={{ fontSize: 12 }} to="/agent-team">Open My Agents →</Link></div>
        <div className="flex wrap" style={{ gap: 8 }}>
          {agents.slice(0, 8).map((a) => (
            <span key={a.id} className={'pill ' + dot(a.status)} title={a.designation || ''}>
              <span className="dot" />{a.name} · {a.status}</span>
          ))}
          {agents.length === 0 && <span className="muted" style={{ fontSize: 13 }}>Your team sets up when you activate the product.</span>}
        </div>
      </div>

      {/* THIS WEEK — ROI */}
      <div className="card" style={{ background: 'var(--grad)', color: '#fff', border: 'none' }}>
        <div className="between">
          <div>
            <div style={{ fontSize: 12, opacity: .9, textTransform: 'uppercase', letterSpacing: 1 }}>This week</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{doneCount} tasks done · ~{hours} hours saved</div>
          </div>
          <Link className="btn secondary" to="/analytics">Details</Link>
        </div>
        {data?.roi?.weekly_note && <p style={{ color: 'rgba(255,255,255,.92)', fontSize: 13, margin: '8px 0 0' }}>{data.roi.weekly_note}</p>}
      </div>
    </>
  )
}
