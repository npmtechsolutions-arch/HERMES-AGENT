import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

const TYPE_LABEL = {
  industry_template: 'Industry', agent_pack: 'Agent Pack', skill: 'Skill',
  workflow: 'Workflow', integration: 'Integration',
}

export default function Marketplace() {
  const nav = useNavigate()
  const [items, setItems] = useState(null)
  const [activeIndustry, setActiveIndustry] = useState(null)
  const [typeFilter, setTypeFilter] = useState('')
  const [freeOnly, setFreeOnly] = useState(false)
  const [q, setQ] = useState('')
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const [busy, setBusy] = useState(null)
  const recogRef = useRef(null)
  const itemsRef = useRef(null); itemsRef.current = items

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => api.get('/marketplace').then((d) => { setItems(d.items); itemsRef.current = d.items; setActiveIndustry(d.active_industry) }).catch(() => flash('err', 'Could not load the marketplace.'))
  useEffect(() => { load() }, [])

  const install = async (it, { confirmSwitch = true } = {}) => {
    if (it.status === 'in_review') { flash('err', `“${it.name}” is under security review — available once approved.`); return }
    // One industry at a time — confirm a switch from the currently-active industry.
    if (confirmSwitch && it.type === 'industry_template' && activeIndustry && it.industry !== activeIndustry) {
      if (!window.confirm(`You currently run ${activeIndustry}. Installing “${it.name}” will switch your whole company to ${it.industry} (one industry at a time). Continue?`)) return
    }
    setBusy(it.id)
    try {
      const r = await api.post(`/marketplace/${it.id}/install`); flash('ok', r.message); speak(r.message)
      if (r.reskinned) {
        // An industry template only sets the skin — the office still needs staffing &
        // workflows, so continue in Guided Setup where it picks up from here.
        window.dispatchEvent(new Event('hermus:skin-changed'))
        nav(`/guided-setup?from=marketplace&name=${encodeURIComponent(it.name)}`)
      } else { await load() }
    }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not install the pack.') }
    finally { setBusy(null) }
  }
  const uninstall = async (it) => {
    if (!window.confirm(it.type === 'industry_template'
      ? `Uninstall “${it.name}”? Your company will return to the universal core (no industry skin).`
      : `Uninstall “${it.name}”?`)) return
    setBusy(it.id)
    try { const r = await api.post(`/marketplace/${it.id}/uninstall`); flash('ok', r.message); speak(r.message); if (it.type === 'industry_template') window.dispatchEvent(new Event('hermus:skin-changed')); await load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not uninstall the pack.') }
    finally { setBusy(null) }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/marketplace/resolve', { transcript: phrase })
      const find = (id) => (itemsRef.current || []).find((x) => x.id === id)
      switch (r.action) {
        case 'install': { const it = find(r.id); if (it) await install(it) } break
        case 'uninstall': { const it = find(r.id); if (it) await uninstall(it) } break
        case 'filter': setTypeFilter(r.type || ''); setFreeOnly(!!r.free); setQ(''); flash('ok', r.message); break
        case 'search': setQ(r.query); flash('ok', r.message); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__marketplaceVoice = (t) => { runCommand(t); return true }; return () => { if (window.__marketplaceVoice) delete window.__marketplaceVoice } })

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
  const types = ['industry_template', ...new Set(items.map((i) => i.type))].filter((v, i, a) => a.indexOf(v) === i)
  const shown = items.filter((it) =>
    (!typeFilter || it.type === typeFilter) &&
    (!freeOnly || it.is_free) &&
    (!q || `${it.name} ${it.description} ${(it.industry_tags || []).join(' ')}`.toLowerCase().includes(q.toLowerCase())))
  const industryCount = items.filter((i) => i.type === 'industry_template').length

  return (
    <>
      <PageHead title="Marketplace" sub="Industry templates, agent packs, skills & integrations — signed packages. Install to your desktop.">
        <span className="muted" style={{ fontSize: 12 }}>{items.length} packs · {industryCount} industries</span>
      </PageHead>

      <div className="card mb" style={{ background: activeIndustry ? 'var(--success-bg)' : 'var(--panel-2)', border: activeIndustry ? '1px solid var(--success-border)' : '1px solid var(--border)', boxShadow: 'none' }}>
        <div className="flex" style={{ fontSize: 13 }}>
          <Icon name="building" size={16} style={{ color: activeIndustry ? 'var(--success-fg)' : 'var(--muted)' }} />
          {activeIndustry
            ? <span>Your company runs the <strong>{activeIndustry}</strong> industry pack. Installing a different industry switches your whole company — <strong>one industry at a time</strong>.</span>
            : <span>No industry installed — your company runs on the universal core. Install an industry pack below to skin everything to your business.</span>}
        </div>
      </div>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "install the healthcare pack", "uninstall it", "show industry templates", "search legal"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="card mb">
        <div className="flex wrap" style={{ gap: 8, alignItems: 'center' }}>
          <button className={'btn sm ' + (typeFilter === '' ? '' : 'ghost')} onClick={() => setTypeFilter('')}>All</button>
          {types.map((t) => (
            <button key={t} className={'btn sm ' + (typeFilter === t ? '' : 'ghost')} onClick={() => setTypeFilter(t)}>{TYPE_LABEL[t] || t}</button>
          ))}
          <label className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer', marginLeft: 8 }}>
            <input type="checkbox" checked={freeOnly} style={{ width: 15 }} onChange={(e) => setFreeOnly(e.target.checked)} /> Free only
          </label>
          <input style={{ marginLeft: 'auto', maxWidth: 220 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search packs…" />
        </div>
      </div>

      <div className="grid cols-3">
        {shown.map((it) => (
          <div className="card" key={it.id} style={it.installed ? { borderColor: 'var(--green)' } : {}}>
            <div className="between mb">
              <span className="tag">{TYPE_LABEL[it.type] || it.type.replace('_', ' ')}</span>
              <div className="flex" style={{ gap: 4 }}>
                {it.status === 'in_review' && <span className="tag" style={{ color: 'var(--amber)' }}>in review</span>}
                {it.is_free ? <span className="tag" style={{ color: 'var(--green)' }}>Free</span>
                  : <span className="tag">₹{it.price.toLocaleString()}</span>}
              </div>
            </div>
            <h3 style={{ margin: '4px 0' }}>{it.name} {it.installed && <span className="tag" style={{ color: 'var(--green)', fontSize: 11 }}>✓ active</span>}</h3>
            <p className="muted" style={{ fontSize: 13, minHeight: 56 }}>{it.description}</p>
            <div className="between">
              <span className="muted" style={{ fontSize: 12 }}>by {it.publisher} · {it.installs.toLocaleString()} installs</span>
            </div>
            {it.status === 'in_review'
              ? <button className="btn ghost sm mt" style={{ width: '100%' }} disabled title="Under security review">In review — available soon</button>
              : it.installed
                ? <button className="btn danger sm mt" style={{ width: '100%' }} disabled={busy === it.id} onClick={() => uninstall(it)}>
                    {busy === it.id ? 'Working…' : 'Uninstall'}</button>
                : <button className="btn sm mt" style={{ width: '100%' }} disabled={busy === it.id} onClick={() => install(it)}>
                    {busy === it.id ? 'Installing…' : (it.type === 'industry_template' && activeIndustry ? 'Switch to this' : 'Install to desktop')}</button>}
          </div>
        ))}
        {shown.length === 0 && <div className="empty" style={{ gridColumn: '1/-1' }}>No packs match this filter.</div>}
      </div>
    </>
  )
}
