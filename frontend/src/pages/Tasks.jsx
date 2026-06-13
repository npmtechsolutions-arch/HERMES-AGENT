import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead, Pill } from '../components/ui'

const COLS = [
  ['queued', 'Queued'], ['working', 'Working'], ['waiting', 'Waiting'],
  ['reviewing', 'Reviewing'], ['completed', 'Completed'],
]

export default function Tasks() {
  const [tasks, setTasks] = useState(null)
  const [sel, setSel] = useState(null)
  const [planner, setPlanner] = useState(false)
  const [params] = useSearchParams()
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } }
  const load = () => api.get('/tasks').then(setTasks).catch(() => flash('err', 'Could not load tasks.'))
  useEffect(() => { load() }, [])
  useEffect(() => { if (params.get('plan')) setPlanner(params.get('plan')) }, [params])

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/tasks/resolve', { transcript: phrase })
      switch (r.action) {
        case 'create_task': { const t = await api.post('/tasks/quick', { utterance: r.utterance, execute: r.execute, use_llm: false }); flash('ok', t.message); speak(t.message); await load(); setSel(t.id) } break
        case 'execute_task': { const t = await api.post(`/tasks/${r.id}/execute`); flash('ok', `Executing “${r.title}”.`); speak(`Executing ${r.title}.`); await load() } break
        case 'cancel_task': { const t = await api.post(`/tasks/${r.id}/cancel`); flash('ok', t.message || `Canceled “${r.title}”.`); speak('Canceled.'); await load() } break
        case 'open_task': setSel(r.id); flash('ok', `Opened “${r.title}”.`); break
        case 'plan_open': setPlanner(''); flash('ok', 'Opening the planner.'); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__tasksVoice = (t) => { runCommand(t); return true }; return () => { if (window.__tasksVoice) delete window.__tasksVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!tasks) return <Loading />
  const cols = [...COLS]
  if (tasks.some((t) => t.status === 'canceled')) cols.push(['canceled', 'Canceled'])

  return (
    <>
      <PageHead title="Task Board" sub='Voice or manual tasks decomposed by the CEO Agent — by click or voice.'>
        <button className="btn" onClick={() => setPlanner('')}><Icon name="plus" size={16} /> New task</button>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "create a task to prepare the GST report", "run the GST task", "cancel the leads task"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {tasks.length === 0 && <div className="card" style={{ textAlign: 'center', padding: 28 }}>
        <p className="muted">No tasks yet. Click <strong>New task</strong> or say "create a task to follow up with new leads".</p></div>}

      <div className="kanban">
        {cols.map(([key, label]) => {
          const col = tasks.filter((t) => t.status === key ||
            (key === 'working' && ['planning'].includes(t.status)) ||
            (key === 'waiting' && ['escalated'].includes(t.status)))
          return (
            <div className="kcol" key={key}>
              <h4>{label} · {col.length}</h4>
              {col.map((t) => (
                <div className="kcard" key={t.id} onClick={() => setSel(t.id)} style={key === 'canceled' ? { opacity: 0.6 } : {}}>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>{t.title}</div>
                  <div className="between">
                    <span className={'pr-' + t.priority} style={{ fontSize: 11 }}>● {t.priority}</span>
                    <span className="tag">{t.source}</span>
                  </div>
                </div>
              ))}
            </div>
          )
        })}
      </div>

      {sel && <TaskDetail id={sel} onClose={() => setSel(null)} onChange={load} onFlash={flash} />}
      {planner !== false && <Planner seed={planner} onClose={() => setPlanner(false)} onCreated={load} onFlash={flash} />}
    </>
  )
}

