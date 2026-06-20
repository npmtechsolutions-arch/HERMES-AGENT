import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Icon from './Icon'

// Doc 26 Part 1 — first-run guided setup. A voice-and-click overlay that ends in
// a REAL completed task (Step 4 calls the live assistant), never a dead form.
const TEAM = [
  { name: 'Aria', role: 'Chief of Staff — understands what you need', icon: 'sparkles' },
  { name: 'Scheduler', role: 'Reminders, calendar, routines', icon: 'clock' },
  { name: 'Inbox', role: 'Your messages & email', icon: 'inbox' },
  { name: 'Scribe', role: 'Writing, notes, documents', icon: 'scroll' },
  { name: 'Finder', role: 'Remembers things & looks them up', icon: 'brain' },
]

function say(text) {
  try {
    if (window.speechSynthesis) {
      const u = new SpeechSynthesisUtterance(text); u.lang = 'en-IN'
      window.speechSynthesis.cancel(); window.speechSynthesis.speak(u)
    }
  } catch {}
}

export default function FirstRunWizard() {
  const nav = useNavigate()
  const [st, setSt] = useState(null)
  const [hidden, setHidden] = useState(false)
  const [about, setAbout] = useState({ name: '', language: '', role: '' })
  const [taskText, setTaskText] = useState('Remind me to call the bank tomorrow at 11am.')
  const [taskResult, setTaskResult] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.get('/onboarding').then(setSt).catch(() => setSt({ completed: true })) }, [])
  useEffect(() => {
    if (!st || st.completed) return
    const k = STEP_KEY(st.step)
    if (k === 'welcome') say("Hi, I'm Aria, your chief of staff. I'll set things up in a couple of minutes. You can talk to me or type.")
    if (k === 'first_task') say("Let's do one thing together. Try saying: remind me to call the bank tomorrow at 11.")
  }, [st?.step])

  if (!st || st.completed || hidden) return null
  const stepKey = STEP_KEY(st.step)
  const goto = (step, skip_key) => api.post('/onboarding/nav', { step, skip_key }).then(setSt)
  const next = () => goto(st.step + 1)
  const skip = () => goto(st.step + 1, stepKey)
  const finish = async () => { await api.post('/onboarding/complete', {}); setHidden(true); window.location.assign('#/') }
  const skipAll = async () => { await api.post('/onboarding/complete', {}); setHidden(true) }

  const saveAbout = async () => {
    setBusy(true)
    try { const r = await api.post('/onboarding/about', about); say(r.message); setSt((s) => ({ ...s, step: Math.max(s.step, 3) })) }
    finally { setBusy(false) }
  }
  const runFirstTask = async (text) => {
    setBusy(true)
    try {
      const r = await api.post('/onboarding/first-task', { text })
      setTaskResult(r.result); say(r.result?.summary || 'Done — that\'s how everything works.')
      setSt((s) => ({ ...s, step: Math.max(s.step, 5) }))
      window.dispatchEvent(new Event('hermus-activity'))
    } finally { setBusy(false) }
  }

  return (
    <div style={OVERLAY}>
      <div className="card" style={PANEL}>
        <div className="between">
          <div className="flex" style={{ gap: 8, alignItems: 'center' }}>
            <Icon name="sparkles" size={18} /><strong>Guided setup</strong>
            <span className="muted" style={{ fontSize: 12 }}>Step {st.step} of {st.total}</span>
          </div>
          <button className="btn sm ghost" onClick={skipAll}>Skip setup</button>
        </div>
        <div style={{ height: 4, background: 'var(--bg-2)', borderRadius: 4, margin: '10px 0 16px' }}>
          <div style={{ width: `${(st.step / st.total) * 100}%`, height: '100%', background: 'var(--primary)', borderRadius: 4, transition: 'width .3s' }} />
        </div>

        {stepKey === 'welcome' && (
          <Step title="Hi, I'm Aria 👋" body="Your chief of staff. I'll set things up in a couple of minutes — you can talk to me or just type.">
            <div className="flex" style={{ gap: 8 }}>
              <button className="btn" onClick={next}>Let's go</button>
              <button className="btn ghost" onClick={skipAll}>Skip</button>
            </div>
          </Step>
        )}

        {stepKey === 'about' && (
          <Step title="A little about you" body="So I can personalise things. All optional.">
            <Field label="What should I call you?"><input value={about.name} onChange={(e) => setAbout({ ...about, name: e.target.value })} placeholder="Your name" /></Field>
            <Field label="Preferred language"><input value={about.language} onChange={(e) => setAbout({ ...about, language: e.target.value })} placeholder="English" /></Field>
            <Field label="What do you do? (optional)"><input value={about.role} onChange={(e) => setAbout({ ...about, role: e.target.value })} placeholder="e.g. freelance designer" /></Field>
            <div className="flex" style={{ gap: 8, marginTop: 4 }}>
              <button className="btn" disabled={busy} onClick={async () => { await saveAbout() }}>Save & continue</button>
              <button className="btn ghost" onClick={skip}>Skip</button>
            </div>
          </Step>
        )}

        {stepKey === 'team' && (
          <Step title="Meet your team" body="They're ready — you just ask, I assign.">
            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {TEAM.map((a) => (
                <div key={a.name} className="flex" style={{ gap: 8, alignItems: 'center', border: '1px solid var(--border)', borderRadius: 10, padding: '8px 10px' }}>
                  <Icon name={a.icon} size={16} />
                  <div><div style={{ fontWeight: 600, fontSize: 13 }}>{a.name}</div><div className="muted" style={{ fontSize: 11 }}>{a.role}</div></div>
                </div>
              ))}
            </div>
            <button className="btn mt" onClick={next}>Got it</button>
          </Step>
        )}

        {stepKey === 'first_task' && (
          <Step title="Let's do one thing together ✨" body="Type or say a command and watch an assistant actually do it.">
            <form onSubmit={(e) => { e.preventDefault(); runFirstTask(taskText) }} className="flex">
              <input value={taskText} onChange={(e) => setTaskText(e.target.value)} />
              <button className="btn" type="submit" disabled={busy}>Run it</button>
            </form>
            <button className="btn ghost sm mt" disabled={busy} onClick={() => runFirstTask(st.example_task)}>
              Or tap to run the example
            </button>
            {taskResult && (
              <div className="card mt" style={{ background: 'var(--bg-2)' }}>
                <div style={{ fontSize: 13.5 }}>🔊 {taskResult.summary}</div>
                <div className="muted" style={{ fontSize: 11, marginTop: 4 }}>Done by <strong>{taskResult.tool}</strong> — check your Activity log. That's how everything works.</div>
                <button className="btn mt" onClick={next}>Continue</button>
              </div>
            )}
          </Step>
        )}

        {stepKey === 'powerups' && (
          <Step title="Optional power-ups" body="All skippable — set up anytime later.">
            <Row icon="link" title="Connect email & calendar" desc="So I can read mail and book real events" action={() => { skipAll(); nav('/settings') }} cta="Connect" />
            <Row icon="play" title="Practice on pretend data" desc="Watch me work in Rehearsal first" action={() => { skipAll(); nav('/rehearsal') }} cta="Try it" />
            <Row icon="brain" title="Import contacts or notes" desc="I can learn them" action={() => { skipAll(); nav('/brain') }} cta="Import" />
            <button className="btn mt" onClick={next}>Continue</button>
          </Step>
        )}

        {stepKey === 'done' && (
          <Step title="You're all set 🎉" body="Tap the mic or just type any time. Say 'what can you do?' whenever you're not sure.">
            <button className="btn" onClick={finish}>Go to Home</button>
          </Step>
        )}
      </div>
    </div>
  )
}

