import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useMode } from '../mode'
import Icon from '../components/Icon'
import { Empty, Loading, Modal, PageHead } from '../components/ui'

const STAGES = [['new', 'New'], ['qualified', 'Qualified'], ['follow_up', 'Follow-up'],
  ['site_visit', 'Site Visit'], ['booking', 'Booking'], ['won', 'Won']]
const SCORE = { hot: 'var(--red)', warm: 'var(--amber)', cold: 'var(--muted)' }
const money = (v) => v ? `₹${(v / 100000).toFixed(0)}L` : '—'

export default function Leads() {
  const [leads, setLeads] = useState(null)
  const [clar, setClar] = useState([])
  const [skin, setSkin] = useState(null)
  const [sel, setSel] = useState(null)
  const [add, setAdd] = useState(false)
  const [imp, setImp] = useState(false)

  const load = () => Promise.all([api.get('/leads'), api.get('/clarifications'), api.get('/universal/skin')])
    .then(([l, c, s]) => { setLeads(l); setClar(c); setSkin(s) })
  useEffect(() => { load() }, [])
  if (!leads) return <Loading />
  const v = skin || { pipeline: 'Inquiry Pipeline', inquiry: 'inquiry', appointment: 'appointment' }

  const loadDemo = async () => { await api.post('/re/demo', {}); load() }
  const answer = async (id, ans) => { await api.post(`/clarifications/${id}/answer`, { answer: ans }); load() }

  return (
    <>
      <PageHead title={v.pipeline}
        sub={`${v.inquiry} → Follow-up → ${v.appointment} — answered in minutes, followed up forever. (Universal engine E1, skinned to ${v.industry || 'your industry'}.)`}>
        {leads.length === 0 && <button className="btn secondary" onClick={loadDemo}><Icon name="sparkles" size={15} /> Load demo</button>}
        <button className="btn secondary" onClick={() => setImp(true)}><Icon name="download" size={15} /> Import</button>
        <button className="btn" onClick={() => setAdd(true)}><Icon name="plus" size={16} /> Add {v.inquiry.toLowerCase()}</button>
      </PageHead>

      {clar.length > 0 && (
        <div className="card mb" style={{ borderColor: 'var(--amber)' }}>
          <div className="flex mb"><Icon name="chat" size={16} style={{ color: 'var(--amber)' }} />
            <strong>Agent needs your input ({clar.length}) — ask-don't-guess</strong></div>
          {clar.map((c) => (
            <div key={c.id} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 13 }}>{c.question}</span>
              <div className="row-actions">
                {(c.options || []).map((o) => <button key={o} className="btn secondary sm" onClick={() => answer(c.id, o)}>{o}</button>)}
              </div>
            </div>
          ))}
        </div>
      )}

      {leads.length === 0
        ? <Empty>No leads yet. Load the RE demo or add a lead — the agents take it from there.</Empty>
        : <div className="kanban" style={{ gridTemplateColumns: 'repeat(6,1fr)' }}>
            {STAGES.map(([k, label]) => {
              const col = leads.filter((l) => l.stage === k)
              return (
                <div className="kcol" key={k}>
                  <h4>{label} · {col.length}</h4>
                  {col.map((l) => (
                    <div className="kcard" key={l.id} onClick={() => setSel(l.id)}>
                      <div className="between"><strong style={{ fontSize: 13 }}>{l.name}</strong>
                        <span className="tag" style={{ color: SCORE[l.score], fontSize: 10 }}>● {l.score}</span></div>
                      <div className="muted" style={{ fontSize: 12 }}>{l.requirement} · {money(l.budget)} · {l.location}</div>
                      <div className="flex wrap" style={{ marginTop: 5, gap: 4 }}>
                        <span className="tag" style={{ fontSize: 10 }}>{l.source}</span>
                        {l.agent_paused && <span className="tag" style={{ fontSize: 10, color: 'var(--blue)' }}>you've got it</span>}
                        {l.opt_out && <span className="tag" style={{ fontSize: 10, color: 'var(--muted)' }}>opted out</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>}

      {sel && <Conversation id={sel} onClose={() => setSel(null)} onChange={load} />}
      {add && <AddLead onClose={() => setAdd(false)} onAdded={load} v={v} />}
      {imp && <ImportWizard onClose={() => setImp(false)} onDone={load} v={v} />}
    </>
  )
}

function ImportWizard({ onClose, onDone, v }) {
  const [csv, setCsv] = useState('')
  const [inspect, setInspect] = useState(null)
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)
  const ROLES = ['name', 'phone', 'budget', 'requirement', 'location', 'ignore']

  const doInspect = async () => { setBusy(true); try { setInspect(await api.post('/import/inspect', { csv })) } finally { setBusy(false) } }
  const setRole = (idx, role) => setInspect({ ...inspect, columns: inspect.columns.map(c => c.index === idx ? { ...c, role } : c) })
  const commit = async () => {
    const mapping = {}; inspect.columns.forEach(c => { if (c.role !== 'ignore') mapping[c.role] = c.index })
    const r = await api.post('/import/commit', { csv, mapping }); setDone(r); onDone()
  }

  return (
    <Modal title={`Import ${v.inquiry_plural || 'records'}`} onClose={onClose}>
      {!inspect ? <>
        <p className="muted">Paste a CSV (from Excel, your CRM, phone contacts…). We'll inspect the columns and ask you to confirm — never guessing silently.</p>
        <textarea rows={5} value={csv} onChange={(e) => setCsv(e.target.value)}
          placeholder={'Name,Mobile,Budget,Type,Area\nAnil Kumar,+91-98765-43210,9000000,3BHK,OMR'} />
        <button className="btn mt" onClick={doInspect} disabled={!csv.trim() || busy}>{busy ? 'Inspecting…' : 'Inspect columns'}</button>
      </> : done ? (
        <div className="card" style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)' }}>
          <strong style={{ color: 'var(--success-fg)' }}>✓ Imported {done.created} {v.inquiry_plural?.toLowerCase() || 'records'}</strong>
          <div style={{ fontSize: 13, marginTop: 6 }}>Skipped {done.skipped_duplicates} duplicate(s); {done.flagged_for_review} flagged for review (rule U3 — never guessed).</div>
        </div>
      ) : <>
        <div className="flex wrap mb" style={{ fontSize: 12 }}>
          <span className="tag">{inspect.total_rows} rows</span>
          <span className="tag">{inspect.duplicates} duplicates</span>
          <span className="tag" style={{ color: 'var(--amber)' }}>{inspect.flagged} flagged</span>
        </div>
        <h4>Confirm the columns</h4>
        {inspect.columns.map((c) => (
          <div key={c.index} className="between" style={{ padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
            <div><strong style={{ fontSize: 13 }}>{c.header}</strong>
              <div className="muted" style={{ fontSize: 11 }}>{c.question || `e.g. ${(c.sample || []).join(', ')}`}</div></div>
            <select value={c.role} onChange={(e) => setRole(c.index, e.target.value)} style={{ width: 130 }}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        ))}
        <div className="muted mt" style={{ fontSize: 12 }}>{inspect.note}</div>
        <button className="btn mt" style={{ width: '100%' }} onClick={commit}>Import (dedupe on phone)</button>
      </>}
    </Modal>
  )
}

function WhyModal({ interactionId, onClose }) {
  const [why, setWhy] = useState(null)
  const advanced = useMode() === 'advanced'
  useEffect(() => { api.get(`/why/interaction/${interactionId}`).then(setWhy) }, [interactionId])
  return (
    <Modal title="Why did the agent do this?" onClose={onClose}>
      {!why ? <Loading /> : <>
        <div className="card" style={{ background: 'var(--grad-soft)', boxShadow: 'none' }}>
          <div style={{ fontSize: 14 }}>{why.plain}</div>
        </div>
        <details className="mt" open={advanced}>
          <summary style={{ cursor: 'pointer', fontSize: 13, fontWeight: 600 }}>Show technical detail</summary>
          <div className="card mt" style={{ background: 'var(--panel-2)', boxShadow: 'none', fontSize: 12 }}>
            <div className="mb"><strong>Rules applied:</strong> {why.technical.rules_applied.join(', ')}</div>
            <div className="muted">channel: {why.technical.channel} · drafted_by: {why.technical.drafted_by} · status: {why.technical.status} · model: {why.technical.model}</div>
            {why.technical.reviewed_by && <div className="muted">reviewed_by: {why.technical.reviewed_by}</div>}
            {why.technical.validator?.length > 0 && <div className="muted">validator: {why.technical.validator.map(v => v.code).join(', ')}</div>}
            {why.technical.identity_chain && <div className="muted" style={{ marginTop: 4 }}>
              identity: {Object.values(why.technical.identity_chain).join(' · ')}</div>}
          </div>
        </details>
      </>}
    </Modal>
  )
}

function Conversation({ id, onClose, onChange }) {
  const [l, setL] = useState(null)
  const [reply, setReply] = useState('')
  const [tick, setTick] = useState(0)
  const [whyFor, setWhyFor] = useState(null)
  const load = () => api.get(`/leads/${id}`).then(setL)
  useEffect(() => { load() }, [id])
  useEffect(() => { const t = setInterval(() => setTick((x) => x + 1), 1000); return () => clearInterval(t) }, [])
  if (!l) return <Modal title="Lead" onClose={onClose}><Loading /></Modal>

  const act = async (path, body) => { await api.post(`/leads/${id}/${path}`, body); load(); onChange() }
  const recall = async (iid) => { await api.post(`/interactions/${iid}/recall`); load(); onChange() }
  const mistake = async (iid) => { await api.post(`/interactions/${iid}/mistake`, { note: 'Marked wrong by the owner.' }); load(); onChange() }
  const sendReply = async () => { if (!reply.trim()) return; await act('reply', { body: reply }); setReply('') }

  return (
    <Modal title={`${l.name} · ${l.requirement} · ${money(l.budget)}`} onClose={onClose}>
      <div className="flex wrap mb">
        <span className="tag" style={{ color: SCORE[l.score] }}>● {l.score}</span>
        <span className="tag">{l.phone}</span><span className="tag">{l.location}</span>
        <span className="tag">stage: {l.stage}</span>
        {l.agent_paused
          ? <button className="btn green sm" onClick={() => act('handback')}>Hand back to agent</button>
          : <button className="btn secondary sm" onClick={() => act('takeover')}>I've got this one</button>}
      </div>

      <div className="row-actions mb">
        <button className="btn sm" disabled={l.agent_paused} onClick={() => act('qualify')}>Qualify (speed-to-lead)</button>
        <button className="btn secondary sm" disabled={l.agent_paused || l.opt_out} onClick={() => act('followup')}>Send follow-up</button>
        <button className="btn secondary sm" disabled={l.agent_paused} onClick={() => act('visit')}>Offer site visit</button>
      </div>

      <div className="card" style={{ background: 'var(--panel-2)', boxShadow: 'none', maxHeight: 320, overflowY: 'auto' }}>
        {l.interactions.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No messages yet.</div>}
        {l.interactions.map((m) => {
          const out = m.direction === 'out'
          const secs = m.undo_until ? Math.max(0, Math.ceil((new Date(m.undo_until) - Date.now()) / 1000)) : 0
          return (
            <div key={m.id} style={{ display: 'flex', justifyContent: out ? 'flex-end' : 'flex-start', marginBottom: 10 }}>
              <div style={{ maxWidth: '82%' }}>
                <div style={{ padding: '9px 13px', borderRadius: 13, fontSize: 13, whiteSpace: 'pre-wrap',
                  background: m.status === 'held' ? 'var(--danger-bg)' : out ? 'var(--grad)' : 'var(--panel)',
                  color: m.status === 'held' ? 'var(--danger-fg)' : out && m.status !== 'held' ? '#fff' : 'var(--text)',
                  border: out && m.status !== 'held' ? 'none' : '1px solid var(--border)' }}>
                  {m.body}
                </div>
                <div className="flex wrap" style={{ gap: 6, marginTop: 3, justifyContent: out ? 'flex-end' : 'flex-start' }}>
                  <span className="muted" style={{ fontSize: 10 }}>{m.channel} · {m.drafted_by}</span>
                  {m.status === 'queued' && <>
                    <span className="tag" style={{ fontSize: 10, color: 'var(--amber)' }}>sending in {secs}s</span>
                    <button className="btn danger sm" style={{ padding: '1px 7px', fontSize: 11 }} onClick={() => recall(m.id)}>Recall</button>
                  </>}
                  {m.status === 'held' && <span className="tag" style={{ fontSize: 10, color: 'var(--red)' }}>
                    🚫 held: {(m.validator || []).map(v => v.code).join(', ') || 'needs your approval'}</span>}
                  {m.reviewed_by && <span className="tag" style={{ fontSize: 10, color: 'var(--green)' }}>✓ reviewed by you</span>}
                  {out && <button className="btn ghost sm" style={{ padding: '1px 7px', fontSize: 11 }}
                    onClick={() => setWhyFor(m.id)}>Why?</button>}
                  {m.status === 'sent' && out && <button className="btn ghost sm" style={{ padding: '1px 7px', fontSize: 11 }}
                    onClick={() => mistake(m.id)}>That was wrong</button>}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex mt">
        <input value={reply} onChange={(e) => setReply(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && sendReply()}
          placeholder="Reply yourself (this pauses the agent on this thread)…" />
        <button className="btn" onClick={sendReply}><Icon name="send" size={16} /></button>
      </div>
      {whyFor && <WhyModal interactionId={whyFor} onClose={() => setWhyFor(null)} />}
    </Modal>
  )
}

function AddLead({ onClose, onAdded }) {
  const [f, setF] = useState({ name: '', phone: '', requirement: '3BHK', budget: '', location: '', source: 'manual' })
  const [msg, setMsg] = useState('')
  const submit = async () => {
    const r = await api.post('/leads', { ...f, budget: Number(f.budget) || null })
    if (r.status === 'duplicate') { setMsg(r.message); return }
    onAdded(); onClose()
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <Modal title="Add a lead" onClose={onClose}>
      {msg && <div className="error-box">{msg}</div>}
      <div className="grid cols-2" style={{ gap: 12 }}>
        <div className="field"><label>Name</label><input value={f.name} onChange={set('name')} autoFocus /></div>
        <div className="field"><label>Phone (dedupe key)</label><input value={f.phone} onChange={set('phone')} /></div>
        <div className="field"><label>Requirement</label><input value={f.requirement} onChange={set('requirement')} /></div>
        <div className="field"><label>Budget (₹)</label><input type="number" value={f.budget} onChange={set('budget')} /></div>
        <div className="field"><label>Location</label><input value={f.location} onChange={set('location')} /></div>
        <div className="field"><label>Source</label>
          <select value={f.source} onChange={set('source')}>
            <option value="manual">Manual / voice</option><option value="portal">Portal</option>
            <option value="whatsapp">WhatsApp</option></select></div>
      </div>
      <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={!f.name || !f.phone}>Capture lead</button>
    </Modal>
  )
}