function Planner({ seed, onClose, onCreated, onFlash }) {
  const [utterance, setUtterance] = useState(seed || '')
  const [plan, setPlan] = useState(null)
  const [busy, setBusy] = useState(false)
  const [useLlm, setUseLlm] = useState(true)

  const doPlan = async () => {
    setBusy(true); setPlan(null)
    try { setPlan(await api.post('/tasks/plan', { utterance, use_llm: useLlm })) }
    catch (e) { onFlash('err', e?.message || 'Could not plan that.') }
    finally { setBusy(false) }
  }
  useEffect(() => { if (seed) doPlan() }, [])

  const create = async (execute) => {
    try {
      const t = await api.post('/tasks', {
        title: utterance.slice(0, 80), utterance, source: 'voice',
        priority: plan.amount_detected ? 'urgent' : 'normal', plan,
      })
      if (execute) await api.post(`/tasks/${t.id}/execute`)
      onFlash('ok', execute ? `Task created & executing: ${t.title}` : `Task queued: ${t.title}`)
      onCreated(); onClose()
    } catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not create the task.') }
  }

  return (
    <Modal title="CEO Agent — Task Planner" onClose={onClose}>
      <p className="muted">Describe the work in natural language. The CEO Agent decomposes it.</p>
      <textarea rows={2} value={utterance} onChange={(e) => setUtterance(e.target.value)}
        placeholder='e.g. "Prepare the monthly GST report and email it to my CA by Friday"' />
      <label className="flex mt" style={{ fontSize: 13, cursor: 'pointer', width: 'auto' }}>
        <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} style={{ width: 16 }} />
        Reason with the local LLM (slower on CPU — falls back to instant rules)
      </label>
      <button className="btn mt" onClick={doPlan} disabled={!utterance || busy}>
        {busy ? (useLlm ? '🧠 Thinking locally…' : 'Planning…') : 'Decompose with CEO Agent'}</button>
      {busy && useLlm && <div className="muted mt" style={{ fontSize: 12 }}>
        Running on-device inference — no data leaves this machine. This can take a while on CPU.</div>}

      {plan && (
        <div className="mt">
          <div className="card" style={{ background: 'var(--bg-2)' }}>
            {plan.engine && <span className="tag mb" style={{ color: plan.engine.includes('llm') ? 'var(--accent)' : 'var(--muted)' }}>🧠 planned by {plan.engine}</span>}
            <div className="muted" style={{ fontSize: 13, margin: '10px 0' }}>🔊 {plan.readback}</div>
            {plan.subtasks.map((s) => (
              <div className="wf-node mb" key={s.step}>
                <div className="ix" style={{ background: 'var(--panel-2)' }}>{s.step}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13 }}>{s.description}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{s.agent_name} · {s.department} · skill: {s.skill}</div>
                </div>
              </div>
            ))}
            <div className="flex wrap" style={{ fontSize: 12 }}>
              <span className="tag">⏱ {plan.estimate_minutes} min</span>
              {plan.amount_detected && <span className="tag">💰 ₹{plan.amount_detected.toLocaleString()}</span>}
              {plan.deadline_hint && <span className="tag">📅 {plan.deadline_hint}</span>}
              {plan.requires_approval
                ? <span className="tag" style={{ color: 'var(--amber)' }}>🛡️ Needs approval ({plan.approval.rule})</span>
                : <span className="tag" style={{ color: 'var(--green)' }}>✓ Auto ({plan.approval.rule})</span>}
            </div>
          </div>
          <div className="row-actions mt">
            <button className="btn green" onClick={() => create(true)}>Proceed (execute)</button>
            <button className="btn secondary" onClick={() => create(false)}>Save as queued</button>
          </div>
        </div>
      )}
    </Modal>
  )
}

