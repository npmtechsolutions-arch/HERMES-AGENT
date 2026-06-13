import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead, Pill } from '../components/ui'

const NODE_COLOR = {
  trigger: 'var(--blue)', condition: 'var(--amber)', action: 'var(--primary)',
  agent_task: 'var(--accent)', approval: 'var(--orange)', notification: 'var(--green)',
}

export default function Workflows() {
  const [wfs, setWfs] = useState(null)
  const [builder, setBuilder] = useState(false)
  const [view, setView] = useState(null)
  const [params] = useSearchParams()
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => api.get('/workflows').then(setWfs).catch(() => flash('err', 'Could not load workflows.'))
  useEffect(() => { load() }, [])
  useEffect(() => { if (params.get('compile')) setBuilder(params.get('compile')) }, [params])

  const setStatus = async (w, active) => {
    try { const r = await api.post(`/workflows/${w.id}/${active ? 'activate' : 'deactivate'}`); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.message || 'Could not change the workflow.') }
  }
  const remove = async (w) => {
    if (!window.confirm(`Delete workflow “${w.name}”?`)) return
    try { const r = await api.del(`/workflows/${w.id}`); flash('ok', r.message || `Deleted “${w.name}”.`); load() }
    catch (e) { flash('err', e?.message || 'Could not delete the workflow.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/workflows/resolve', { transcript: phrase })
      const w = r.id ? (wfs || []).find((x) => x.id === r.id) : null
      switch (r.action) {
        case 'create': { const x = await api.post('/workflows/quick', { utterance: r.utterance, activate: r.activate }); flash('ok', x.message); speak(x.message); load() } break
        case 'build': setBuilder(''); flash('ok', 'Opening the workflow builder.'); break
        case 'activate': if (w) { await setStatus(w, true); speak(r.message) } break
        case 'deactivate': if (w) { await setStatus(w, false); speak(r.message) } break
        case 'dry_run': if (w) { setView(w); try { const x = await api.post(`/workflows/${w.id}/dry_run`); flash('ok', x.message); speak(x.message) } catch (e) { flash('err', e?.message || 'Dry-run failed.') } } break
        case 'delete': if (w) await remove(w); break
        case 'open': if (w) setView(w); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__workflowsVoice = (t) => { runCommand(t); return true }; return () => { if (window.__workflowsVoice) delete window.__workflowsVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!wfs) return <Loading />
  return (
    <>
      <PageHead title="Workflows" sub='Speak a sentence — it compiles to a workflow graph. By click or voice.'>
        <button className="btn" onClick={() => setBuilder('')}><Icon name="plus" size={16} /> Build workflow</button>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "build a workflow to email me every morning", "activate the sales workflow", "dry run the X workflow"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="grid cols-2">
        {wfs.map((w) => (
          <div className="card" key={w.id}>
            <div className="between mb">
              <h3 style={{ margin: 0 }}>{w.name}</h3><Pill status={w.status} />
            </div>
            {w.source_utterance && <p className="muted" style={{ fontSize: 12 }}>🎙️ “{w.source_utterance}”</p>}
            <WfGraph graph={w.graph} compact />
            <div className="row-actions mt" style={{ flexWrap: 'wrap' }}>
              <button className="btn secondary sm" onClick={() => setView(w)}>View / dry-run</button>
              {w.status === 'active'
                ? <button className="btn ghost sm" onClick={() => setStatus(w, false)}>Pause</button>
                : <button className="btn green sm" onClick={() => setStatus(w, true)}>Activate</button>}
              <button className="icon-btn" style={{ width: 32, height: 32 }} title="Delete" onClick={() => remove(w)}><Icon name="x" size={14} /></button>
            </div>
          </div>
        ))}
        {wfs.length === 0 && <div className="empty">No workflows yet. Build one (or say "build a workflow to …").</div>}
      </div>

      {builder !== false && <Builder seed={builder} onClose={() => setBuilder(false)} onCreated={load} onFlash={flash} />}
      {view && <ViewWf w={view} onClose={() => setView(null)} onFlash={flash} />}
    </>
  )
}

function WfGraph({ graph, compact }) {
  const nodes = graph?.nodes || []
  return (
    <div>
      {nodes.map((n, i) => (
        <div key={n.node_id}>
          <div className="wf-node" style={{ padding: compact ? '8px 10px' : '12px 14px' }}>
            <div className="ix" style={{ background: NODE_COLOR[n.type] || 'var(--panel-2)' }}>
              {n.type[0].toUpperCase()}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13 }}>{n.label}</div>
              <div className="muted" style={{ fontSize: 11 }}>{n.type}</div>
            </div>
          </div>
          {i < nodes.length - 1 && <div className="wf-arrow">↓</div>}
        </div>
      ))}
    </div>
  )
}

