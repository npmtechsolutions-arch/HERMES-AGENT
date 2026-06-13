import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead } from '../components/ui'

const TINT = { violet: 'var(--primary)', blue: '#2f6bff', amber: 'var(--amber)', green: 'var(--green)', red: 'var(--red)' }
const COLORS = ['violet', 'blue', 'amber', 'green', 'red']

export default function AgentTeam() {
  const [team, setTeam] = useState(null)
  const [roster, setRoster] = useState(null)
  const [tab, setTab] = useState(() => new URLSearchParams(location.search).get('tab') || 'test')
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const [pending, setPending] = useState(null)
  const [testReq, setTestReq] = useState(null)
  const [form, setForm] = useState(null)        // { role } for new, or { agent } for edit
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), kind === 'ask' ? 12000 : 7000) }
  const speak = (t, after) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) { after && after(); return }
    const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'
    u.onend = () => after && after(); u.onerror = () => after && after()
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(u)
  }
  const reload = () => Promise.all([api.get('/agentsphere/team'), api.get('/agentsphere/roster')])
    .then(([t, r]) => { setTeam(t); setRoster(r) }).catch(() => { setTeam({ specialists: [] }); setRoster({ agents: [] }) })
  useEffect(() => { reload() }, [])

  const deployTeam = async () => {
    try { const r = await api.post('/agentsphere/deploy-demo'); flash('ok', r.message); speak('Customer team deployed.'); await reload(); setTab('test') }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not deploy the team.') }
  }
  const undeployTeam = async (confirmFirst) => {
    if (confirmFirst && !window.confirm('Remove the whole customer team and its conversations?')) return
    try { const r = await api.post('/agentsphere/undeploy-demo'); flash('ok', r.message); speak('Team removed.'); await reload(); setTab('test') }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not remove the team.') }
  }
  const createAgent = async (payload) => { const r = await api.post('/agentsphere/agents', payload); flash('ok', r.message); await reload(); return r }
  const saveAgent = async (aid, payload) => { const r = await api.patch(`/agentsphere/agents/${aid}`, payload); flash('ok', r.message); await reload(); return r }
  const publishAgent = async (aid, pub, name) => {
    try { const r = await api.post(`/agentsphere/agents/${aid}/${pub ? 'publish' : 'unpublish'}`); flash('ok', r.message); await reload() }
    catch (e) { flash('err', e?.message || `Could not ${pub ? 'publish' : 'unpublish'} ${name}.`) }
  }
  const deleteAgent = async (aid, name) => {
    if (!window.confirm(`Remove “${name}” from the team?`)) return
    try { const r = await api.del(`/agentsphere/agents/${aid}`); flash('ok', r.message); await reload() }
    catch (e) { flash('err', e?.message || 'Could not remove the agent.') }
  }

  const runCommand = async (text, carry) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const src = carry !== undefined ? carry : pending
      const safe = src && src.need ? { need: src.need } : null
      const r = await api.post('/agentsphere/resolve', { transcript: phrase, pending: safe })
      if (r.action === 'clarify') { setPending(r.pending || { need: r.need }); flash('ask', r.message); speak(r.message, () => startListening(r.pending || { need: r.need })); return }
      setPending(null)
      switch (r.action) {
        case 'deploy_team': await deployTeam(); break
        case 'undeploy_team': await undeployTeam(false); break
        case 'add_agent': await createAgent({ name: r.name, role: r.role, capabilities: r.capabilities || [] }); setTab('team'); speak(`Added ${r.name}.`); break
        case 'publish_agent': await publishAgent(r.aid, r.publish, r.name); setTab('team'); break
        case 'delete_agent': { try { const x = await api.del(`/agentsphere/agents/${r.aid}`); flash('ok', x.message); await reload(); setTab('team') } catch (e) { flash('err', e?.message) } } break
        case 'build': setTab('team'); setForm({ role: 'specialist' }); flash('ok', 'Opening the team builder.'); break
        case 'tab': setTab(r.tab); flash('ok', `Opened ${r.tab}.`); break
        case 'test': setTab('test'); setTestReq({ message: r.message, run: Date.now() }); break
        case 'persona': setTab('test'); setTestReq({ message: r.opening, run: Date.now() }); flash('ok', `Running ${r.name}.`); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { setPending(null); const m = e?.detail?.message || e?.message || 'Could not run that command.'; flash('err', m); speak('Sorry, ' + m) }
  }
  useEffect(() => { window.__agentteamVoice = (t) => { runCommand(t); return true }; return () => { if (window.__agentteamVoice) delete window.__agentteamVoice } })

  const startListening = (carry) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t, carry !== undefined ? carry : pending) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!team || !roster) return <Loading />
  const hasAny = (roster.agents || []).length > 0

  const VoiceBar = (
    <>
      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : pending ? '…your answer'
              : hasAny ? 'Say or type: "add a billing specialist", "ask the team why was I charged twice", "publish the billing agent", "open the human inbox"'
                : 'Say or type: "deploy the team" or "build my own team"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : msg.kind === 'ask' ? 'var(--primary)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : msg.kind === 'ask' ? '🎤 ' : '⚠ '}{msg.text}</div>}
    </>
  )

  if (!hasAny) return (
    <>
      <PageHead title="Agent Team" sub="A team of specialist AI agents that talk to your customers — and to each other. Deploy a ready-made team, or build your own." />
      {VoiceBar}
      <div className="grid cols-2">
        <div className="card" style={{ textAlign: 'center', padding: 30 }}>
          <div style={{ fontSize: 36 }}>⚡</div><h3>Deploy a demo team</h3>
          <p className="muted" style={{ fontSize: 13 }}>A ready-made Front Desk router + Reservations, Billing and Support specialists, with sample knowledge. Best for a quick look.</p>
          <button className="btn" onClick={deployTeam}><Icon name="sparkles" size={15} /> Deploy demo team</button>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 30 }}>
          <div style={{ fontSize: 36 }}>🛠️</div><h3>Build your own</h3>
          <p className="muted" style={{ fontSize: 13 }}>Add your own specialists, give each its capabilities (the intents it owns), knowledge scope and confidence threshold, then publish.</p>
          <button className="btn secondary" onClick={() => { setTab('team'); setForm({ role: 'specialist' }) }}><Icon name="plus" size={15} /> Add a specialist</button>
        </div>
      </div>
      {form && <AgentForm form={form} roster={roster} onClose={() => setForm(null)}
        onCreate={createAgent} onSave={saveAgent} onFlash={flash} />}
    </>
  )

  return (
    <>
      <PageHead title="Agent Team"
        sub="A manager agent routes each customer to the right specialist — and specialists consult each other. Build your own, or deploy a demo. Grounded, governed, one tap from a human.">
        <button className="btn ghost sm" onClick={() => undeployTeam(true)}><Icon name="x" size={13} /> Reset team</button>
      </PageHead>
      {VoiceBar}
      <div className="tabs mb" style={{ maxWidth: 520 }}>
        {[['test', 'Test chat'], ['team', 'Team & builder'], ['inbox', 'Human inbox'], ['personas', 'Adversarial']].map(([k, l]) => (
          <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === 'test' && <TestChat team={team} testReq={testReq} speak={speak} />}
      {tab === 'team' && <Builder roster={roster} team={team} onForm={setForm} onPublish={publishAgent} onDelete={deleteAgent} />}
      {tab === 'inbox' && <Inbox onFlash={flash} />}
      {tab === 'personas' && <Personas onRun={(p) => { setTab('test'); setTestReq({ message: p.opening, run: Date.now() }) }} />}
      {form && <AgentForm form={form} roster={roster} onClose={() => setForm(null)}
        onCreate={createAgent} onSave={saveAgent} onFlash={flash} />}
    </>
  )
}

/* ── Team builder ─────────────────────────────────────────────────────────── */
function Builder({ roster, team, onForm, onPublish, onDelete }) {
  const agents = roster.agents || []
  const hasManager = agents.some((a) => a.role === 'manager')
  return (
    <>
      <div className="between mb">
        <div className="flex" style={{ fontSize: 13 }}><Icon name="users" size={15} />
          <strong>Your team</strong><span className="muted">— {agents.filter((a) => a.published).length} published · {agents.filter((a) => !a.published).length} draft</span></div>
        <div className="flex" style={{ gap: 6 }}>
          {!hasManager && <button className="btn ghost sm" onClick={() => onForm({ role: 'manager' })}><Icon name="plus" size={13} /> Manager</button>}
          <button className="btn sm" onClick={() => onForm({ role: 'specialist' })}><Icon name="plus" size={14} /> Add specialist</button>
        </div>
      </div>

      <div className="grid cols-3 mb">
        {agents.map((a) => (
          <div className="card" key={a.id} style={{ opacity: a.published ? 1 : 0.7, borderStyle: a.published ? 'solid' : 'dashed' }}>
            <div className="between mb">
              <div className="flex">
                <div className="avatar" style={{ background: TINT[a.color] || 'var(--primary)' }}>{a.name[0]}</div>
                <div><h3 style={{ margin: 0, fontSize: 15 }}>{a.name}</h3>
                  <div className="muted" style={{ fontSize: 11 }}>{a.role === 'manager' ? 'Manager · router' : 'Specialist'} · v{a.version}</div></div>
              </div>
              <span className="tag" style={{ fontSize: 10, color: a.published ? 'var(--green)' : 'var(--amber)' }}>{a.published ? '🟢 published' : '🟡 draft'}</span>
            </div>
            <div style={{ fontSize: 12.5, marginBottom: 8 }}>{a.purpose}</div>
            <div className="flex wrap mb" style={{ gap: 4 }}>
              {(a.capabilities || []).map((c) => <span key={c} className="tag" style={{ fontSize: 10 }}>{c}</span>)}
              {a.role === 'manager' && !(a.capabilities || []).length && <span className="tag" style={{ fontSize: 10 }}>routes all intents</span>}
            </div>
            <div className="muted mb" style={{ fontSize: 11 }}>
              handoff &lt; {a.confidence_threshold} · {a.can_delegate ? 'can consult peers' : 'no delegation'} · knows {(a.memory_scopes || []).join(', ') || '—'}</div>
            <div className="flex wrap" style={{ gap: 6 }}>
              <button className="btn ghost sm" onClick={() => onForm({ agent: a })}><Icon name="settings" size={12} /> Edit</button>
              {a.published
                ? <button className="btn ghost sm" onClick={() => onPublish(a.id, false, a.name)}>Unpublish</button>
                : <button className="btn sm" onClick={() => onPublish(a.id, true, a.name)}>Publish</button>}
              <button className="icon-btn" style={{ width: 30, height: 30 }} title="Remove" onClick={() => onDelete(a.id, a.name)}><Icon name="x" size={13} /></button>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}><Icon name="workflow" size={15} /> Routing matrix <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>— which intents go where (published only)</span></h3>
        {(team.routing_matrix || []).length === 0
          ? <div className="muted" style={{ fontSize: 13 }}>No published specialists with capabilities yet. Add capabilities to a specialist and publish it.</div>
          : <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead><tr style={{ textAlign: 'left', color: 'var(--muted)' }}><th style={{ padding: 6 }}>Capability</th><th>Specialist</th><th>Test utterance</th></tr></thead>
              <tbody>{team.routing_matrix.map((m, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                  <td style={{ padding: 6 }}><span className="tag" style={{ fontSize: 10 }}>{m.capability}</span></td>
                  <td>{m.agent}</td><td className="muted">“{m.test_utterance}”</td></tr>))}</tbody>
            </table>}
        {roster.budget && <div className="muted mt" style={{ fontSize: 12 }}>
          Containment: max delegation depth {roster.budget.max_depth} · {roster.budget.hop_budget} hops/turn ·
          {roster.budget.token_budget} token budget · ${roster.budget.cost_per_1k}/1k tokens. Enforced before each model call.</div>}
      </div>
    </>
  )
}

/* ── Create / edit a team agent ───────────────────────────────────────────── */
function AgentForm({ form, roster, onClose, onCreate, onSave, onFlash }) {
  const editing = !!form.agent
  const a = form.agent
  const hasManager = (roster.agents || []).some((x) => x.role === 'manager')
  const [f, setF] = useState({
    name: a?.name || '', role: a?.role || form.role || 'specialist', purpose: a?.purpose || '',
    persona: a?.persona || '', capabilities: a?.capabilities || [], memory_scopes: a?.memory_scopes || ['knowledge', 'business'],
    confidence_threshold: a?.confidence_threshold ?? 0.55, can_delegate: a?.can_delegate ?? true,
    color: a?.color || 'blue', published: a?.published ?? true,
  })
  const [capInput, setCapInput] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setF({ ...f, [k]: v })
  const addCap = (c) => { const v = (c || '').trim().toLowerCase(); if (v && !f.capabilities.includes(v)) setF({ ...f, capabilities: [...f.capabilities, v] }); setCapInput('') }
  const rmCap = (c) => setF({ ...f, capabilities: f.capabilities.filter((x) => x !== c) })
  const toggleScope = (s) => setF({ ...f, memory_scopes: f.memory_scopes.includes(s) ? f.memory_scopes.filter((x) => x !== s) : [...f.memory_scopes, s] })
  const canBeManager = f.role === 'manager' || (!hasManager || (editing && a.role === 'manager'))

  const submit = async () => {
    setBusy(true)
    try {
      const payload = { name: f.name, role: f.role, purpose: f.purpose || undefined, persona: f.persona || undefined,
        capabilities: f.capabilities, memory_scopes: f.memory_scopes, confidence_threshold: Number(f.confidence_threshold),
        can_delegate: f.can_delegate, color: f.color, published: f.published }
      if (editing) await onSave(a.id, payload); else await onCreate(payload)
      onClose()
    } catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not save the agent.') }
    finally { setBusy(false) }
  }

  return (
    <Modal title={editing ? `Edit ${a.name}` : 'Add a team agent'} onClose={onClose}>
      <div className="grid cols-2" style={{ gap: 12 }}>
        <div className="field"><label>Name</label><input value={f.name} onChange={(e) => set('name', e.target.value)} placeholder="e.g. Billing Agent" autoFocus /></div>
        <div className="field"><label>Role</label>
          <select value={f.role} onChange={(e) => set('role', e.target.value)} disabled={editing && a.role === 'manager'}>
            <option value="specialist">Specialist</option>
            {(hasManager ? (editing && a.role === 'manager') : true) && <option value="manager">Manager (router)</option>}
          </select></div>
      </div>
      <div className="field"><label>What it handles (purpose)</label><input value={f.purpose} onChange={(e) => set('purpose', e.target.value)} placeholder="e.g. Billing, invoices, refunds" /></div>

      {f.role === 'specialist' && <>
        <div className="field"><label>Capabilities / intents it owns</label>
          <div className="flex wrap mb" style={{ gap: 4 }}>
            {f.capabilities.map((c) => <span key={c} className="tag" style={{ cursor: 'pointer' }} onClick={() => rmCap(c)}>{c} ✕</span>)}
          </div>
          <div className="flex"><input value={capInput} onChange={(e) => setCapInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCap(capInput) } }} placeholder="type an intent + Enter (e.g. refund)" />
            <button className="btn ghost sm" onClick={() => addCap(capInput)}>Add</button></div>
          <div className="flex wrap mt" style={{ gap: 4 }}>
            {(roster.capability_suggestions || []).filter((c) => !f.capabilities.includes(c)).slice(0, 12).map((c) =>
              <span key={c} className="tag" style={{ cursor: 'pointer', opacity: 0.7 }} onClick={() => addCap(c)}>+ {c}</span>)}
          </div>
        </div>
      </>}

      <div className="field"><label>Knowledge it can read</label>
        <div className="flex wrap">{(roster.knowledge_scopes || ['business', 'knowledge', 'personal', 'operational']).map((s) => (
          <label key={s} className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={f.memory_scopes.includes(s)} style={{ width: 16 }} onChange={() => toggleScope(s)} /> {s}</label>))}</div></div>

      <div className="grid cols-2" style={{ gap: 12 }}>
        <div className="field"><label>Hand off below confidence ({f.confidence_threshold})</label>
          <input type="range" min="0.3" max="0.9" step="0.05" value={f.confidence_threshold} onChange={(e) => set('confidence_threshold', e.target.value)} /></div>
        <div className="field"><label>Delegation</label>
          <label className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer', paddingTop: 8 }}>
            <input type="checkbox" checked={f.can_delegate} style={{ width: 16 }} onChange={(e) => set('can_delegate', e.target.checked)} /> can consult peers</label></div>
      </div>

      <div className="field"><label>Persona / instructions (optional)</label>
        <textarea rows={2} value={f.persona} onChange={(e) => set('persona', e.target.value)} placeholder="Leave blank for a sensible default." /></div>

      <div className="between">
        <div className="flex" style={{ gap: 6 }}>{COLORS.map((c) => (
          <button key={c} onClick={() => set('color', c)} style={{ width: 26, height: 26, borderRadius: 8, background: TINT[c], border: f.color === c ? '2px solid var(--text)' : 'none', cursor: 'pointer' }} />))}</div>
        <label className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer' }}>
          <input type="checkbox" checked={f.published} style={{ width: 16 }} onChange={(e) => set('published', e.target.checked)} /> publish (live)</label>
      </div>
      <button className="btn mt" style={{ width: '100%' }} onClick={submit} disabled={!f.name || busy}>
        {busy ? 'Saving…' : editing ? 'Save changes' : 'Add to team'}</button>
    </Modal>
  )
}

/* ── Live multi-agent test chat with transparency ─────────────────────────── */
function TestChat({ team, testReq, speak }) {
  const [msgs, setMsgs] = useState([])
  const [input, setInput] = useState('')
  const [conv, setConv] = useState(null)
  const [busy, setBusy] = useState(false)
  const endRef = useRef(null)
  const convRef = useRef(null); convRef.current = conv
  const published = (team.manager ? 1 : 0) + (team.specialists || []).length
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  const send = async (text) => {
    const q = (text ?? input).trim()
    if (!q || busy) return
    setInput(''); setMsgs((m) => [...m, { role: 'user', body: q }]); setBusy(true)
    try {
      const r = await api.post('/agentsphere/converse', { message: q, conversation_id: convRef.current })
      setConv(r.conversation_id)
      setMsgs((m) => [...m, { role: 'assistant', body: r.response, trace: r.trace, routed_to: r.routed_to, escalated: r.escalated }])
      speak && speak(r.response)
    } catch (e) {
      setMsgs((m) => [...m, { role: 'assistant', body: '⚠ ' + (e?.detail?.message || e?.message || 'failed'), error: true }])
    } finally { setBusy(false) }
  }
  useEffect(() => { if (testReq?.message) send(testReq.message) }, [testReq?.run])

  const starters = ['Why was I charged twice this month?', 'Can I book a table for 4 tomorrow at 8pm?',
    'I want to change my reservation AND ask why my bill was so high', 'Just connect me to a human']

  return (
    <div className="card" style={{ minHeight: 360, display: 'flex', flexDirection: 'column' }}>
      {published === 0 && <div className="card mb" style={{ borderColor: 'var(--amber)', fontSize: 13 }}>
        ⚠ No published agents yet — add a specialist in <strong>Team &amp; builder</strong> and publish it, then test here.</div>}
      <div style={{ flex: 1, overflowY: 'auto', maxHeight: 460 }}>
        {!msgs.length && (
          <div className="muted" style={{ textAlign: 'center', padding: 24 }}>
            <div style={{ marginBottom: 10 }}>Talk to your team like a customer would (type, voice, or the orb). You'll see exactly how it routed.</div>
            <div className="flex wrap" style={{ justifyContent: 'center', gap: 6 }}>
              {starters.map((s) => <button key={s} className="tag" style={{ cursor: 'pointer' }} onClick={() => send(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => <Bubble key={i} m={m} />)}
        {busy && <div className="muted" style={{ fontSize: 13, padding: 6 }}>🧠 routing…</div>}
        <div ref={endRef} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); send() }} className="flex mt">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type a customer message…" />
        <button className="btn" type="submit" disabled={busy}><Icon name="send" size={14} /> {busy ? '…' : 'Send'}</button>
      </form>
    </div>
  )
}

function Bubble({ m }) {
  if (m.role === 'user')
    return <div style={{ textAlign: 'right', margin: '8px 0' }}>
      <span style={{ background: 'var(--primary)', color: '#fff', padding: '8px 12px', borderRadius: 12, display: 'inline-block', maxWidth: '78%' }}>{m.body}</span></div>
  return (
    <div style={{ margin: '8px 0' }}>
      {m.routed_to && <div className="muted" style={{ fontSize: 11, marginBottom: 3 }}>
        <Icon name="chat" size={11} /> {m.routed_to}{m.escalated && ' · handed to a human'}</div>}
      <span style={{ background: 'var(--surface-2, #f3f2fa)', padding: '8px 12px', borderRadius: 12, display: 'inline-block', maxWidth: '82%' }}>{m.body}</span>
      {m.trace && <TraceView t={m.trace} />}
    </div>
  )
}

function TraceView({ t }) {
  const [open, setOpen] = useState(false)
  const r = t.routing || {}
  return (
    <div className="card" style={{ marginTop: 6, padding: 10, background: 'var(--grad-soft)' }}>
      <div className="between" style={{ cursor: 'pointer' }} onClick={() => setOpen((o) => !o)}>
        <div className="flex wrap" style={{ gap: 5, fontSize: 11.5 }}>
          {r.to && <span className="tag">→ {r.to}{r.rerouted ? ' (re-routed)' : ''}</span>}
          {r.consulted && <span className="tag" style={{ color: 'var(--primary)' }}>🤝 consulted {r.consulted}</span>}
          <span className="tag" style={{ color: t.grounded ? 'var(--green)' : 'var(--amber)' }}>{t.grounded ? '✓ grounded' : '⚠ ungrounded'}</span>
          <span className="tag">conf {r.confidence}</span>
          <span className="tag">{t.hops} hops · ${t.cost}</span>
          {t.input_guardrails?.length > 0 && <span className="tag" style={{ color: 'var(--red)' }}>🛡️ injection blocked</span>}
          {t.handoff && <span className="tag" style={{ color: 'var(--red)' }}>👤 {t.handoff.reason}</span>}
        </div>
        <Icon name={open ? 'x' : 'search'} size={12} />
      </div>
      {open && (
        <div style={{ marginTop: 8, fontSize: 12 }}>
          {r.reason && <div className="muted" style={{ marginBottom: 6 }}>Router: “{r.reason}”</div>}
          {t.internal_thread?.length > 0 && (
            <div style={{ borderLeft: '2px solid var(--primary)', paddingLeft: 8, margin: '6px 0' }}>
              <div style={{ fontWeight: 600, marginBottom: 3 }}>Internal agent dialogue</div>
              {t.internal_thread.map((it, i) => (
                <div key={i} style={{ padding: '2px 0' }}>
                  <span className="tag" style={{ fontSize: 10 }}>{it.kind}</span> <strong>{it.from}</strong> → <strong>{it.to}</strong>: {it.text}
                  <span className="muted"> (${it.cost})</span>
                </div>
              ))}
            </div>
          )}
          {t.citations?.length > 0 && <div style={{ marginTop: 4 }}>📎 {t.citations.map((c) => c.title).join(', ')}</div>}
          {t.budget && <div className="muted" style={{ marginTop: 6 }}>
            Budget: {t.budget.hops_used}/{t.budget.hop_budget} hops · {t.budget.tokens_used}/{t.budget.token_budget} tokens ·
            depth≤{t.budget.max_depth} {t.budget.within ? '· within limits' : '· capped'}</div>}
        </div>
      )}
    </div>
  )
}

/* ── Human inbox (escalations) ────────────────────────────────────────────── */
function Inbox({ onFlash }) {
  const [rows, setRows] = useState(null)
  const [active, setActive] = useState(null)
  const load = () => api.get('/agentsphere/escalations').then(setRows).catch(() => onFlash('err', 'Could not load the inbox.'))
  useEffect(() => { load() }, [])
  if (!rows) return <Loading />
  if (!rows.length) return <div className="card" style={{ textAlign: 'center', padding: 30 }}>
    <div style={{ fontSize: 30 }}>📭</div><p className="muted">No escalations. When an agent is unsure or a customer asks for a human, it lands here.</p></div>

  const REASON = { low_confidence: '🤔 low confidence', asked_for_human: '🙋 asked for human', ungrounded: '📭 no knowledge', guardrail: '🛡️ guardrail', misroute: '🔀 misroute' }
  return (
    <>
      <div className="grid cols-2">
        {rows.map((e) => (
          <div className="card" key={e.id} style={{ borderColor: e.overdue ? 'var(--red)' : undefined }}>
            <div className="between mb">
              <span className="tag">{REASON[e.reason] || e.reason}</span>
              <span className="pill" style={{ color: e.status === 'resolved' ? 'var(--green)' : e.overdue ? 'var(--red)' : 'var(--amber)' }}>
                <span className="dot" /> {e.status}{e.overdue && e.status !== 'resolved' ? ' · SLA overdue' : ''}</span>
            </div>
            <div style={{ fontSize: 13, marginBottom: 6 }}>{e.summary}</div>
            <button className="btn ghost sm" onClick={() => setActive(e)}>Open conversation</button>
          </div>
        ))}
      </div>
      {active && <EscModal e={active} onClose={() => { setActive(null); load() }} onFlash={onFlash} />}
    </>
  )
}

function EscModal({ e, onClose, onFlash }) {
  const [reply, setReply] = useState(e.suggested_reply || '')
  const [resume, setResume] = useState('')
  const [e2, setE2] = useState(e)
  const [busy, setBusy] = useState(false)
  const claim = async () => {
    try { setE2(await api.post(`/agentsphere/escalations/${e.id}/claim`)); onFlash('ok', 'Escalation claimed.') }
    catch (err) { onFlash('err', err?.message || 'Could not claim.') }
  }
  const resolve = async () => {
    setBusy(true)
    try { const r = await api.post(`/agentsphere/escalations/${e.id}/resolve`, { reply, resume_instructions: resume }); onFlash('ok', r.message || 'Resolved.'); onClose() }
    catch (err) { onFlash('err', err?.message || 'Could not resolve.') }
    finally { setBusy(false) }
  }
  return (
    <Modal title="Human handoff" onClose={onClose}>
      <div className="card" style={{ maxHeight: 200, overflowY: 'auto', marginBottom: 10 }}>
        {(e2.transcript || []).map((m, i) => (
          <div key={i} style={{ margin: '4px 0', fontSize: 13 }}>
            <span className="tag" style={{ fontSize: 10 }}>{m.role}</span> {m.body}</div>))}
      </div>
      <div className="muted mb" style={{ fontSize: 12 }}>Reason: {e2.reason} · {e2.status}{e2.claimed_by ? ' · claimed' : ''}</div>
      {e2.status !== 'resolved' && (
        <>
          {e2.status === 'queued' && <button className="btn ghost sm mb" onClick={claim}>Claim</button>}
          <label className="muted" style={{ fontSize: 12 }}>Reply to customer (AI-drafted)</label>
          <textarea value={reply} onChange={(ev) => setReply(ev.target.value)} rows={3} style={{ width: '100%', marginBottom: 8 }} />
          <label className="muted" style={{ fontSize: 12 }}>Return-to-AI instructions (optional)</label>
          <input value={resume} onChange={(ev) => setResume(ev.target.value)} placeholder='e.g. "Billing resolved, resume upsell flow"' style={{ width: '100%', marginBottom: 10 }} />
          <button className="btn" style={{ width: '100%' }} onClick={resolve} disabled={!reply.trim() || busy}>{busy ? 'Sending…' : 'Send & resolve'}</button>
        </>
      )}
      {e2.status === 'resolved' && <div className="pill st-active"><span className="dot" /> Resolved</div>}
    </Modal>
  )
}

/* ── Adversarial sandbox personas ─────────────────────────────────────────── */
function Personas({ onRun }) {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.get('/agentsphere/personas').then(setRows) }, [])
  if (!rows) return <Loading />
  return (
    <>
      <div className="card mb" style={{ fontSize: 13 }}><Icon name="shield" size={14} style={{ color: 'var(--primary)' }} />
        {' '}Before publishing, test every agent against hostile inputs — public-facing means adversarial. Click a persona to run it in the test chat.</div>
      <div className="grid cols-3">
        {rows.map((p) => (
          <div className="card" key={p.id}>
            <div style={{ fontSize: 26 }}>{p.emoji}</div>
            <h3 style={{ margin: '4px 0', fontSize: 15 }}>{p.name}</h3>
            <div style={{ fontSize: 13, fontStyle: 'italic', marginBottom: 6 }}>“{p.opening}”</div>
            <div className="muted mb" style={{ fontSize: 11 }}>Tests: {p.tests}</div>
            <button className="btn sm" onClick={() => onRun(p)}><Icon name="play" size={12} /> Run in test chat</button>
          </div>
        ))}
      </div>
    </>
  )
}
