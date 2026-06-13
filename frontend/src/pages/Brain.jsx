import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead } from '../components/ui'

const CLASSES = ['personal', 'business', 'knowledge', 'operational']

export default function Brain() {
  const [items, setItems] = useState(null)
  const [forgotten, setForgotten] = useState([])
  const [showForgotten, setShowForgotten] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [mode, setMode] = useState(null)
  const [classFilter, setClassFilter] = useState('')
  const [ingest, setIngest] = useState(false)
  const [ingestSeed, setIngestSeed] = useState(null)
  const [params] = useSearchParams()
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([
    api.get('/memory/items').then(setItems),
    api.get('/memory/forgotten').then(setForgotten).catch(() => {}),
  ]).catch(() => flash('err', 'Could not load your memory.'))
  useEffect(() => { load() }, [])
  useEffect(() => { const q = params.get('q'); if (q) { setQuery(q); doSearch(q) } }, [params]) // eslint-disable-line

  const doSearch = async (q) => {
    const term = (q || query).trim()
    if (!term) { flash('err', 'Type or say what to search for.'); return }
    try { const r = await api.post('/memory/search', { query: term, top_k: 8 }); setResults(r.results); setMode(r.mode); flash(r.results.length ? 'ok' : 'err', r.message); speak(r.message) }
    catch (e) { flash('err', e?.message || 'Search failed.') }
  }
  const forget = async (m) => {
    if (!window.confirm(`Forget “${m.title}”? It stays recoverable for 30 days.`)) return
    try { const r = await api.del(`/memory/items/${m.id}`); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not forget that.') }
  }
  const restore = async (m) => {
    try { const r = await api.post(`/memory/items/${m.id}/restore`); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not restore that.') }
  }
  const loadDemo = async () => {
    try { const r = await api.post('/memory/demo'); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.message || 'Could not load the starter brain.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/memory/resolve', { transcript: phrase })
      const find = (id) => [...(items || []), ...forgotten].find((x) => x.id === id)
      switch (r.action) {
        case 'demo': await loadDemo(); break
        case 'search': setQuery(r.query); await doSearch(r.query); break
        case 'filter': setClassFilter(r.memory_class); flash('ok', r.message); break
        case 'ingest': { const res = await api.post('/memory/ingest', { title: r.title, body: r.body, memory_class: r.memory_class }); flash('ok', res.message); speak(res.message); load() } break
        case 'ingest_open': setIngestSeed(null); setIngest(true); flash('ok', r.message); break
        case 'forget': { const m = find(r.id); if (m) await forget(m) } break
        case 'restore': { const m = find(r.id) || { id: r.id, title: r.name }; await restore(m) } break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__brainVoice = (t) => { runCommand(t); return true }; return () => { if (window.__brainVoice) delete window.__brainVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!items) return <Loading />
  const visibleClasses = classFilter ? [classFilter] : CLASSES
  return (
    <>
      <PageHead title="Second Brain" sub="Semantic + keyword search across your private memory. All local.">
        <div className="flex" style={{ gap: 8 }}>
          {forgotten.length > 0 && <button className="btn ghost sm" onClick={() => setShowForgotten((v) => !v)}>
            <Icon name="refresh" size={14} /> Forgotten ({forgotten.length})</button>}
          <button className="btn" onClick={() => { setIngestSeed(null); setIngest(true) }}><Icon name="plus" size={16} /> Ingest knowledge</button>
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "search for the Sharma quote", "remember that the wifi is HERMUS-Guest", "forget the refund policy", "restore it"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="card mb">
        <div className="flex">
          <input value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && doSearch()}
            placeholder='Ask: "What did we quote Sharma?" or "GST filing SOP"' />
          <button className="btn" onClick={() => doSearch()}>Search</button>
        </div>
        {results && <div className="mt">
          <div className="between mb">
            <div className="muted" style={{ fontSize: 12 }}>{results.length} results
              {mode && <span className="tag" style={{ marginLeft: 6,
                color: mode.includes('semantic') ? 'var(--accent)' : 'var(--muted)' }}>{mode}</span>}</div>
            <button className="btn ghost sm" onClick={() => { setResults(null); setQuery('') }}>Clear</button>
          </div>
          {results.map((r) => (
            <div key={r.id} className="card mb" style={{ background: 'var(--bg-2)' }}>
              <div className="between"><strong>{r.title}</strong>
                <span className="tag">{r.memory_class} · score {r.score}</span></div>
              <div style={{ fontSize: 13, margin: '6px 0' }}>{r.snippet}</div>
              <div className="cite">📎 {r.citation}</div>
            </div>
          ))}
          {results.length === 0 && <div className="muted">No matches.</div>}
        </div>}
      </div>

      {showForgotten && (
        <div className="card mb" style={{ borderColor: 'var(--amber)' }}>
          <h3 style={{ marginTop: 0 }}>Recently forgotten · {forgotten.length} <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>(recoverable 30 days)</span></h3>
          {forgotten.map((m) => (
            <div key={m.id} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div><div style={{ fontSize: 13, fontWeight: 600 }}>{m.title}</div>
                <div className="muted" style={{ fontSize: 12 }}>{m.snippet}</div></div>
              <button className="btn secondary sm" onClick={() => restore(m)}>↩ Restore</button>
            </div>
          ))}
          {forgotten.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Nothing forgotten.</div>}
        </div>
      )}

      {items.length === 0 && (
        <div className="card mb between" style={{ alignItems: 'center' }}>
          <span className="muted" style={{ fontSize: 13 }}>Your Second Brain is empty. Ingest a note, or load a starter set to explore search.</span>
          <button className="btn sm" onClick={loadDemo}><Icon name="plus" size={14} /> Load starter brain</button>
        </div>
      )}

      {classFilter && <div className="muted mb" style={{ fontSize: 12 }}>
        Filtered to <strong>{classFilter}</strong> · <button className="btn ghost sm" onClick={() => setClassFilter('')}>show all</button></div>}

      <div className="grid cols-2">
        {visibleClasses.map((cls) => {
          const list = items.filter((m) => m.memory_class === cls)
          return (
            <div className="card" key={cls}>
              <h3 style={{ textTransform: 'capitalize' }}>{cls} memory · {list.length}</h3>
              {list.map((m) => (
                <div key={m.id} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{m.title}
                      {m.pii && <span className="tag" style={{ marginLeft: 6, color: 'var(--amber)' }}>PII</span>}</div>
                    <div className="muted" style={{ fontSize: 12 }}>{m.snippet}</div>
                  </div>
                  <button className="btn ghost sm" onClick={() => forget(m)} title="Forget (MC-04)">Forget</button>
                </div>
              ))}
              {list.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Empty.</div>}
            </div>
          )
        })}
      </div>

      {ingest && <IngestModal seed={ingestSeed} onClose={() => setIngest(false)} onDone={load} onFlash={flash} onSpeak={speak} />}
    </>
  )
}

function IngestModal({ seed, onClose, onDone, onFlash, onSpeak }) {
  const [f, setF] = useState({ title: seed?.title || '', body: seed?.body || '', memory_class: seed?.memory_class || 'knowledge' })
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try {
      const r = await api.post('/memory/ingest', f)
      setMsg(r.message)
      if (r.status === 'duplicate') { onFlash('err', r.message) }
      else { onFlash('ok', r.message); onSpeak(r.message); onDone(); setTimeout(onClose, 800) }
    } catch (e) { setMsg(''); onFlash('err', e?.detail?.message || e?.message || 'Ingest failed.') }
    finally { setBusy(false) }
  }
  return (
    <Modal title="Ingest into Second Brain" onClose={onClose}>
      <p className="muted">Paste a document, note, or transcript. (OCR/AV transcription in desktop app.)</p>
      {msg && <div className="error-box" style={{ background: 'var(--panel-2)', color: 'var(--text)', borderColor: 'var(--border)' }}>{msg}</div>}
      <div className="field"><label>Title</label><input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></div>
      <div className="field"><label>Class</label>
        <select value={f.memory_class} onChange={(e) => setF({ ...f, memory_class: e.target.value })}>
          {CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}</select></div>
      <div className="field"><label>Content</label><textarea rows={5} value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} /></div>
      <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={!f.title || !f.body || busy}>{busy ? 'Ingesting…' : 'Ingest'}</button>
    </Modal>
  )
}
