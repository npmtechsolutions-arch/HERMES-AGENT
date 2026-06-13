import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead } from '../components/ui'

const TYPE_COLOR = {
  customer: '#36d399', vendor: '#ff9f43', project: '#6c8cff', agent: '#b07cff',
  document: '#4dabff', policy: '#ffcf5c', task: '#ff5d6c', contact: '#8c94ad',
  product: '#2dd4bf', custom: '#8c94ad',
}
const TYPES = ['customer', 'vendor', 'contact', 'project', 'task', 'document', 'agent', 'policy', 'product']

export default function Graph() {
  const [g, setG] = useState(null)
  const [sel, setSel] = useState(null)
  const [q, setQ] = useState('')
  const [modal, setModal] = useState(null)   // 'entity' | 'relation'
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const gRef = useRef(null); gRef.current = g

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = (keepSel) => api.get('/graph').then((d) => { setG(d); if (keepSel) setSel((s) => s && d.entities.find((e) => e.id === s.id)) }).catch(() => flash('err', 'Could not load the graph.'))
  useEffect(() => { load() }, [])

  const addEntity = async (type, name, attrs = {}) => {
    try { const r = await api.post('/graph/entities', { type, name, attrs }); flash('ok', r.message); speak(r.message); await load(); return r }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not add the entity.'); return null }
  }
  const connect = async (from_id, to_id, relation) => {
    try { const r = await api.post('/graph/relations', { from_id, to_id, relation }); flash('ok', r.message); speak(r.message); await load(true) }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not link those.') }
  }
  const delEntity = async (e) => {
    if (!window.confirm(`Remove “${e.name}” and all its relationships?`)) return
    try { const r = await api.del(`/graph/entities/${e.id}`); flash('ok', r.message); speak(r.message); setSel(null); load() }
    catch (er) { flash('err', er?.detail?.message || er?.message || 'Could not remove the entity.') }
  }
  const delRelation = async (rid) => {
    try { const r = await api.del(`/graph/relations/${rid}`); flash('ok', r.message); load(true) }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not remove the relationship.') }
  }
  const loadDemo = async () => {
    try { const r = await api.post('/graph/demo'); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.message || 'Could not load the demo graph.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/graph/resolve', { transcript: phrase })
      const find = (id) => (gRef.current?.entities || []).find((e) => e.id === id)
      switch (r.action) {
        case 'demo': await loadDemo(); break
        case 'add_entity': await addEntity(r.type, r.name); break
        case 'connect': await connect(r.from_id, r.to_id, r.relation); break
        case 'delete_entity': { const e = find(r.id); if (e) await delEntity(e) } break
        case 'focus': { const e = find(r.id); if (e) { setSel(e); setQ(''); flash('ok', r.message) } } break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__graphVoice = (t) => { runCommand(t); return true }; return () => { if (window.__graphVoice) delete window.__graphVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!g) return <Loading />

  const W = 900, H = 460, cx = W / 2, cy = H / 2
  const pos = {}
  g.entities.forEach((e, i) => {
    const ang = (i / Math.max(1, g.entities.length)) * Math.PI * 2
    pos[e.id] = { x: cx + 160 * Math.cos(ang), y: cy + 160 * Math.sin(ang) }
  })
  const neighbors = sel ? new Set(g.relations.filter((r) => r.from_id === sel.id || r.to_id === sel.id)
    .flatMap((r) => [r.from_id, r.to_id])) : null
  const matchQ = (e) => q && e.name.toLowerCase().includes(q.toLowerCase())
  const dim = (id) => (sel && !neighbors.has(id) && id !== sel.id) || (q && !matchQ(g.entities.find((e) => e.id === id)))
  const selRels = sel ? g.relations.filter((r) => r.from_id === sel.id || r.to_id === sel.id) : []
  const nameOf = (id) => g.entities.find((e) => e.id === id)?.name || '?'

  return (
    <>
      <PageHead title="Knowledge Graph" sub="Entities & typed relationships powering graph-augmented retrieval.">
        <div className="flex" style={{ gap: 8 }}>
          <button className="btn secondary sm" onClick={() => setModal('entity')}><Icon name="plus" size={14} /> Entity</button>
          <button className="btn secondary sm" onClick={() => setModal('relation')} disabled={g.entities.length < 2}><Icon name="link" size={14} /> Link</button>
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "add a customer named Acme", "connect Acme to the OMR project as client_of", "focus on Acme", "remove PrintFast"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {g.entities.length === 0 && (
        <div className="card mb between" style={{ alignItems: 'center' }}>
          <span className="muted" style={{ fontSize: 13 }}>No entities yet. Add one, or load a sample graph to explore.</span>
          <button className="btn sm" onClick={loadDemo}><Icon name="plus" size={14} /> Load sample graph</button>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: '1fr 300px' }}>
        <div className="card" style={{ padding: 8 }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search / highlight entities…"
            style={{ width: '100%', marginBottom: 6 }} />
          <svg className="graph-svg" viewBox={`0 0 ${W} ${H}`}>
            {g.relations.map((r) => {
              const a = pos[r.from_id], b = pos[r.to_id]
              if (!a || !b) return null
              const active = sel && (r.from_id === sel.id || r.to_id === sel.id)
              return <g key={r.id} opacity={sel && !active ? 0.25 : 1}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={active ? 'var(--primary)' : 'var(--border)'} strokeWidth={active ? 2 : 1.5} />
                <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2} fill="var(--muted)" fontSize="10" textAnchor="middle">{r.relation}</text>
              </g>
            })}
            {g.entities.map((e) => {
              const p = pos[e.id]
              return <g key={e.id} onClick={() => setSel(sel?.id === e.id ? null : e)} style={{ cursor: 'pointer' }}>
                <circle cx={p.x} cy={p.y} r="26" fill={TYPE_COLOR[e.type] || '#8c94ad'}
                  stroke={sel?.id === e.id ? 'var(--primary)' : (matchQ(e) ? 'var(--amber)' : 'none')} strokeWidth="3"
                  opacity={dim(e.id) ? 0.25 : 0.9} />
                <text x={p.x} y={p.y + 42} fill="var(--text)" fontSize="11" textAnchor="middle" opacity={dim(e.id) ? 0.35 : 1}>{e.name}</text>
                <text x={p.x} y={p.y + 4} fill="#fff" fontSize="10" fontWeight="700" textAnchor="middle">{e.type[0].toUpperCase()}</text>
              </g>
            })}
          </svg>
        </div>

        <div className="card">
          {!sel && <>
            <h3 style={{ marginTop: 0 }}>Legend</h3>
            {Object.entries(TYPE_COLOR).filter(([t]) => g.entities.some((e) => e.type === t)).map(([t, c]) => (
              <div key={t} className="flex" style={{ marginBottom: 6, fontSize: 13 }}>
                <span style={{ width: 12, height: 12, borderRadius: 3, background: c, display: 'inline-block' }} />
                <span style={{ textTransform: 'capitalize' }}>{t} · {g.entities.filter((e) => e.type === t).length}</span>
              </div>
            ))}
            <div className="muted mt" style={{ fontSize: 12 }}>{g.entities.length} entities · {g.relations.length} relationships</div>
          </>}
          {sel && <>
            <div className="between"><h4 style={{ margin: 0 }}>{sel.name}</h4>
              <button className="icon-btn" style={{ width: 28, height: 28 }} onClick={() => setSel(null)}><Icon name="x" size={13} /></button></div>
            <div className="tag" style={{ textTransform: 'capitalize' }}>{sel.type}</div>
            {Object.entries(sel.attrs || {}).length > 0 && <div className="mt" style={{ fontSize: 12 }}>
              {Object.entries(sel.attrs || {}).map(([k, v]) => (
                <div key={k} className="muted">{k}: <span style={{ color: 'var(--text)' }}>{String(v)}</span></div>))}
            </div>}
            <h5 className="mt" style={{ marginBottom: 4 }}>Relationships · {selRels.length}</h5>
            {selRels.map((r) => (
              <div key={r.id} className="between" style={{ fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
                <span>{r.from_id === sel.id ? '→' : '←'} <strong>{r.from_id === sel.id ? nameOf(r.to_id) : nameOf(r.from_id)}</strong> <span className="muted">({r.relation})</span></span>
                <button className="icon-btn" style={{ width: 24, height: 24 }} title="Remove link" onClick={() => delRelation(r.id)}><Icon name="x" size={11} /></button>
              </div>
            ))}
            {selRels.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No relationships.</div>}
            <button className="btn danger sm mt" onClick={() => delEntity(sel)}>Remove entity</button>
          </>}
        </div>
      </div>

      {modal === 'entity' && <EntityModal onClose={() => setModal(null)} onAdd={addEntity} />}
      {modal === 'relation' && <RelationModal entities={g.entities} onClose={() => setModal(null)} onConnect={connect} />}
    </>
  )
}

function EntityModal({ onClose, onAdd }) {
  const [type, setType] = useState('customer')
  const [name, setName] = useState('')
  return (
    <Modal title="Add entity" onClose={onClose}>
      <div className="field"><label>Type</label>
        <select value={type} onChange={(e) => setType(e.target.value)}>{TYPES.map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
      <div className="field"><label>Name</label><input autoFocus value={name} onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && name.trim()) { onAdd(type, name.trim()); onClose() } }} /></div>
      <button className="btn" style={{ width: '100%' }} disabled={!name.trim()} onClick={() => { onAdd(type, name.trim()); onClose() }}>Add</button>
    </Modal>
  )
}

function RelationModal({ entities, onClose, onConnect }) {
  const [from, setFrom] = useState(entities[0]?.id || '')
  const [to, setTo] = useState(entities[1]?.id || '')
  const [rel, setRel] = useState('related_to')
  return (
    <Modal title="Link entities" onClose={onClose}>
      <div className="field"><label>From</label>
        <select value={from} onChange={(e) => setFrom(e.target.value)}>{entities.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></div>
      <div className="field"><label>Relationship</label><input value={rel} onChange={(e) => setRel(e.target.value)} placeholder="e.g. client_of, supplies, governs" /></div>
      <div className="field"><label>To</label>
        <select value={to} onChange={(e) => setTo(e.target.value)}>{entities.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></div>
      <button className="btn" style={{ width: '100%' }} disabled={!from || !to || from === to}
        onClick={() => { onConnect(from, to, rel.trim() || 'related_to'); onClose() }}>Link</button>
    </Modal>
  )
}
