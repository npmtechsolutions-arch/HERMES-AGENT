import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { PageHead } from '../components/ui'

// Doc 26 Part 4.1 — simple, plain-language agent creation (everyone). No code,
// no tool-picking, no permissions UI. Aria infers SAFE tools from the
// description; anything sensitive auto-routes through approval. Advanced control
// (instructions, tools, delegation) is the Pro panel.
export default function AgentCreate() {
  const nav = useNavigate()
  const [a, setA] = useState({ description: '', name: '', cadence: 'on demand' })
  const [proposal, setProposal] = useState(null)
  const [busy, setBusy] = useState(false)

  const say = (t) => { try { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.speak(u) } catch {} }

  const propose = async () => {
    setBusy(true)
    try { const r = await api.post('/agents/simple/propose', a); setProposal(r); say(r.readback) }
    finally { setBusy(false) }
  }
  const create = async () => {
    setBusy(true)
    try { const r = await api.post('/agents/simple', a); say(r.message); nav('/my-agents') }
    finally { setBusy(false) }
  }

  return (
    <>
      <button className="btn sm ghost mb" onClick={() => nav('/my-agents')}>← My Agents</button>
      <PageHead title="Create your own agent" subtitle="Just describe what it should do — in plain words." />

      <div className="card">
        <Field label="What should this agent do?">
          <textarea rows={3} value={a.description} onChange={(e) => setA({ ...a, description: e.target.value })}
            placeholder="e.g. Watch deal sites and tell me about discounts on cameras." />
        </Field>
        <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Field label="What should I call it?"><input value={a.name} onChange={(e) => setA({ ...a, name: e.target.value })} placeholder="Deal Hunter" /></Field>
          <Field label="How often should it work?">
            <div className="tabs" style={{ margin: 0 }}>
              {['on demand', 'every morning', 'hourly', 'weekly'].map((c) => (
                <button key={c} className={a.cadence === c ? 'active' : ''} onClick={() => setA({ ...a, cadence: c })}>{c}</button>
              ))}
            </div>
          </Field>
        </div>
        <button className="btn" disabled={busy || !a.description.trim()} onClick={propose}>
          <Icon name="sparkles" size={14} /> Propose this agent
        </button>
      </div>

      {proposal && (
        <div className="card mt" style={{ borderTop: '3px solid var(--primary)' }}>
          <div style={{ fontSize: 14, marginBottom: 8 }}>🔊 {proposal.readback}</div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>It will be able to:</div>
          <div className="flex wrap" style={{ gap: 6, marginBottom: 10 }}>
            {proposal.tools.length === 0 && <span className="muted" style={{ fontSize: 12 }}>safe lookup tools</span>}
            {proposal.tools.map((t) => <span key={t} className="tag">{t.split('.').slice(-1)[0].replace(/_/g, ' ')}</span>)}
          </div>
          <div className="muted mb" style={{ fontSize: 11 }}>🔒 Sensitive actions (sending messages, anything about money) always ask you first — this agent can't do them on its own.</div>
          <div className="flex" style={{ gap: 8 }}>
            <button className="btn" disabled={busy} onClick={create}>Create agent</button>
            <button className="btn ghost" onClick={() => setProposal(null)}>Adjust</button>
          </div>
        </div>
      )}
    </>
  )
}

function Field({ label, children }) { return <div style={{ marginBottom: 12 }}><div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{label}</div>{children}</div> }
