import { useEffect, useRef, useState } from 'react'
import { api, openEvents } from '../api'
import Icon from '../components/Icon'
import { Empty, Loading, Modal, PageHead } from '../components/ui'

export default function Skills() {
  const [skills, setSkills] = useState(null)
  const [imp, setImp] = useState(false)
  const [form, setForm] = useState(null)        // null | {} (new) | { skill } (edit)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } }
  const load = () => api.get('/skills').then(setSkills).catch(() => flash('err', 'Could not load skills.'))
  useEffect(() => {
    load()
    const ws = openEvents((m) => { if (m.topic === 'skill.proposed') load() })
    return () => { try { ws && ws.close() } catch {} }
  }, [])

  const save = async (s) => {
    try { const r = await api.post(`/skills/${s.id}/save`); flash('ok', r.message || `Saved “${s.name}”.`); load() }
    catch (e) { flash('err', e?.message || 'Could not save the skill.') }
  }
  const discard = async (s, confirmFirst) => {
    if (confirmFirst && !window.confirm(`Remove skill “${s.name}”?`)) return
    try { const r = await api.del(`/skills/${s.id}`); flash('ok', r.message || `Removed “${s.name}”.`); load() }
    catch (e) { flash('err', e?.message || 'Could not remove the skill.') }
  }
  const setSandbox = async (s, lvl) => {
    try { const r = await api.patch(`/skills/${s.id}`, { sandbox_level: lvl }); flash('ok', `“${s.name}” → ${lvl} sandbox.`); load() }
    catch (e) { flash('err', e?.message || 'Could not change the sandbox.') }
  }
  const saveAll = async (proposed) => {
    try { for (const s of proposed) await api.post(`/skills/${s.id}/save`); flash('ok', `Saved ${proposed.length} skill(s).`); load() }
    catch (e) { flash('err', e?.message || 'Could not save all.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/skills/resolve', { transcript: phrase })
      const s = r.id ? (skills || []).find((x) => x.id === r.id) : null
      switch (r.action) {
        case 'create': setForm({}); flash('ok', 'Opening the new-skill form.'); break
        case 'import': setImp(true); flash('ok', 'Opening the import dialog.'); break
        case 'save': if (s) { await save(s); speak(r.message) } break
        case 'discard': if (s) { await discard(s, false); speak(r.message) } break
        case 'sandbox': if (s) { await setSandbox(s, r.level); speak(r.message) } break
        case 'edit': if (s) { setForm({ skill: s }); flash('ok', `Opened “${s.name}”.`) } break
        case 'save_all': await saveAll((skills || []).filter((x) => x.status === 'proposed')); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__skillsVoice = (t) => { runCommand(t); return true }; return () => { if (window.__skillsVoice) delete window.__skillsVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!skills) return <Loading />
  const proposed = skills.filter((s) => s.status === 'proposed')
  const active = skills.filter((s) => s.status === 'active')

  const Card = ({ s, isProposed }) => (
    <div className="card">
      <div className="between mb">
        <div>
          <h3 style={{ margin: 0 }}>{s.name}</h3>
          <div className="muted" style={{ fontSize: 12 }}>{s.description}</div>
        </div>
        <span className="tag" style={{ color: s.source === 'auto_captured' ? 'var(--accent)' : 'var(--muted)' }}>
          {s.source === 'auto_captured' ? '🧠 auto-captured' : s.source}</span>
      </div>
      <div className="flex wrap mb" style={{ fontSize: 12 }}>
        <span className="tag">confidence {Math.round((s.confidence || 0) * 100)}%</span>
        <span className="tag">runs {s.runs}</span>
        <span className="tag">🔒 {s.sandbox_level === 'docker' ? 'Docker sandbox' : 'process jail'}</span>
      </div>
      {s.definition?.steps && (
        <div className="card" style={{ background: 'var(--panel-2)', boxShadow: 'none', padding: 12, marginBottom: 12 }}>
          {s.definition.steps.map((st, i) => (
            <div key={i} style={{ fontSize: 12.5, padding: '2px 0' }}>
              <span className="tag" style={{ marginRight: 6 }}>{st.order || i + 1}</span>{st.do}</div>
          ))}
        </div>
      )}
      <div className="between" style={{ flexWrap: 'wrap', gap: 8 }}>
        <div className="flex" style={{ fontSize: 12 }}>
          <span className="muted">Sandbox:</span>
          {['process', 'docker'].map((l) => (
            <button key={l} className={'btn sm ' + (s.sandbox_level === l ? '' : 'ghost')}
              onClick={() => setSandbox(s, l)}>{l}</button>
          ))}
        </div>
        <div className="row-actions">
          <button className="btn ghost sm" onClick={() => setForm({ skill: s })}><Icon name="settings" size={12} /> Edit</button>
          {isProposed
            ? <>
                <button className="btn green sm" onClick={() => save(s)}><Icon name="check" size={14} /> Save skill</button>
                <button className="btn ghost sm" onClick={() => discard(s)}>Discard</button>
              </>
            : <button className="btn ghost sm" onClick={() => discard(s, true)}>Archive</button>}
        </div>
      </div>
    </div>
  )

  return (
    <>
      <PageHead title="Skills" sub="Agents capture reusable skills from completed work — self-improving, but supervised. Author or import your own, by click or voice.">
        <div className="flex" style={{ gap: 6 }}>
          <button className="btn secondary" onClick={() => setImp(true)}><Icon name="download" size={15} /> Import</button>
          <button className="btn" onClick={() => setForm({})}><Icon name="plus" size={15} /> New skill</button>
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "create a skill", "save the lead-nurture skill", "import a skill", "discard the X skill"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {proposed.length > 0 && (
        <div className="mb">
          <div className="between mb">
            <div className="flex"><Icon name="sparkles" size={16} style={{ color: 'var(--accent)' }} />
              <strong>Proposed by your agents ({proposed.length})</strong>
              <span className="muted" style={{ fontSize: 12 }}>— review and save to reuse in one command next time</span></div>
            {proposed.length > 1 && <button className="btn green sm" onClick={() => saveAll(proposed)}><Icon name="check" size={13} /> Save all</button>}
          </div>
          <div className="grid cols-2">{proposed.map((s) => <Card key={s.id} s={s} isProposed />)}</div>
        </div>
      )}

      <div className="flex mb"><Icon name="zap" size={16} /><strong>Saved skills ({active.length})</strong></div>
      {active.length === 0
        ? <Empty>No saved skills yet. Author one with <strong>New skill</strong>, import one, or run a task/pipeline — agents will propose skills from what they learn.</Empty>
        : <div className="grid cols-2">{active.map((s) => <Card key={s.id} s={s} />)}</div>}

      {imp && <ImportModal onClose={() => setImp(false)} onDone={load} onFlash={flash} />}
      {form && <SkillForm form={form} onClose={() => setForm(null)} onDone={load} onFlash={flash} />}
    </>
  )
}

function SkillForm({ form, onClose, onDone, onFlash }) {
  const editing = !!form.skill
  const s = form.skill
  const [name, setName] = useState(s?.name || '')
  const [description, setDescription] = useState(s?.description || '')
  const [steps, setSteps] = useState((s?.definition?.steps || []).map((x) => x.do || '').filter(Boolean).length
    ? s.definition.steps.map((x) => x.do || '') : [''])
  const [busy, setBusy] = useState(false)

  const setStep = (i, v) => setSteps(steps.map((x, j) => j === i ? v : x))
  const addStep = () => setSteps([...steps, ''])
  const rm = (i) => setSteps(steps.filter((_, j) => j !== i))
  const submit = async () => {
    setBusy(true)
    try {
      const body = { name, description, steps: steps.filter((x) => x.trim()) }
      const r = editing ? await api.patch(`/skills/${s.id}`, body) : await api.post('/skills', body)
      onFlash('ok', r.message || (editing ? 'Skill saved.' : 'Skill created.')); onDone(); onClose()
    } catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not save the skill.') }
    finally { setBusy(false) }
  }
  return (
    <Modal title={editing ? `Edit ${s.name}` : 'New skill'} onClose={onClose}>
      <div className="field"><label>Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Lead Nurture Sequence" autoFocus /></div>
      <div className="field"><label>Description</label>
        <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What does this skill do?" /></div>
      <h4>Steps (in order)</h4>
      {steps.map((st, i) => (
        <div key={i} className="flex mb" style={{ gap: 6 }}>
          <span className="tag" style={{ minWidth: 22, justifyContent: 'center' }}>{i + 1}</span>
          <input style={{ flex: 1 }} value={st} onChange={(e) => setStep(i, e.target.value)} placeholder="What happens at this step?" />
          <button className="icon-btn" style={{ width: 30, height: 30 }} onClick={() => rm(i)}><Icon name="x" size={13} /></button>
        </div>
      ))}
      <button className="btn ghost sm mb" onClick={addStep}><Icon name="plus" size={13} /> Add step</button>
      <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={!name || busy}>
        {busy ? 'Saving…' : editing ? 'Save changes' : 'Create skill'}</button>
    </Modal>
  )
}

function ImportModal({ onClose, onDone, onFlash }) {
  const [f, setF] = useState({ format: 'hermes', name: '', document: '' })
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try { const r = await api.post('/skills/import', f); onFlash('ok', r.message || `Imported “${r.skill.name}”.`); onDone(); onClose() }
    catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not import the skill.') }
    finally { setBusy(false) }
  }
  return (
    <Modal title="Import a skill" onClose={onClose}>
      <p className="muted">Bring a Hermes / OpenClaw skill document — both are structured step lists.
        Paste it and we'll convert it to our format.</p>
      <div className="field"><label>Source format</label>
        <select value={f.format} onChange={(e) => setF({ ...f, format: e.target.value })}>
          <option value="hermes">Hermes skill document</option>
          <option value="openclaw">OpenClaw config</option>
          <option value="generic">Generic (numbered steps)</option>
        </select></div>
      <div className="field"><label>Name (optional)</label>
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
      <div className="field"><label>Skill document</label>
        <textarea rows={6} value={f.document} onChange={(e) => setF({ ...f, document: e.target.value })}
          placeholder={'1. Fetch leads from CRM\n2. Score by budget\n3. Email the top 5'} /></div>
      <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={!f.document || busy}>{busy ? 'Importing…' : 'Import'}</button>
    </Modal>
  )
}
