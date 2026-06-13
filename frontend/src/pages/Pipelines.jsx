import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead, Pill } from '../components/ui'

export default function Pipelines() {
  const [pipelines, setPipelines] = useState(null)
  const [agents, setAgents] = useState([])
  const [build, setBuild] = useState(false)
  const [edit, setEdit] = useState(null)
  const [runId, setRunId] = useState(null)
  const [runPipe, setRunPipe] = useState(null)
  const [runAuto, setRunAuto] = useState(false)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } }
  const load = () => Promise.all([api.get('/pipelines'), api.get('/agents')])
    .then(([p, a]) => { setPipelines(p); setAgents(a.filter((x) => x.status !== 'archived')) })
    .catch(() => flash('err', 'Could not load pipelines.'))
  useEffect(() => { load() }, [])

  const startRun = (pl, auto = false) => { setRunPipe(pl); setRunAuto(auto); setRunId('new') }
  const remove = async (pl) => {
    if (!window.confirm(`Delete pipeline “${pl.name}”?`)) return
    try { const r = await api.del(`/pipelines/${pl.id}`); flash('ok', r.message || `Deleted “${pl.name}”.`); load() }
    catch (e) { flash('err', e?.message || 'Could not delete the pipeline.') }
  }
  const duplicate = async (pl) => {
    try {
      const r = await api.post('/pipelines', { name: `${pl.name} (copy)`, description: pl.description,
        steps: pl.steps.map((s) => ({ agent_id: s.agent_id, instruction: s.instruction, requires_approval: s.requires_approval })) })
      flash('ok', `Duplicated as “${r.name || pl.name + ' (copy)'}”.`); load()
    } catch (e) { flash('err', e?.message || 'Could not duplicate.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/pipelines/resolve', { transcript: phrase })
      const pl = r.id ? (pipelines || []).find((x) => x.id === r.id) : null
      switch (r.action) {
        case 'build': setBuild(true); flash('ok', 'Opening the pipeline builder.'); break
        case 'run': if (pl) { startRun(pl, true); flash('ok', r.message); speak(r.message) } break
        case 'edit': if (pl) { setEdit(pl); flash('ok', `Opened “${pl.name}”.`) } break
        case 'delete': if (pl) await remove(pl); break
        case 'duplicate': if (pl) await duplicate(pl); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__pipelinesVoice = (t) => { runCommand(t); return true }; return () => { if (window.__pipelinesVoice) delete window.__pipelinesVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!pipelines) return <Loading />

  return (
    <>
      <PageHead title="Agent Pipelines" sub="Chain your AI employees into a workflow, run it, approve each step, get a report — by click or voice.">
        <button className="btn" onClick={() => setBuild(true)}><Icon name="plus" size={16} /> Build pipeline</button>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "build a pipeline", "run the onboarding pipeline", "duplicate the launch pipeline"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {pipelines.length === 0 && <div className="empty">
        No pipelines yet. Build one (or say "build a pipeline"), or adopt a suggested pipeline from <strong>Your Company → AI Org Builder</strong>.</div>}

      <div className="grid cols-2">
        {pipelines.map((pl) => (
          <div className="card" key={pl.id}>
            <div className="between mb">
              <div>
                <h3 style={{ margin: 0 }}>{pl.name}</h3>
                <div className="muted" style={{ fontSize: 12 }}>{pl.description}</div>
              </div>
              <div className="flex" style={{ gap: 4 }}>
                {pl.last_run && <span className="tag" style={{ fontSize: 10, color: pl.last_run.status === 'completed' ? 'var(--green)' : 'var(--amber)' }}>last: {pl.last_run.status}</span>}
                <span className="tag">{pl.source}</span>
              </div>
            </div>
            <div className="mb">
              {pl.steps.map((s, i) => (
                <div key={s.id}>
                  <div className="wf-node" style={{ padding: '9px 12px' }}>
                    <div className="ix" style={{ background: 'var(--grad)' }}>{i + 1}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{s.agent_name}
                        {s.requires_approval && <Icon name="shield" size={12} style={{ marginLeft: 6, color: 'var(--orange)' }} />}
                      </div>
                      <div className="muted" style={{ fontSize: 12 }}>{s.instruction}</div>
                    </div>
                  </div>
                  {i < pl.steps.length - 1 && <div className="wf-arrow">↓</div>}
                </div>
              ))}
              {pl.steps.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No steps yet — Edit to add agents.</div>}
            </div>
            <div className="row-actions" style={{ flexWrap: 'wrap' }}>
              <button className="btn green sm" disabled={!pl.steps.length} onClick={() => startRun(pl)}><Icon name="play" size={14} /> Run</button>
              <button className="btn secondary sm" onClick={() => setEdit(pl)}>Edit</button>
              <button className="btn ghost sm" onClick={() => duplicate(pl)} title="Duplicate"><Icon name="layers" size={13} /> Duplicate</button>
              <button className="icon-btn" style={{ width: 32, height: 32 }} title="Delete" onClick={() => remove(pl)}><Icon name="x" size={14} /></button>
            </div>
          </div>
        ))}
      </div>

      {build && <Builder agents={agents} onClose={() => setBuild(false)} onSaved={load} onFlash={flash} />}
      {edit && <Builder agents={agents} existing={edit} onClose={() => setEdit(null)} onSaved={load} onFlash={flash} />}
      {runId && <RunView pipeline={runPipe} autoStart={runAuto} onClose={() => { setRunId(null); setRunAuto(false); load() }} onFlash={flash} />}
    </>
  )
}

// ── Pipeline builder ──────────────────────────────────────────────────────
function Builder({ agents, existing, onClose, onSaved, onFlash }) {
  const [name, setName] = useState(existing?.name || '')
  const [description, setDescription] = useState(existing?.description || '')
  const [busy, setBusy] = useState(false)
  const [steps, setSteps] = useState(existing?.steps?.map((s) => ({
    agent_id: s.agent_id, instruction: s.instruction, requires_approval: s.requires_approval,
  })) || [{ agent_id: agents[0]?.id || '', instruction: '', requires_approval: false }])

  const setStep = (i, k, v) => setSteps(steps.map((s, j) => j === i ? { ...s, [k]: v } : s))
  const addStep = () => setSteps([...steps, { agent_id: agents[0]?.id || '', instruction: '', requires_approval: false }])
  const rm = (i) => setSteps(steps.filter((_, j) => j !== i))
  const move = (i, d) => { const j = i + d; if (j < 0 || j >= steps.length) return; const n = [...steps];[n[i], n[j]] = [n[j], n[i]]; setSteps(n) }
  const save = async () => {
    setBusy(true)
    try {
      const body = { name, description, steps: steps.filter((s) => s.agent_id && s.instruction) }
      const r = existing ? await api.patch(`/pipelines/${existing.id}`, body) : await api.post('/pipelines', body)
      onFlash('ok', r.message || (existing ? 'Pipeline saved.' : 'Pipeline created.')); onSaved(); onClose()
    } catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not save the pipeline.') }
    finally { setBusy(false) }
  }

  return (
    <Modal title={existing ? 'Edit pipeline' : 'Build a pipeline'} onClose={onClose}>
      {agents.length === 0 && <div className="card mb" style={{ borderColor: 'var(--amber)', fontSize: 13 }}>
        ⚠ No agents yet — hire AI employees in <strong>Org Chart</strong> first, then build a pipeline.</div>}
      <div className="field"><label>Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Launch a new product" autoFocus /></div>
      <div className="field"><label>Description</label>
        <input value={description} onChange={(e) => setDescription(e.target.value)} /></div>
      <h4>Steps — agents run top to bottom</h4>
      {steps.map((s, i) => (
        <div key={i} className="card mb" style={{ background: 'var(--panel-2)', boxShadow: 'none', padding: 12 }}>
          <div className="between mb">
            <span className="tag">Step {i + 1}</span>
            <div className="flex">
              <button className="icon-btn" style={{ width: 28, height: 28 }} onClick={() => move(i, -1)}>↑</button>
              <button className="icon-btn" style={{ width: 28, height: 28 }} onClick={() => move(i, 1)}>↓</button>
              <button className="icon-btn" style={{ width: 28, height: 28 }} onClick={() => rm(i)}><Icon name="x" size={13} /></button>
            </div>
          </div>
          <select value={s.agent_id} onChange={(e) => setStep(i, 'agent_id', e.target.value)} style={{ marginBottom: 8 }}>
            {agents.map((a) => <option key={a.id} value={a.id}>{a.name} — {a.designation}</option>)}
          </select>
          <textarea rows={2} value={s.instruction} placeholder="What should this agent do?"
            onChange={(e) => setStep(i, 'instruction', e.target.value)} />
          <label className="flex mt" style={{ fontSize: 13, width: 'auto', cursor: 'pointer' }}>
            <input type="checkbox" checked={s.requires_approval} style={{ width: 16 }}
              onChange={(e) => setStep(i, 'requires_approval', e.target.checked)} />
            Require my approval before the next agent starts
          </label>
        </div>
      ))}
      <button className="btn secondary sm mb" onClick={addStep} disabled={!agents.length}><Icon name="plus" size={14} /> Add step</button>
      <button className="btn" style={{ width: '100%' }} onClick={save}
        disabled={!name || busy || !steps.some((s) => s.agent_id && s.instruction)}>
        {busy ? 'Saving…' : existing ? 'Save pipeline' : 'Create pipeline'}</button>
    </Modal>
  )
}

// ── Run view: live execution + per-step approval + final report ───────────
function RunView({ pipeline, autoStart, onClose, onFlash }) {
  const [run, setRun] = useState(null)
  const [useAi, setUseAi] = useState(true)
  const [running, setRunning] = useState(false)
  const stop = useRef(false)
  const started = useRef(false)

  const stepStatusPill = (st) => ({
    pending: 'pending', running: 'working', awaiting_approval: 'waiting',
    done: 'completed', rejected: 'rejected',
  }[st] || st)

  async function loop(runId) {
    setRunning(true); stop.current = false
    try {
      while (!stop.current) {
        const r = await api.post(`/pipelines/runs/${runId}/advance`)
        setRun(r)
        if (r.status === 'waiting_approval' || r.status === 'completed' || r.status === 'failed') break
      }
    } catch (e) { onFlash('err', e?.message || 'The run hit an error.') }
    finally { setRunning(false) }
  }

  const start = async () => {
    try { const r = await api.post(`/pipelines/${pipeline.id}/run`, { use_ai: useAi }); setRun(r); loop(r.id) }
    catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not start the run.') }
  }
  const decide = async (stepRunId, decision) => {
    try {
      const r = await api.post(`/pipelines/runs/${run.id}/decide`, { step_run_id: stepRunId, decision })
      setRun(r)
      if (decision === 'approve' && r.status !== 'completed') loop(r.id)
    } catch (e) { onFlash('err', e?.message || 'Could not record your decision.') }
  }
  useEffect(() => { if (autoStart && !started.current) { started.current = true; start() } }, [])
  useEffect(() => () => { stop.current = true }, [])

  return (
    <Modal title={`Run · ${pipeline.name}`} onClose={onClose}>
      {!run && (
        <>
          <p className="muted">Your agents will work one after another. Steps marked for approval pause for your review.</p>
          <label className="flex mb" style={{ fontSize: 13, width: 'auto', cursor: 'pointer' }}>
            <input type="checkbox" checked={useAi} style={{ width: 16 }} onChange={(e) => setUseAi(e.target.checked)} />
            Produce real output with the local LLM (slower) — off = fast simulated output
          </label>
          <button className="btn green" style={{ width: '100%' }} onClick={start}>
            <Icon name="play" size={16} /> Start run</button>
        </>
      )}

      {run && <>
        <div className="between mb">
          <Pill status={run.status === 'waiting_approval' ? 'waiting' : run.status} />
          {running && <span className="muted" style={{ fontSize: 12 }}>🧠 agents working…</span>}
        </div>

        {run.steps.map((s) => (
          <div key={s.id} className="card mb" style={{ background: 'var(--panel-2)', boxShadow: 'none', padding: 14 }}>
            <div className="between mb">
              <div className="flex">
                <div className="ix" style={{ width: 26, height: 26, borderRadius: 8,
                  background: 'var(--grad)', color: '#fff', display: 'grid', placeItems: 'center',
                  fontSize: 12, fontWeight: 700 }}>{s.seq}</div>
                <strong style={{ fontSize: 13 }}>{s.agent_name}</strong>
              </div>
              <Pill status={stepStatusPill(s.status)} />
            </div>
            <div className="muted" style={{ fontSize: 12, marginBottom: s.output ? 8 : 0 }}>{s.instruction}</div>
            {s.output && <div style={{ fontSize: 13, whiteSpace: 'pre-wrap', background: 'var(--panel)',
              border: '1px solid var(--border)', borderRadius: 10, padding: 11 }}>
              {s.output}
              {s.engine && <div className="cite mt" style={{ fontSize: 11 }}>via {s.engine}</div>}
            </div>}
            {s.status === 'awaiting_approval' && (
              <div className="row-actions mt">
                <button className="btn green sm" onClick={() => decide(s.id, 'approve')}>
                  <Icon name="check" size={14} /> Approve & continue</button>
                <button className="btn danger sm" onClick={() => decide(s.id, 'reject')}>Reject & stop</button>
              </div>
            )}
          </div>
        ))}

        {run.final_report && (
          <div className="card" style={{ background: 'var(--grad-soft)', border: '1px solid var(--border)' }}>
            <h3 style={{ marginTop: 0 }}><Icon name="sparkles" size={17} /> Final report</h3>
            <div style={{ fontSize: 13.5, whiteSpace: 'pre-wrap' }}>{run.final_report}</div>
          </div>
        )}
      </>}
    </Modal>
  )
}
