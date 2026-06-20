import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 26 Part 3 — Agent Profile. Overview / Doing now / Recent work / This week
// (plain-language summary from operational memory) / light Settings. Deep edits
// (tools, permissions, instructions) live in the Pro panel — not here.
const TABS = ['Overview', 'Doing now', 'Recent work', 'This week', 'Settings']

function say(t) { try { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } catch {} }

export default function AgentProfile() {
  const { id } = useParams()
  const nav = useNavigate()
  const [p, setP] = useState(null)
  const [tab, setTab] = useState('Overview')
  const [edit, setEdit] = useState(null)
  const [msg, setMsg] = useState('')

  const load = () => api.get(`/agents/${id}/profile`).then((x) => { setP(x); setEdit({ name: x.name, tone: x.tone, hours: x.hours, voice_id: x.voice_id }) })
  useEffect(() => { load() }, [id])

  // voice: "how has <agent> been doing"
  useEffect(() => {
    window.__agentprofileVoice = (t) => {
      if (/how (has|is).*(doing|been)|weekly|summary/i.test(t) && p) { say(p.this_week.phrase); return true }
      return false
    }
    return () => { if (window.__agentprofileVoice) delete window.__agentprofileVoice }
  }, [p])

  if (!p) return <Loading />
  const saveLight = async () => {
    const r = await api.post(`/agents/${id}/light-edit`, edit)
    setMsg('Saved.'); setTimeout(() => setMsg(''), 1500); load()
  }
  const toggle = async () => {
    await api.post(`/agents/${id}/${p.status === 'paused' ? 'resume' : 'pause'}`, {})
    load()
  }

  return (
    <>
      <button className="btn sm ghost mb" onClick={() => nav('/my-agents')}>← My Agents</button>
      <PageHead title={p.name} subtitle={p.is_ceo ? 'Chief of Staff' : p.role} />
      <div className="flex between mb" style={{ alignItems: 'center' }}>
        <span className={'pill ' + statusCls(p.status)}><span className="dot" />{p.status}</span>
        <button className="btn sm ghost" onClick={() => say(p.this_week.phrase)}><Icon name="play" size={13} /> How's it doing?</button>
      </div>

      <div className="tabs mb">{TABS.map((t) => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}</div>

      {tab === 'Overview' && (
        <div className="card">
          <p style={{ marginTop: 0 }}>{p.description || p.role}</p>
          <Row k="Status" v={p.status} /><Row k="Voice" v={p.voice_id} />
          <Row k="Tone" v={p.tone} /><Row k="Working hours" v={p.hours} />
        </div>
      )}

      {tab === 'Doing now' && (
        <div className="card">
          {p.doing_now ? <div style={{ fontSize: 14 }}>🟢 {p.doing_now}</div>
            : <div className="muted">Idle — nothing in progress right now.</div>}
        </div>
      )}

      {tab === 'Recent work' && (
        <div className="card">
          {p.recent.length === 0 && <div className="muted">No recent activity.</div>}
          {p.recent.map((r, i) => (
            <div key={i} className="flex between" style={{ padding: '8px 2px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: 13 }}>{r.summary}</div>
              <div className="muted" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{r.tool}</div>
            </div>
          ))}
        </div>
      )}

      {tab === 'This week' && (
        <div className="card">
          <div style={{ fontSize: 14, marginBottom: 10 }}>🔊 {p.this_week.phrase}</div>
          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <Stat n={p.this_week.actions} l="actions" />
            <Stat n={`~${p.this_week.minutes_saved}m`} l="saved" />
            <Stat n={p.this_week.waiting} l="waiting for you" />
          </div>
          {Object.keys(p.this_week.by_tool).length > 0 && (
            <div className="mt">
              {Object.entries(p.this_week.by_tool).map(([t, c]) => (
                <div key={t} className="flex between" style={{ fontSize: 12.5, padding: '4px 0' }}>
                  <span>{t.split('.').slice(-1)[0].replace(/_/g, ' ')}</span><span className="muted">{c}×</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'Settings' && (
        <div className="card">
          <div className="muted mb" style={{ fontSize: 12 }}>Light edits — safe and instant. Tools, permissions and instructions are a Pro feature.</div>
          <Field label="Name"><input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
          <Field label="Tone">
            <div className="tabs" style={{ margin: 0, maxWidth: 260 }}>
              {['friendly', 'formal', 'concise'].map((x) => <button key={x} className={edit.tone === x ? 'active' : ''} onClick={() => setEdit({ ...edit, tone: x })}>{x}</button>)}
            </div>
          </Field>
          <Field label="Working hours"><input value={edit.hours} onChange={(e) => setEdit({ ...edit, hours: e.target.value })} placeholder="e.g. 9–6, anytime" /></Field>
          <Field label="Voice"><input value={edit.voice_id} onChange={(e) => setEdit({ ...edit, voice_id: e.target.value })} /></Field>
          <div className="flex" style={{ gap: 8 }}>
            <button className="btn" onClick={saveLight}>Save</button>
            <button className="btn ghost" onClick={toggle}>{p.status === 'paused' ? 'Resume' : 'Pause'}</button>
            {msg && <span className="muted" style={{ alignSelf: 'center', fontSize: 12 }}>{msg}</span>}
          </div>
          <div className="muted mt" style={{ fontSize: 11 }}>🔒 Locked safety rules always apply — even Pro can't let an agent move money or message new contacts without your approval.</div>
        </div>
      )}
    </>
  )
}

function statusCls(s) { return { working: 'green', paused: 'grey', idle: 'grey', error: 'red', escalated: 'red', waiting: 'amber' }[s] || 'grey' }
function Row({ k, v }) { return <div className="flex between" style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}><span className="muted" style={{ fontSize: 12.5 }}>{k}</span><span style={{ fontSize: 13 }}>{v || '—'}</span></div> }
function Field({ label, children }) { return <div style={{ marginBottom: 12 }}><div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>{label}</div>{children}</div> }
function Stat({ n, l }) { return <div style={{ textAlign: 'center', padding: 10, background: 'var(--bg-2)', borderRadius: 10 }}><div style={{ fontSize: 20, fontWeight: 700 }}>{n}</div><div className="muted" style={{ fontSize: 11 }}>{l}</div></div> }
