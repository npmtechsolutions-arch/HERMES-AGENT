import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead } from '../components/ui'

export default function Verticals() {
  const nav = useNavigate()
  const [data, setData] = useState(null)          // { categories, verticals }
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(null)
  const [msg, setMsg] = useState(null)            // { kind:'ok'|'err', text }
  const [loadErr, setLoadErr] = useState(false)
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('All')
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const load = () => api.get('/verticals').then((d) => { setData(d); setLoadErr(false) })
    .catch(() => setLoadErr(true))
  useEffect(() => { load() }, [])

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const find = (vid) => (data?.verticals || []).find((v) => v.id === vid)

  const deploy = async (v) => {
    if (!v || busy) return
    setBusy(v.id)
    try {
      const r = await api.post(`/verticals/${v.id}/deploy`)
      flash('ok', r.message || `${v.name} deployed.`)
      await load()
      window.dispatchEvent(new Event('hermus:skin-changed'))
      // A deploy creates a full workspace — hand the user to Guided Setup to finish
      // the remaining steps (tune the agent, connect a channel) and confirm what's live.
      nav(`/guided-setup?from=vertical&name=${encodeURIComponent(v.name)}`)
    } catch (e) { flash('err', e?.message || `Couldn't deploy ${v.name}.`) }
    finally { setBusy(null) }
  }

  const undeploy = async (v) => {
    if (!v || busy) return
    setBusy(v.id)
    try {
      const r = await api.post(`/verticals/${v.id}/undeploy`)
      flash('ok', r.message || `${v.name} removed.`)
      await load()
      window.dispatchEvent(new Event('hermus:skin-changed'))
    } catch (e) { flash('err', e?.message || `Couldn't undeploy ${v.name}.`) }
    finally { setBusy(null) }
  }

  // ── voice / natural-language command ───────────────────────────────────────
  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    try {
      const r = await api.post('/verticals/resolve', { transcript: phrase })
      const v = r.vid ? find(r.vid) : null
      if (r.action === 'deploy') {
        if (v?.deployed) flash('err', `${v.name} is already deployed.`)
        else await deploy(v)
      } else if (r.action === 'undeploy') {
        if (v && !v.deployed) flash('err', `${v.name} isn't deployed.`)
        else await undeploy(v)
      } else if (r.action === 'open') { setDetail(v) }
      else if (r.action === 'close') { setDetail(null) }
      else { flash('err', r.message || "I didn't catch a vertical action.") }
    } catch (e) { flash('err', e?.message || 'Could not run that command.') }
    setCmd('')
  }

  // register so the global voice orb can drive this page too
  useEffect(() => {
    window.__verticalsVoice = (t) => { runCommand(t); return true }
    return () => { if (window.__verticalsVoice) delete window.__verticalsVoice }
  })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false)
    r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (loadErr) return (
    <>
      <PageHead title="Vertical Agents" />
      <div className="card" style={{ textAlign: 'center', padding: 32 }}>
        <p className="muted">Couldn't load the vertical agents.</p>
        <button className="btn sm" onClick={load}>Retry</button>
      </div>
    </>
  )
  if (!data) return <Loading />

  const all = data.verticals
  const deployedCount = all.filter((v) => v.deployed).length
  const ql = q.trim().toLowerCase()
  const matches = (v) => !ql || [v.name, v.for, v.industry, v.tagline, v.category]
    .some((s) => (s || '').toLowerCase().includes(ql))
  const visible = all.filter((v) => (cat === 'All' || v.category === cat) && matches(v))
  const cats = ['All', ...data.categories]

  return (
    <>
      <PageHead title="Vertical Agents"
        sub={`${data.count} ready-made AI agents across ${data.categories.length} industries. Pick yours — it deploys in one click, and you can undeploy any time. You can also just say what you want.`} />

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
            placeholder={listening ? 'Listening…' : 'Say or type: "deploy the dentist agent", "uninstall the restaurant agent", "show the gym agent"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}>
            <Icon name="send" size={13} /> Run</button>
        </div>
      </div>

      {/* Search + category filter */}
      <div className="flex mb" style={{ gap: 8 }}>
        <div className="searchbar" style={{ flex: 1, maxWidth: 360 }}>
          <Icon name="search" size={15} />
          <input style={{ border: 'none', background: 'transparent', outline: 'none', width: '100%' }}
            value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search verticals…" />
        </div>
        <span className="muted" style={{ fontSize: 12, alignSelf: 'center' }}>
          {visible.length} shown · {deployedCount} deployed</span>
      </div>
      <div className="flex wrap mb" style={{ gap: 5 }}>
        {cats.map((c) => (
          <button key={c} className={`tag${cat === c ? ' active' : ''}`} style={{ cursor: 'pointer',
            ...(cat === c ? { background: 'var(--primary)', color: '#fff' } : {}) }}
            onClick={() => setCat(c)}>{c}</button>
        ))}
      </div>

      {/* Cards grouped by category */}
      {visible.length === 0 && <div className="card" style={{ textAlign: 'center', padding: 24 }}>
        <p className="muted">No verticals match “{q}”.</p></div>}
      {(cat === 'All' ? data.categories : [cat]).map((c) => {
        const items = visible.filter((v) => v.category === c)
        if (!items.length) return null
        return (
          <div key={c} style={{ marginBottom: 18 }}>
            <div className="nav-group-label" style={{ marginBottom: 8 }}>{c} · {items.length}</div>
            <div className="grid cols-3">
              {items.map((v) => (
                <VCard key={v.id} v={v} busy={busy === v.id}
                  onDetail={() => setDetail(v)} onDeploy={() => deploy(v)} onUndeploy={() => undeploy(v)} />
              ))}
            </div>
          </div>
        )
      })}

      <div className="card mt" style={{ background: 'var(--grad-soft)' }}>
        <div className="flex" style={{ fontSize: 13 }}><Icon name="sparkles" size={15} style={{ color: 'var(--primary)' }} />
          <span>Each vertical is the <strong>same universal core</strong>, configured: an industry roster + the right
            automations + a persona concierge + compliance — deployed (or removed) as one product.</span></div>
      </div>

      {detail && <DetailModal v={detail} busy={busy === detail.id} onClose={() => setDetail(null)}
        onDeploy={() => { deploy(detail); setDetail(null) }}
        onUndeploy={() => { undeploy(detail); setDetail(null) }} />}
    </>
  )
}

