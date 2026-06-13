import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead } from '../components/ui'

const PAIN = { high: ['🔴', 'var(--red)'], medium: ['🟡', 'var(--amber)'], low: ['🟢', 'var(--green)'] }
const COMP = { low: ['🟢 low comp', 'var(--green)'], medium: ['🟡 med comp', 'var(--amber)'], high: ['🔴 high comp', 'var(--red)'] }
const RANK = { 1: '🥇 #1 pick', 2: '🥈 #2 pick', 3: '🥉 #3 pick' }

export default function Solutions() {
  const [data, setData] = useState(null)            // { categories, count, solutions }
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(null)
  const [msg, setMsg] = useState(null)              // { kind, text }
  const [loadErr, setLoadErr] = useState(false)
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('All')
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const load = () => api.get('/solutions').then((d) => { setData(d); setLoadErr(false) }).catch(() => setLoadErr(true))
  useEffect(() => { load() }, [])

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const find = (sid) => (data?.solutions || []).find((s) => s.id === sid)

  const deploy = async (s) => {
    if (!s || busy) return
    setBusy(s.id)
    try { const r = await api.post(`/solutions/${s.id}/deploy`); flash('ok', r.message || `${s.name} deployed.`); await load() }
    catch (e) { flash('err', e?.message || `Couldn't deploy ${s.name}.`) }
    finally { setBusy(null) }
  }
  const undeploy = async (s) => {
    if (!s || busy) return
    setBusy(s.id)
    try { const r = await api.post(`/solutions/${s.id}/undeploy`); flash('ok', r.message || `${s.name} removed.`); await load() }
    catch (e) { flash('err', e?.message || `Couldn't undeploy ${s.name}.`) }
    finally { setBusy(null) }
  }

  // ── voice / natural-language command ───────────────────────────────────────
  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    try {
      const r = await api.post('/solutions/resolve', { transcript: phrase })
      const s = r.sid ? find(r.sid) : null
      if (r.action === 'deploy') { s?.deployed ? flash('err', `${s.name} is already deployed.`) : await deploy(s) }
      else if (r.action === 'undeploy') { (s && !s.deployed) ? flash('err', `${s.name} isn't deployed.`) : await undeploy(s) }
      else if (r.action === 'open') setDetail(s)
      else if (r.action === 'close') setDetail(null)
      else flash('err', r.message || "I didn't catch a solution action.")
    } catch (e) { flash('err', e?.message || 'Could not run that command.') }
    setCmd('')
  }
  useEffect(() => { window.__solutionsVoice = (t) => { runCommand(t); return true }; return () => { if (window.__solutionsVoice) delete window.__solutionsVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (loadErr) return (
    <>
      <PageHead title="Solutions" />
      <div className="card" style={{ textAlign: 'center', padding: 32 }}>
        <p className="muted">Couldn't load the solutions.</p>
        <button className="btn sm" onClick={load}>Retry</button>
      </div>
    </>
  )
  if (!data) return <Loading />

  const all = data.solutions
  const deployedCount = all.filter((s) => s.deployed).length
  const top = all.filter((s) => s.rank).sort((a, b) => a.rank - b.rank)
  const ql = q.trim().toLowerCase()
  const matches = (s) => !ql || [s.name, s.tagline, s.problem, s.target, s.category]
    .some((x) => (x || '').toLowerCase().includes(ql))
  const visible = all.filter((s) => (cat === 'All' || s.category === cat) && matches(s))
  const cats = ['All', ...data.categories]

  return (
    <>
      <PageHead title="Solutions"
        sub={`${data.count} focused, ready-made AI agents for real SMB pain — deploy one in a click, undeploy any time. Simpler than a CRM. You can also just say what you want.`} />

      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {/* Voice / command bar */}
      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "deploy review generation", "uninstall the no-show prevention", "show daily briefing"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}>
            <Icon name="send" size={13} /> Run</button>
        </div>
      </div>

      {/* Top picks */}
      {top.length > 0 && cat === 'All' && !ql && (
        <div className="card mb" style={{ background: 'var(--grad)', color: '#fff', border: 'none' }}>
          <h3 style={{ color: '#fff', margin: '0 0 10px' }}><Icon name="sparkles" size={17} /> Top picks (best fit × market gap × willingness-to-pay)</h3>
          <div className="grid cols-3">
            {top.map((s) => (
              <div key={s.id} style={{ background: 'rgba(255,255,255,.14)', borderRadius: 12, padding: 14 }}>
                <div style={{ fontWeight: 700 }}>{RANK[s.rank]} — {s.emoji} {s.name}</div>
                <div style={{ fontSize: 12.5, color: 'rgba(255,255,255,.9)', marginTop: 4 }}>{s.tagline}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Search + category filter */}
      <div className="flex mb" style={{ gap: 8 }}>
        <div className="searchbar" style={{ flex: 1, maxWidth: 360 }}>
          <Icon name="search" size={15} />
          <input style={{ border: 'none', background: 'transparent', outline: 'none', width: '100%' }}
            value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search solutions…" />
        </div>
        <span className="muted" style={{ fontSize: 12, alignSelf: 'center' }}>
          {visible.length} shown · {deployedCount} deployed</span>
      </div>
      <div className="flex wrap mb" style={{ gap: 5 }}>
        {cats.map((c) => (
          <button key={c} className="tag" style={{ cursor: 'pointer',
            ...(cat === c ? { background: 'var(--primary)', color: '#fff' } : {}) }}
            onClick={() => setCat(c)}>{c}</button>
        ))}
      </div>

      {visible.length === 0 && <div className="card" style={{ textAlign: 'center', padding: 24 }}>
        <p className="muted">No solutions match “{q}”.</p></div>}
      {(cat === 'All' ? data.categories : [cat]).map((c) => {
        const items = visible.filter((s) => s.category === c)
        if (!items.length) return null
        return (
          <div key={c} style={{ marginBottom: 18 }}>
            <div className="nav-group-label" style={{ marginBottom: 8 }}>{c} · {items.length}</div>
            <div className="grid cols-3">
              {items.map((s) => (
                <SCard key={s.id} s={s} busy={busy === s.id}
                  onDetail={() => setDetail(s)} onDeploy={() => deploy(s)} onUndeploy={() => undeploy(s)} />
              ))}
            </div>
          </div>
        )
      })}

      {detail && <DetailModal s={detail} busy={busy === detail.id} onClose={() => setDetail(null)}
        onDeploy={() => { deploy(detail); setDetail(null) }} onUndeploy={() => { undeploy(detail); setDetail(null) }} />}
    </>
  )
}

function SCard({ s, busy, onDetail, onDeploy, onUndeploy }) {
  return (
    <div className="card" style={s.rank ? { borderColor: 'var(--primary)' } : {}}>
      <div className="between mb">
        <div className="flex" style={{ gap: 6 }}>
          <span style={{ fontSize: 20 }}>{s.emoji}</span>
          <span title={`pain: ${s.pain}`}>{PAIN[s.pain][0]}</span>
          {s.rank && <span className="tag" style={{ color: 'var(--primary)', fontSize: 10 }}>{RANK[s.rank]}</span>}
        </div>
        <span className="tag" style={{ color: 'var(--green)' }}>{s.price}/mo</span>
      </div>
      <h3 style={{ margin: 0, fontSize: 15 }}>{s.name}</h3>
      <div className="muted" style={{ fontSize: 12.5, margin: '3px 0 8px' }}>{s.tagline}</div>
      <div style={{ fontSize: 12, color: 'var(--text)', minHeight: 46 }}>{s.problem}</div>
      <div className="flex wrap mb mt" style={{ gap: 4 }}>
        <span className="tag" style={{ fontSize: 10, color: COMP[s.competition][1] }}>{COMP[s.competition][0]}</span>
        <span className="tag" style={{ fontSize: 10 }}>{s.difficulty}</span>
        {s.engines.map((e) => <span key={e} className="tag" style={{ fontSize: 10, color: 'var(--primary)' }}>{e}</span>)}
      </div>
      <div className="between">
        <button className="btn ghost sm" onClick={onDetail}>Details</button>
        {s.deployed
          ? <div className="flex" style={{ gap: 6 }}>
              <span className="pill st-active" style={{ fontSize: 11 }}><span className="dot" /> deployed</span>
              <button className="btn ghost sm" disabled={busy} onClick={onUndeploy} title="Remove this agent">
                {busy ? '…' : 'Undeploy'}</button>
            </div>
          : <button className="btn sm" disabled={busy} onClick={onDeploy}>
              <Icon name="zap" size={13} /> {busy ? 'Setting up…' : 'Deploy'}</button>}
      </div>
    </div>
  )
}

function DetailModal({ s, busy, onClose, onDeploy, onUndeploy }) {
  return (
    <Modal title={`${s.emoji} ${s.name}`} onClose={onClose}>
      <div className="flex wrap mb">
        {s.rank && <span className="tag" style={{ color: 'var(--primary)' }}>{RANK[s.rank]}</span>}
        <span className="tag">{PAIN[s.pain][0]} {s.pain} pain</span>
        <span className="tag" style={{ color: COMP[s.competition][1] }}>{COMP[s.competition][0]}</span>
        <span className="tag" style={{ color: 'var(--green)' }}>{s.price}/mo</span>
        <span className="tag">{s.category}</span>
        <span className="tag">{s.difficulty}</span>
      </div>
      <p style={{ fontSize: 14 }}>{s.tagline}</p>
      <h4>Target</h4><div className="muted" style={{ fontSize: 13 }}>{s.target}</div>
      <h4>The problem</h4><div className="muted" style={{ fontSize: 13 }}>{s.problem}</div>
      <h4>What the agent does</h4>
      <div>{s.flow.map((f, i) => (
        <div key={i} className="flex" style={{ fontSize: 13, padding: '3px 0' }}>
          <span className="tag" style={{ minWidth: 22, justifyContent: 'center' }}>{i + 1}</span>{f}</div>))}</div>
      <h4>Why it works</h4><div className="muted" style={{ fontSize: 13 }}>{s.why}</div>
      <div className="flex wrap mt mb">
        <span className="muted" style={{ fontSize: 12 }}>Engines:</span>{s.engines.map((e) => <span key={e} className="tag">{e}</span>)}
        <span className="muted" style={{ fontSize: 12, marginLeft: 8 }}>Recipes:</span>{s.recipes.map((r) => <span key={r} className="tag">{r}</span>)}
      </div>
      {s.deployed
        ? <button className="btn ghost" style={{ width: '100%' }} disabled={busy} onClick={onUndeploy}>
            <Icon name="x" size={15} /> {busy ? 'Removing…' : `Undeploy ${s.name}`}</button>
        : <button className="btn" style={{ width: '100%' }} disabled={busy} onClick={onDeploy}>
            <Icon name="zap" size={15} /> {busy ? 'Setting up…' : 'Deploy this agent'}</button>}
    </Modal>
  )
}
