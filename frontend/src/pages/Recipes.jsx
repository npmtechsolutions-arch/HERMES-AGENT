import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useMode } from '../mode'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

export default function Recipes() {
  const [data, setData] = useState(null)        // { categories, count, enabled_count, recipes }
  const [msg, setMsg] = useState(null)
  const [q, setQ] = useState('')
  const [cat, setCat] = useState('All')
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const mode = useMode()
  const nav = useNavigate()

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } }
  const load = () => api.get('/recipes?grouped=true').then(setData).catch(() => flash('err', 'Could not load recipes.'))
  useEffect(() => { load() }, [])

  const find = (rid) => (data?.recipes || []).find((r) => r.id === rid)
  const toggle = async (r, enabled, params) => {
    try { const x = await api.post(`/recipes/${r.id}/toggle`, { enabled, params: params ?? r.params }); flash('ok', x.message); await load(); return x }
    catch (e) { flash('err', e?.message || `Couldn't update ${r.name}.`) }
  }
  const setParam = async (r, k, v) => {
    try { const x = await api.post(`/recipes/${r.id}/toggle`, { enabled: r.enabled, params: { [k]: v } }); flash('ok', `“${r.name}” updated.`); await load() }
    catch (e) { flash('err', e?.message || 'Could not save.') }
  }
  const fork = async (r) => {
    try { const w = await api.post(`/recipes/${r.id}/open-as-workflow`); flash('ok', w.message); nav('/workflows') }
    catch (e) { flash('err', e?.message || 'Could not open as workflow.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/recipes/resolve', { transcript: phrase })
      const rc = r.rid ? find(r.rid) : null
      switch (r.action) {
        case 'enable': { const x = await toggle(rc, true); if (x) speak(x.message) } break
        case 'disable': { const x = await toggle(rc, false); if (x) speak(x.message) } break
        case 'set_param': { await api.post(`/recipes/${r.rid}/toggle`, { enabled: true, params: { [r.key]: r.value } }); flash('ok', r.message); speak(r.message); await load() } break
        case 'open_workflow': rc && await fork(rc); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__recipesVoice = (t) => { runCommand(t); return true }; return () => { if (window.__recipesVoice) delete window.__recipesVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!data) return <Loading />
  const ql = q.trim().toLowerCase()
  const matches = (r) => !ql || [r.name, r.desc, r.category, r.engine].some((s) => (s || '').toLowerCase().includes(ql))
  const visible = data.recipes.filter((r) => (cat === 'All' || r.category === cat) && matches(r))
  const cats = ['All', ...data.categories]

  return (
    <>
      <PageHead title="Recipes" sub={`${data.count} one-toggle automations — turn one on, tune a setting, or just say it. Every recipe obeys the universal rules.`} />

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "turn on the daily briefing", "answer leads within 3 minutes", "disable invoice chasing"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="flex mb" style={{ gap: 8 }}>
        <div className="searchbar" style={{ flex: 1, maxWidth: 340 }}>
          <Icon name="search" size={15} />
          <input style={{ border: 'none', background: 'transparent', outline: 'none', width: '100%' }}
            value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search recipes…" />
        </div>
        <span className="muted" style={{ fontSize: 12, alignSelf: 'center' }}>{visible.length} shown · {data.enabled_count} on</span>
      </div>
      <div className="flex wrap mb" style={{ gap: 5 }}>
        {cats.map((c) => (
          <button key={c} className="tag" style={{ cursor: 'pointer', ...(cat === c ? { background: 'var(--primary)', color: '#fff' } : {}) }}
            onClick={() => setCat(c)}>{c}</button>
        ))}
      </div>

      {(cat === 'All' ? data.categories : [cat]).map((c) => {
        const items = visible.filter((r) => r.category === c)
        if (!items.length) return null
        return (
          <div key={c} style={{ marginBottom: 16 }}>
            <div className="nav-group-label" style={{ marginBottom: 8 }}>{c} · {items.length}</div>
            <div className="grid cols-2">
              {items.map((r) => (
                <RecipeCard key={r.id} r={r} mode={mode} onToggle={toggle} onSetParam={setParam} onFork={fork} />
              ))}
            </div>
          </div>
        )
      })}

      {mode === 'simple' && <div className="card mt" style={{ background: 'var(--grad-soft)' }}>
        <div className="flex" style={{ fontSize: 13 }}><Icon name="sparkles" size={15} style={{ color: 'var(--primary)' }} />
          <span>Want to customize beyond these toggles? Switch to <strong>Advanced</strong> (top bar) to "Open as workflow" and edit the full automation.</span></div>
      </div>}
    </>
  )
}

function RecipeCard({ r, mode, onToggle, onSetParam, onFork }) {
  // local copy of params so typing doesn't fire an API call per keystroke (saves on blur)
  const [draft, setDraft] = useState(r.params)
  useEffect(() => { setDraft(r.params) }, [JSON.stringify(r.params)])
  const commit = (k) => { if (draft[k] !== r.params[k]) onSetParam(r, k, draft[k]) }

  return (
    <div className="card" style={r.enabled ? { borderColor: 'var(--green)' } : {}}>
      <div className="between mb">
        <div>
          <h3 style={{ margin: 0, fontSize: 15 }}>{r.name}</h3>
          <div className="muted" style={{ fontSize: 12.5 }}>{r.desc}</div>
        </div>
        <label className="flex" style={{ cursor: 'pointer' }} title={r.enabled ? 'On' : 'Off'}>
          <input type="checkbox" checked={r.enabled} style={{ width: 18, height: 18 }} onChange={() => onToggle(r, !r.enabled)} />
        </label>
      </div>
      {Object.keys(r.params).length > 0 && (
        <div className="flex wrap mb" style={{ gap: 8 }}>
          {Object.entries(draft).map(([k, v]) => (
            <div key={k} className="flex" style={{ gap: 6, fontSize: 12 }}>
              <span className="muted">{k}:</span>
              {typeof v === 'number'
                ? <input type="number" value={v} style={{ width: 70, padding: '3px 6px' }} disabled={!r.enabled}
                    onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })}
                    onBlur={() => commit(k)} onKeyDown={(e) => { if (e.key === 'Enter') commit(k) }} />
                : <input value={v} style={{ width: 220, padding: '3px 6px' }} disabled={!r.enabled}
                    onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                    onBlur={() => commit(k)} onKeyDown={(e) => { if (e.key === 'Enter') commit(k) }} />}
            </div>
          ))}
        </div>
      )}
      <div className="between">
        <div className="flex wrap" style={{ gap: 4 }}>
          <span className="tag" style={{ color: 'var(--primary)' }}>{r.engine}</span>
          {mode === 'advanced' && r.rules.map((u) => <span key={u} className="tag" style={{ fontSize: 10 }}>{u}</span>)}
        </div>
        {mode === 'advanced' && <button className="btn ghost sm" onClick={() => onFork(r)}>
          <Icon name="workflow" size={13} /> Open as workflow</button>}
      </div>
    </div>
  )
}