function Builder({ seed, onClose, onCreated, onFlash }) {
  const [utterance, setUtterance] = useState(seed || '')
  const [graph, setGraph] = useState(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)

  const compile = async () => {
    setBusy(true)
    try { const r = await api.post('/workflows/compile', { utterance }); setGraph(r.graph); setName(utterance.slice(0, 50)); if (r.unmapped_steps?.length) onFlash('ok', r.unmapped_steps[0]) }
    catch (e) { onFlash('err', e?.message || 'Could not compile that.') }
    finally { setBusy(false) }
  }
  useEffect(() => { if (seed) compile() }, [])

  const save = async (activate) => {
    setBusy(true)
    try {
      const w = await api.post('/workflows', { name, graph, status: activate ? 'active' : 'draft', source_utterance: utterance })
      if (activate) await api.post(`/workflows/${w.id}/activate`)
      onFlash('ok', activate ? `Workflow activated: ${name}` : `Workflow saved as draft: ${name}`); onCreated(); onClose()
    } catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not save the workflow.') }
    finally { setBusy(false) }
  }

  return (
    <Modal title="Voice-to-Workflow Builder" onClose={onClose}>
      <p className="muted">Speak or type a sentence describing the automation.</p>
      <textarea rows={2} value={utterance} onChange={(e) => setUtterance(e.target.value)}
        placeholder='"Every Monday at 9, pull last week’s sales from Zoho, make a summary deck and Slack it to founders"' />
      <button className="btn mt" onClick={compile} disabled={!utterance || busy}>{busy ? 'Compiling…' : 'Compile to graph'}</button>
      {graph && <>
        <div className="field mt"><label>Workflow name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div className="card" style={{ background: 'var(--bg-2)' }}><WfGraph graph={graph} /></div>
        <div className="row-actions mt">
          <button className="btn green" onClick={() => save(true)} disabled={busy || !name}>Activate</button>
          <button className="btn secondary" onClick={() => save(false)} disabled={busy || !name}>Save as draft</button>
        </div>
      </>}
    </Modal>
  )
}

function ViewWf({ w, onClose, onFlash }) {
  const [run, setRun] = useState(null)
  const [history, setHistory] = useState(null)
  const [busy, setBusy] = useState(false)
  const dryRun = async () => {
    setBusy(true)
    try { const r = await api.post(`/workflows/${w.id}/dry_run`); setRun(r); onFlash('ok', r.message || 'Dry-run complete.'); api.get(`/workflows/${w.id}/runs`).then(setHistory) }
    catch (e) { onFlash('err', e?.message || 'Dry-run failed.') }
    finally { setBusy(false) }
  }
  useEffect(() => { api.get(`/workflows/${w.id}/runs`).then(setHistory).catch(() => {}) }, [w.id])
  return (
    <Modal title={w.name} onClose={onClose}>
      <WfGraph graph={w.graph} />
      <button className="btn secondary mt" onClick={dryRun} disabled={busy}>{busy ? 'Running…' : '▶ Dry-run (sandbox)'}</button>
      {run && <div className="card mt" style={{ background: 'var(--bg-2)' }}>
        <div className="between mb"><span className="muted" style={{ fontSize: 12 }}>Run {run.run_id}</span>
          <Pill status={run.status} /></div>
        {run.node_results.map((r) => (
          <div key={r.node_id} className="between" style={{ fontSize: 13, padding: '4px 0' }}>
            <span>{r.label}</span><span className="tag" style={{ color: 'var(--green)' }}>{r.status}</span>
          </div>
        ))}
      </div>}
      {history && history.length > 0 && <>
        <h4 className="mt">Run history ({history.length})</h4>
        {history.slice(0, 8).map((h) => (
          <div key={h.id} className="between" style={{ fontSize: 12.5, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
            <span className="muted">{h.trigger_info?.mode || 'run'} · {h.started_at ? new Date(h.started_at).toLocaleString() : ''}</span>
            <Pill status={h.status} />
          </div>
        ))}
      </>}
    </Modal>
  )
}