function TaskDetail({ id, onClose, onChange, onFlash }) {
  const [t, setT] = useState(null)
  const [agents, setAgents] = useState([])
  const [editing, setEditing] = useState(false)
  const [f, setF] = useState({ title: '', priority: 'normal', assignee_agent_id: '' })
  const load = () => api.get(`/tasks/${id}`).then((x) => { setT(x); setF({ title: x.title, priority: x.priority, assignee_agent_id: x.assignee_agent_id || '' }) })
  useEffect(() => { load(); api.get('/agents').then(setAgents).catch(() => {}) }, [id])
  if (!t) return <Modal title="Task" onClose={onClose}><Loading /></Modal>

  const execute = async () => {
    try { await api.post(`/tasks/${id}/execute`); onFlash('ok', 'Task execution started.'); load(); onChange() }
    catch (e) { onFlash('err', e?.message || 'Could not execute the task.') }
  }
  const cancel = async () => {
    if (!window.confirm(`Cancel “${t.title}”?`)) return
    try { const r = await api.post(`/tasks/${id}/cancel`); onFlash('ok', r.message || 'Task canceled.'); load(); onChange() }
    catch (e) { onFlash('err', e?.message || 'Could not cancel the task.') }
  }
  const save = async () => {
    try { const r = await api.patch(`/tasks/${id}`, { title: f.title, priority: f.priority, assignee_agent_id: f.assignee_agent_id }); onFlash('ok', r.message || 'Task updated.'); setEditing(false); load(); onChange() }
    catch (e) { onFlash('err', e?.message || 'Could not save the task.') }
  }
  const terminal = ['completed', 'canceled'].includes(t.status)

  return (
    <Modal title={editing ? `Edit · ${t.title}` : t.title} onClose={onClose}>
      {editing ? (
        <>
          <div className="field"><label>Title</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
          <div className="grid cols-2" style={{ gap: 12 }}>
            <div className="field"><label>Priority</label>
              <select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>
                {['low', 'normal', 'high', 'urgent'].map((p) => <option key={p} value={p}>{p}</option>)}</select></div>
            <div className="field"><label>Assignee</label>
              <select value={f.assignee_agent_id} onChange={(e) => setF({ ...f, assignee_agent_id: e.target.value })}>
                <option value="">— unassigned —</option>
                {agents.filter((a) => a.status !== 'archived').map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
          </div>
          <div className="row-actions"><button className="btn ghost" onClick={() => setEditing(false)}>Cancel</button>
            <button className="btn" onClick={save} disabled={!f.title}>Save changes</button></div>
        </>
      ) : (
        <>
          <div className="flex wrap mb"><Pill status={t.status} />
            <span className={'tag pr-' + t.priority}>{t.priority}</span>
            <span className="tag">{t.source}</span>
            {t.assignee_agent_id && <span className="tag">{agents.find((a) => a.id === t.assignee_agent_id)?.name || 'assigned'}</span>}
          </div>
          {t.utterance && <p className="muted">🎙️ “{t.utterance}”</p>}

          {t.plan?.subtasks && <>
            <h4>Plan (CEO Agent DAG)</h4>
            {t.plan.subtasks.map((s) => (
              <div className="wf-node mb" key={s.step}>
                <div className="ix" style={{ background: 'var(--panel-2)' }}>{s.step}</div>
                <div style={{ flex: 1 }}><div style={{ fontSize: 13 }}>{s.description}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{s.agent_name} · {s.department}</div></div>
              </div>
            ))}
          </>}

          {t.bus?.length > 0 && <>
            <h4 className="mt">🔁 Agent Messaging Bus</h4>
            {t.bus.map((m, i) => (
              <div className="bus-msg" key={i}>
                <div className="ring" style={{ width: 30, height: 30, fontSize: 12 }}>A</div>
                <div><div className="who">{m.from_agent_id} · <span className="tag">{m.kind}</span></div>
                  <div style={{ fontSize: 13 }}>{m.content?.text}</div></div>
              </div>
            ))}
          </>}

          {t.approvals?.length > 0 && <>
            <h4 className="mt">🛡️ Approvals</h4>
            {t.approvals.map((a) => (
              <div key={a.id} className="between" style={{ fontSize: 13, padding: '6px 0' }}>
                <span>{a.summary} <span className="tag">{a.rule_id}</span></span>
                <Pill status={a.state} />
              </div>
            ))}
          </>}

          {t.result && <div className="card mt" style={{ background: 'var(--bg-2)' }}>
            <div className="muted" style={{ fontSize: 12 }}>Result</div>
            <div style={{ fontSize: 13 }}>{t.result.summary}</div></div>}

          <div className="row-actions mt" style={{ flexWrap: 'wrap' }}>
            {!terminal && <button className="btn secondary sm" onClick={() => setEditing(true)}><Icon name="settings" size={13} /> Edit</button>}
            {['queued', 'planning'].includes(t.status) && t.plan && <button className="btn green sm" onClick={execute}>Execute task</button>}
            {!terminal && <button className="btn ghost sm" style={{ color: 'var(--red)' }} onClick={cancel}><Icon name="x" size={13} /> Cancel task</button>}
          </div>
        </>
      )}
    </Modal>
  )
}