const STEP_ORDER = ['welcome', 'about', 'team', 'first_task', 'powerups', 'done']
function STEP_KEY(step) { return STEP_ORDER[Math.max(0, Math.min(step - 1, STEP_ORDER.length - 1))] }

function Step({ title, body, children }) {
  return (
    <div>
      <h2 style={{ margin: '0 0 4px' }}>{title}</h2>
      <p className="muted" style={{ marginTop: 0, fontSize: 13.5 }}>{body}</p>
      {children}
    </div>
  )
}
function Field({ label, children }) {
  return <div style={{ marginBottom: 10 }}><div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{label}</div>{children}</div>
}
function Row({ icon, title, desc, action, cta }) {
  return (
    <div className="flex between" style={{ alignItems: 'center', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 12px', marginBottom: 8 }}>
      <div className="flex" style={{ gap: 8, alignItems: 'center' }}>
        <Icon name={icon} size={16} />
        <div><div style={{ fontWeight: 600, fontSize: 13 }}>{title}</div><div className="muted" style={{ fontSize: 11 }}>{desc}</div></div>
      </div>
      <button className="btn sm" onClick={action}>{cta}</button>
    </div>
  )
}

const OVERLAY = { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.45)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }
const PANEL = { width: 'min(560px, 96vw)', maxHeight: '90vh', overflowY: 'auto' }
