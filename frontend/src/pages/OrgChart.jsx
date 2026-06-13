import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead, Pill } from '../components/ui'

const NAME_POOL = ['Maya', 'Arjun', 'Geeta', 'Sam', 'Neha', 'Vikram', 'Priya', 'Karan', 'Riya', 'Dev', 'Anita', 'Rohan']

export default function OrgChart() {
  const [agents, setAgents] = useState(null)
  const [depts, setDepts] = useState([])
  const [sel, setSel] = useState(null)
  const [hire, setHire] = useState(null)        // null | {} | {prefill}
  const [addDept, setAddDept] = useState(false)
  const [msg, setMsg] = useState(null)          // { kind, text }
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const [params, setParams] = useSearchParams()
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const load = () => Promise.all([api.get('/agents'), api.get('/departments')])
    .then(([a, d]) => { setAgents(a); setDepts(d) }).catch(() => flash('err', 'Could not load the org.'))
  useEffect(() => { load() }, [])
  useEffect(() => { if (params.get('hire')) setHire({}) }, [params])

  const pickName = (list) => {
    const used = new Set((list || []).map((a) => (a.name || '').toLowerCase()))
    return NAME_POOL.find((n) => !used.has(n.toLowerCase())) || 'Alex'
  }
  const deptByName = (name) => name && depts.find((d) => d.name.toLowerCase() === name.toLowerCase())

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    try {
      const r = await api.post('/org/resolve', { transcript: phrase })
      const ceo = (agents || []).find((a) => a.is_ceo)
      switch (r.action) {
        case 'hire': {
          await api.post('/agents', { name: r.name || pickName(agents), designation: r.designation,
            department_id: (deptByName(r.department) || depts[0])?.id, model_id: 'mdl_gemma9b',
            reporting_manager_id: ceo?.id })
          flash('ok', `Hired ${r.name || 'a'} ${r.designation}.`); await load() } break
        case 'hire_open': setHire({ name: r.name || '', department: deptByName(r.department)?.id }); flash('ok', 'Opening the hire form.'); break
        case 'pause': { await api.post(`/agents/${r.id}/pause`); flash('ok', `${r.name} paused.`); await load() } break
        case 'resume': { await api.post(`/agents/${r.id}/resume`); flash('ok', `${r.name} resumed.`); await load() } break
        case 'archive': { await api.del(`/agents/${r.id}`); flash('ok', `${r.name} archived.`); await load() } break
        case 'open': { const a = (agents || []).find((x) => x.id === r.id); if (a) setSel(a) } break
        case 'add_department': { await api.post('/departments', { name: r.name }); flash('ok', `Added department “${r.name}”.`); await load() } break
        default: flash('err', r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
    setCmd('')
  }
  useEffect(() => { window.__orgVoice = (t) => { runCommand(t); return true }; return () => { if (window.__orgVoice) delete window.__orgVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!agents) return <Loading />
  const active = agents.filter((a) => a.status !== 'archived')
  const archived = agents.filter((a) => a.status === 'archived')
  const ceo = active.find((a) => a.is_ceo)
  const byDept = {}
  depts.forEach((d) => { byDept[d.id] = { dept: d, agents: [] } })
  const unassigned = []
  active.filter((a) => !a.is_ceo).forEach((a) => {
    if (byDept[a.department_id]) byDept[a.department_id].agents.push(a)
    else unassigned.push(a)
  })
  if (unassigned.length) byDept.__team = { dept: { id: '__team', name: 'Team' }, agents: unassigned }

  return (
    <>
      <PageHead title="Digital Employee Org Chart"
        sub='Your AI workforce — by click or voice. Say "hire a social media manager".'>
        <div className="flex" style={{ gap: 6 }}>
          <button className="btn ghost" onClick={() => setAddDept(true)}><Icon name="plus" size={15} /> Department</button>
          <button className="btn" onClick={() => setHire({})}><Icon name="plus" size={16} /> Hire AI Employee</button>
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "hire a social media manager", "pause Maya", "fire the collections agent", "add a department called Marketing"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}>
            <Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="card">
        {active.length === 0
          ? <div className="muted" style={{ textAlign: 'center', padding: 28 }}>
              No employees yet. Click <strong>Hire AI Employee</strong> or say "hire a social media manager".</div>
          : <div className="org">
              {ceo && <div className="org-ceo"><AgentNode a={ceo} onClick={() => setSel(ceo)} /></div>}
              <div className="org-depts">
                {Object.values(byDept).filter((g) => g.agents.length).map(({ dept, agents }) => (
                  <div className="org-dept" key={dept.id}>
                    <div className="org-dept-label">{dept.name}</div>
                    {agents.map((a) => <AgentNode key={a.id} a={a} onClick={() => setSel(a)} />)}
                  </div>
                ))}
              </div>
            </div>}
      </div>

      {archived.length > 0 && (
        <div className="card mt">
          <div className="org-dept-label mb">Archived ({archived.length})</div>
          <div className="flex wrap">
            {archived.map((a) => (
              <span key={a.id} className="tag" style={{ cursor: 'pointer' }} onClick={() => setSel(a)}>
                {a.name} · {a.designation}</span>))}
          </div>
        </div>
      )}

      {sel && <AgentModal agent={sel} depts={depts} onClose={() => setSel(null)} onChange={load} onFlash={flash} />}
      {hire && <HireWizard prefill={hire} onClose={() => { setHire(null); setParams({}) }} depts={depts}
        agents={agents} onCreated={load} onFlash={flash} />}
      {addDept && <AddDepartment onClose={() => setAddDept(false)} onSaved={load} onFlash={flash} />}
    </>
  )
}

function AgentNode({ a, onClick }) {
  return (
    <div className={'agent-node' + (a.is_ceo ? ' ceo' : '')} onClick={onClick}>
      <div className="status-ring"><Pill status={a.status} /></div>
      <div className="ring">{a.name[0]}</div>
      <div className="nm">{a.name}</div>
      <div className="ds">{a.designation}</div>
    </div>
  )
}

function AgentModal({ agent, depts, onClose, onChange, onFlash }) {
  const [a, setA] = useState(agent)
  const [perf, setPerf] = useState([])
  const [activity, setActivity] = useState(null)
  const [showActivity, setShowActivity] = useState(false)
  const [editing, setEditing] = useState(false)
  useEffect(() => { api.get(`/agents/${agent.id}/performance`).then(setPerf).catch(() => {}) }, [agent.id])
  const loadActivity = () => { setShowActivity(true); api.get(`/agents/${agent.id}/activity`).then(setActivity).catch(() => {}) }

  const act = async (path, label) => {
    try { const r = await api.post(`/agents/${agent.id}/${path}`); setA(r); onChange(); onFlash('ok', `${r.name} ${label}.`) }
    catch (e) { onFlash('err', e?.message || `Could not ${label} the agent.`) }
  }
  const archive = async () => {
    if (!window.confirm(`Archive “${a.name}”? They'll be removed from the active org (recoverable).`)) return
    try { await api.del(`/agents/${agent.id}`); onChange(); onFlash('ok', `${a.name} archived.`); onClose() }
    catch (e) { onFlash('err', e?.message || 'Could not archive the agent.') }
  }
  const TIER = { local: ['🔒 Local', 'var(--green)'], byo: ['☁ Your Cloud Key', 'var(--amber)'],
    managed: ['☁ Managed Gateway', 'var(--amber)'] }

  if (editing) return <EditAgent a={a} depts={depts} onClose={() => setEditing(false)}
    onSaved={(updated) => { setA(updated); setEditing(false); onChange(); onFlash('ok', `${updated.name} updated.`) }}
    onFlash={onFlash} wrapClose={onClose} />

  return (
    <Modal title={`${a.name} · ${a.designation}`} onClose={onClose}>
      <div className="flex wrap mb"><Pill status={a.status} />
        {a.is_ceo && <span className="tag">CEO Agent</span>}
        <span className="tag">Model: {a.model_id}</span>
        <span className="tag" style={{ color: (TIER[a.model_tier] || TIER.local)[1] }}>
          {(TIER[a.model_tier] || TIER.local)[0]}</span>
        <span className="tag">Voice: {a.voice_id}</span>
      </div>
      <p className="muted">{a.description}</p>

      <button className="btn secondary sm" onClick={loadActivity}>
        <Icon name="chart" size={14} /> Watch live activity (Glass-Box)</button>
      {showActivity && (
        <div className="card mt" style={{ background: 'var(--panel-2)', boxShadow: 'none', maxHeight: 220, overflowY: 'auto' }}>
          {!activity ? <div className="muted" style={{ fontSize: 13 }}>Loading stream…</div>
            : activity.stream.length === 0 ? <div className="muted" style={{ fontSize: 13 }}>No recent activity — assign this agent a task to watch it work.</div>
            : activity.stream.map((s, i) => (
              <div key={i} className="flex" style={{ padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 12.5 }}>
                <span className="tag" style={{ minWidth: 64, justifyContent: 'center',
                  color: s.kind === 'tool' ? 'var(--accent)' : s.kind === 'task' ? 'var(--orange)' : 'var(--muted)' }}>{s.label}</span>
                <span>{s.text}</span>
              </div>
            ))}
        </div>
      )}

      {(a.objectives || []).length > 0 && <>
        <h4>Objectives</h4>
        <ul style={{ marginTop: 4 }}>{(a.objectives || []).map((o, i) => <li key={i}>{o}</li>)}</ul></>}

      {a.skills?.length > 0 && <>
        <h4>Skills</h4>
        <div className="flex wrap">{a.skills.map((s) => <span key={s} className="tag">{s}</span>)}</div>
      </>}
      {a.tools?.length > 0 && <>
        <h4 className="mt">Tools (MCP grants)</h4>
        <div className="flex wrap">{a.tools.map((s) => <span key={s} className="tag">{s}</span>)}</div>
      </>}

      <h4 className="mt">Permissions</h4>
      <div className="muted" style={{ fontSize: 13 }}>
        Spend limit ₹{(a.permissions?.spend_limit || 0).toLocaleString()} ·
        External send: {a.permissions?.external_send || 'n/a'}
      </div>

      {perf[0] && <>
        <h4 className="mt">Performance ({perf[0].period})</h4>
        <div className="grid cols-3" style={{ gap: 8 }}>
          <Metric label="Tasks" v={perf[0].tasks_completed} />
          <Metric label="Success" v={perf[0].success_rate + '%'} />
          <Metric label="Utilization" v={perf[0].utilization + '%'} />
        </div>
      </>}

      <div className="row-actions mt" style={{ flexWrap: 'wrap' }}>
        <button className="btn secondary sm" onClick={() => setEditing(true)}><Icon name="settings" size={14} /> Edit</button>
        {!a.is_ceo && (a.status === 'paused'
          ? <button className="btn green sm" onClick={() => act('resume', 'resumed')}>Resume</button>
          : a.status !== 'archived' && <button className="btn secondary sm" onClick={() => act('pause', 'paused')}>Pause</button>)}
        {!a.is_ceo && a.status !== 'archived' &&
          <button className="btn ghost sm" style={{ color: 'var(--red)' }} onClick={archive}>
            <Icon name="x" size={13} /> Archive (fire)</button>}
      </div>
    </Modal>
  )
}

function EditAgent({ a, depts, onSaved, onClose, onFlash, wrapClose }) {
  const [f, setF] = useState({ name: a.name, designation: a.designation, department_id: a.department_id || depts[0]?.id || '',
    model_id: a.model_id, description: a.description || '',
    skills: (a.skills || []).join(', '), tools: (a.tools || []).join(', ') })
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const save = async () => {
    setBusy(true)
    try {
      const updated = await api.patch(`/agents/${a.id}`, {
        name: f.name, designation: f.designation, department_id: f.department_id, model_id: f.model_id,
        description: f.description, skills: f.skills.split(',').map((s) => s.trim()).filter(Boolean),
        tools: f.tools.split(',').map((s) => s.trim()).filter(Boolean) })
      onSaved(updated)
    } catch (e) { onFlash('err', e?.message || 'Could not save the agent.') }
    finally { setBusy(false) }
  }
  return (
    <Modal title={`Edit ${a.name}`} onClose={wrapClose}>
      <div className="field"><label>Name</label><input value={f.name} onChange={set('name')} /></div>
      <div className="field"><label>Designation</label><input value={f.designation} onChange={set('designation')} /></div>
      <div className="field"><label>Department</label>
        <select value={f.department_id} onChange={set('department_id')}>
          {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></div>
      <div className="field"><label>Model (LLM)</label>
        <select value={f.model_id} onChange={set('model_id')}>
          <option value="mdl_qwen14b_q4">Qwen 14B (Q4)</option>
          <option value="mdl_gemma9b">Gemma 9B</option>
          <option value="mdl_phi3">Phi 3.8B</option></select></div>
      <div className="field"><label>Description</label><textarea rows={2} value={f.description} onChange={set('description')} /></div>
      <div className="field"><label>Skills (comma-separated)</label><input value={f.skills} onChange={set('skills')} /></div>
      <div className="field"><label>Tools (comma-separated)</label><input value={f.tools} onChange={set('tools')} /></div>
      <div className="row-actions">
        <button className="btn ghost" onClick={onClose}>Cancel</button>
        <button className="btn" onClick={save} disabled={!f.name || !f.designation || busy}>{busy ? 'Saving…' : 'Save changes'}</button>
      </div>
    </Modal>
  )
}

function Metric({ label, v }) {
  return <div className="stat" style={{ padding: 12 }}>
    <div className="label">{label}</div><div className="value" style={{ fontSize: 20 }}>{v}</div>
  </div>
}

function HireWizard({ prefill, onClose, depts, agents, onCreated, onFlash }) {
  const [f, setF] = useState({ name: prefill?.name || '', designation: '', department_id: prefill?.department || depts[0]?.id || '',
    description: '', model_id: 'mdl_gemma9b', skills: '', tools: '' })
  const [busy, setBusy] = useState(false)
  const ceo = agents.find((a) => a.is_ceo)

  const submit = async () => {
    setBusy(true)
    try {
      const a = await api.post('/agents', {
        name: f.name, designation: f.designation, department_id: f.department_id,
        description: f.description, model_id: f.model_id,
        skills: f.skills.split(',').map((s) => s.trim()).filter(Boolean),
        tools: f.tools.split(',').map((s) => s.trim()).filter(Boolean),
        reporting_manager_id: ceo?.id,
      })
      onCreated(); onFlash('ok', `Hired ${a.name} · ${a.designation}.`); onClose()
    } catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not hire the agent.') }
    finally { setBusy(false) }
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <Modal title="Hire a new AI employee" onClose={onClose}>
      <p className="muted">The CEO Agent will draft a profile. Confirm to instantiate.</p>
      <div className="field"><label>Name</label><input value={f.name} onChange={set('name')} placeholder="e.g. Maya" autoFocus /></div>
      <div className="field"><label>Designation</label><input value={f.designation} onChange={set('designation')} placeholder="e.g. Social Media Manager" /></div>
      <div className="field"><label>Department</label>
        <select value={f.department_id} onChange={set('department_id')}>
          {depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select></div>
      <div className="field"><label>Model (LLM)</label>
        <select value={f.model_id} onChange={set('model_id')}>
          <option value="mdl_qwen14b_q4">Qwen 14B (Q4)</option>
          <option value="mdl_gemma9b">Gemma 9B</option>
          <option value="mdl_phi3">Phi 3.8B</option>
        </select></div>
      <div className="field"><label>Description</label><textarea value={f.description} onChange={set('description')} rows={2} /></div>
      <div className="field"><label>Skills (comma-separated)</label><input value={f.skills} onChange={set('skills')} placeholder="content, drafting, analytics" /></div>
      <div className="field"><label>Tools (comma-separated)</label><input value={f.tools} onChange={set('tools')} placeholder="browser.automation, comms.whatsapp.send" /></div>
      <button className="btn" style={{ width: '100%' }} onClick={submit}
        disabled={!f.name || !f.designation || busy}>{busy ? 'Hiring…' : 'Confirm & instantiate agent'}</button>
    </Modal>
  )
}

function AddDepartment({ onClose, onSaved, onFlash }) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try { await api.post('/departments', { name }); onFlash('ok', `Added department “${name}”.`); onSaved(); onClose() }
    catch (e) { onFlash('err', e?.message || 'Could not add the department.') }
    finally { setBusy(false) }
  }
  return (
    <Modal title="Add a department" onClose={onClose}>
      <div className="field"><label>Department name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Marketing" autoFocus /></div>
      <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={!name || busy}>
        {busy ? 'Adding…' : 'Add department'}</button>
    </Modal>
  )
}
