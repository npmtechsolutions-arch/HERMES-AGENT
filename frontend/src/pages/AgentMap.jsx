import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 26 Part 2 — the Agent Map. A friendly, live view of the user's team (for
// TRUST, not management). Aria (chief of staff) on top; the others below. Status
// dots stream from the agent.status WebSocket (re-broadcast by Layout). Clicking
// an agent opens its profile (Part 3, AgentProfile).
const STATUS = {
  idle: { label: 'Idle', cls: 'grey' }, working: { label: 'Working', cls: 'green' },
  waiting: { label: 'Waiting', cls: 'amber' }, reviewing: { label: 'Reviewing', cls: 'blue' },
  paused: { label: 'Paused', cls: 'grey' }, error: { label: 'Needs you', cls: 'red' },
  escalated: { label: 'Needs you', cls: 'red' }, completed: { label: 'Done', cls: 'green' },
}
const ICON = { Aria: 'sparkles', Scheduler: 'clock', Inbox: 'inbox', Scribe: 'scroll', Finder: 'brain' }

export default function AgentMap() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [agents, setAgents] = useState(null)
  const [tasks, setTasks] = useState([])
  const [view, setView] = useState('map')
  const [collab, setCollab] = useState(null)   // agentId briefly linked to Aria
  const collabTimer = useRef(null)

  const load = () => Promise.all([api.get('/agents'), api.get('/tasks').catch(() => [])])
    .then(([a, t]) => { setAgents(a); setTasks(t) })
  useEffect(() => { load() }, [])

  // live status: Layout re-broadcasts agent.status as a window event
  useEffect(() => {
    const onStatus = (e) => {
      const { id, name, status } = e.detail || {}
      setAgents((prev) => prev && prev.map((a) => ((a.id === id || a.name === name) ? { ...a, status } : a)))
      if (status === 'working') {
        const hit = (agents || []).find((a) => a.id === id || a.name === name)
        if (hit && !hit.is_ceo) {
          setCollab(hit.id); clearTimeout(collabTimer.current)
          collabTimer.current = setTimeout(() => setCollab(null), 2500)
        }
      }
    }
    window.addEventListener('hermus:agent-status', onStatus)
    return () => window.removeEventListener('hermus:agent-status', onStatus)
  }, [agents])

  // page voice handler: "who's busy", "what is <agent> doing"
  useEffect(() => {
    window.__myagentsVoice = (t) => {
      const speak = (x) => { try { const u = new SpeechSynthesisUtterance(x); u.lang = 'en-IN'; window.speechSynthesis.speak(u) } catch {} }
      const lower = t.toLowerCase()
      if (/who'?s busy|anyone busy|who is working/.test(lower)) {
        const busy = (agents || []).filter((a) => a.status === 'working')
        speak(busy.length ? `${busy.map((a) => a.name).join(', ')} ${busy.length === 1 ? 'is' : 'are'} working.` : 'Everyone is idle right now.')
        return true
      }
      const m = lower.match(/what (?:is|'s) (\w+) (?:doing|up to)/)
      if (m) {
        const a = (agents || []).find((x) => x.name.toLowerCase() === m[1])
        speak(a ? `${a.name} is ${STATUS[a.status]?.label || a.status}.${doingNow(a, tasks) ? ' ' + doingNow(a, tasks) : ''}` : `I couldn't find ${m[1]}.`)
        return true
      }
      return false
    }
    return () => { if (window.__myagentsVoice) delete window.__myagentsVoice }
  }, [agents, tasks])

  if (!agents) return <Loading />
  const aria = agents.find((a) => a.is_ceo || a.name === 'Aria') || agents[0]
  const team = agents.filter((a) => a !== aria)
  const open = (a) => nav('/my-agents/' + a.id)
  const focus = params.get('agent')

  return (
    <>
      <PageHead title="My Agents" subtitle="Your team — who they are, and what they're doing right now." />
      <div className="between mb">
        <div className="muted" style={{ fontSize: 13 }}>{agents.filter((a) => a.status === 'working').length} working now</div>
        <div className="tabs" style={{ margin: 0, maxWidth: 180 }}>
          {['map', 'list'].map((v) => <button key={v} className={view === v ? 'active' : ''} onClick={() => setView(v)}>{v}</button>)}
        </div>
      </div>

      {view === 'map' ? (
        <div className="card" style={{ padding: '26px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}>
            {aria && <AgentCard a={aria} chief onClick={() => open(aria)} doing={doingNow(aria, tasks)} focused={focus === aria.id} />}
          </div>
          <div style={{ height: 18, position: 'relative' }}>
            <div style={{ position: 'absolute', left: '50%', top: 0, width: 1, height: '100%', background: 'var(--border)' }} />
          </div>
          <div className="flex wrap" style={{ gap: 12, justifyContent: 'center' }}>
            {team.map((a) => (
              <div key={a.id} style={{ position: 'relative' }}>
                {collab === a.id && <span className="agent-collab" />}
                <AgentCard a={a} onClick={() => open(a)} doing={doingNow(a, tasks)} focused={focus === a.id} />
              </div>
            ))}
            <button className="card agent-create" onClick={() => nav('/my-agents/new')}
              style={{ width: 150, minHeight: 120, border: '1.5px dashed var(--primary)', background: 'transparent', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="plus" size={20} /><span style={{ fontSize: 12.5, fontWeight: 600 }}>Create your own agent</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="card">
          {[aria, ...team].filter(Boolean).map((a) => (
            <div key={a.id} className="flex between" style={{ alignItems: 'center', padding: '10px 4px', borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => open(a)}>
              <div className="flex" style={{ gap: 10, alignItems: 'center' }}>
                <Icon name={ICON[a.name] || 'bot'} size={17} />
                <div><div style={{ fontWeight: 600, fontSize: 13.5 }}>{a.name}{a.is_ceo ? ' · Chief of Staff' : ''}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{doingNow(a, tasks) || a.designation || roleOf(a.name)}</div></div>
              </div>
              <StatusPill status={a.status} />
            </div>
          ))}
        </div>
      )}
    </>
  )
}

function roleOf(name) {
  return { Aria: 'Understands what you need and assigns it', Scheduler: 'Reminders, calendar & routines',
    Inbox: 'Messages & email', Scribe: 'Writing, notes & documents', Finder: 'Memory & lookup' }[name] || 'Assistant'
}
function doingNow(a, tasks) {
  if (a.status !== 'working') return ''
  const t = (tasks || []).find((x) => x.assignee_agent_id === a.id && ['in_progress', 'working', 'executing'].includes(x.status))
  return t ? `Doing now: ${t.title}` : ''
}
function StatusPill({ status }) {
  const s = STATUS[status] || { label: status, cls: 'grey' }
  return <span className={'pill ' + s.cls} style={{ fontSize: 11 }}><span className="dot" />{s.label}</span>
}
function AgentCard({ a, chief, onClick, doing, focused }) {
  return (
    <button onClick={onClick} className="card agent-card"
      style={{ width: chief ? 220 : 150, minHeight: 120, cursor: 'pointer', textAlign: 'left', border: focused ? '2px solid var(--primary)' : (chief ? '2px solid var(--primary)' : '1px solid var(--border)'), display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div className="flex between" style={{ alignItems: 'center' }}>
        <Icon name={ICON[a.name] || 'bot'} size={18} /><StatusPill status={a.status} />
      </div>
      <div style={{ fontWeight: 700, fontSize: 14 }}>{a.name}</div>
      <div className="muted" style={{ fontSize: 11, lineHeight: 1.4 }}>{chief ? 'Chief of Staff' : (a.designation || roleOf(a.name))}</div>
      {doing && <div style={{ fontSize: 11, color: 'var(--primary)', marginTop: 2 }}>{doing}</div>}
    </button>
  )
}