function VCard({ v, busy, onDetail, onDeploy, onUndeploy }) {
  return (
    <div className="card">
      <div className="between mb">
        <div className="flex">
          <div style={{ fontSize: 28 }}>{v.emoji}</div>
          <div><h3 style={{ margin: 0, fontSize: 15 }}>{v.name}</h3>
            <div className="muted" style={{ fontSize: 11.5 }}>{v.for}</div></div>
        </div>
        <span className="tag" style={{ color: 'var(--green)' }}>{v.price}/mo</span>
      </div>
      <div style={{ fontSize: 12.5, fontWeight: 500, marginBottom: 8 }}>{v.tagline}</div>
      <ul style={{ paddingLeft: 16, fontSize: 12, lineHeight: 1.6, margin: '0 0 10px', minHeight: 92 }}>
        {v.included.slice(0, 4).map((i, k) => <li key={k}>{i}</li>)}
      </ul>
      <div className="flex wrap mb" style={{ gap: 4 }}>
        {v.compliance.map((c) => <span key={c} className="tag" style={{ fontSize: 10, color: 'var(--red)' }}>🔒 {c}</span>)}
        {v.integrations.slice(0, 2).map((i) => <span key={i} className="tag" style={{ fontSize: 10 }}>{i}</span>)}
      </div>
      <div className="between">
        <button className="btn ghost sm" onClick={onDetail}>Details</button>
        {v.deployed
          ? <div className="flex" style={{ gap: 6 }}>
              <span className="pill st-active" style={{ fontSize: 11 }}><span className="dot" /> deployed</span>
              <button className="btn ghost sm" disabled={busy} onClick={onUndeploy} title="Remove this vertical">
                {busy ? '…' : 'Undeploy'}</button>
            </div>
          : <button className="btn sm" disabled={busy} onClick={onDeploy}>
              <Icon name="zap" size={13} /> {busy ? 'Setting up…' : 'Deploy'}</button>}
      </div>
    </div>
  )
}

function DetailModal({ v, busy, onClose, onDeploy, onUndeploy }) {
  return (
    <Modal title={`${v.emoji} ${v.name}`} onClose={onClose}>
      <div className="flex wrap mb">
        <span className="tag" style={{ color: 'var(--green)' }}>{v.price}/mo</span>
        <span className="tag">{v.for}</span>
        <span className="tag" style={{ color: 'var(--primary)' }}>{v.industry}</span>
        <span className="tag">{v.category}</span>
      </div>
      <p style={{ fontSize: 14 }}>{v.tagline}</p>
      <h4>What's included (out of the box)</h4>
      <div>{v.included.map((i, k) => (
        <div key={k} className="flex" style={{ fontSize: 13, padding: '3px 0' }}>
          <Icon name="check" size={14} style={{ color: 'var(--green)' }} />{i}</div>))}</div>
      <h4>Compliance</h4>
      <div className="flex wrap">{v.compliance.length ? v.compliance.map((c) => <span key={c} className="tag" style={{ color: 'var(--red)' }}>🔒 {c}</span>) : <span className="muted" style={{ fontSize: 13 }}>General universal rules apply.</span>}</div>
      <h4>Integrations</h4>
      <div className="flex wrap">{v.integrations.map((i) => <span key={i} className="tag">{i}</span>)}</div>
      <div className="muted mt mb" style={{ fontSize: 12 }}>{v.deployed
        ? 'Deployed. Undeploy removes its roster, pipelines, concierge and automations, and reverts your screens.'
        : `Deploying sets up the full roster, turns on the automations, creates a ${v.name} concierge, and re-skins your screens to this vertical.`}</div>
      {v.deployed
        ? <button className="btn ghost" style={{ width: '100%' }} disabled={busy} onClick={onUndeploy}>
            <Icon name="x" size={15} /> {busy ? 'Removing…' : `Undeploy ${v.name}`}</button>
        : <button className="btn" style={{ width: '100%' }} disabled={busy} onClick={onDeploy}>
            <Icon name="zap" size={15} /> {busy ? 'Setting up…' : `Deploy ${v.name}`}</button>}
    </Modal>
  )
}
