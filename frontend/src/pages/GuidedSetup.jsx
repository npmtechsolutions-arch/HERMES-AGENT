import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

export default function GuidedSetup() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const [state, setState] = useState(null)
  const [industry, setIndustry] = useState('')
  const [goal, setGoal] = useState('')
  const [busy, setBusy] = useState(null)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const stateRef = useRef(null); stateRef.current = state

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 9000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const apply = (s) => { setState(s); stateRef.current = s; if (s.requirement?.industry) setIndustry(s.requirement.industry); if (s.requirement?.goal) setGoal(s.requirement.goal); window.dispatchEvent(new Event('hermus:skin-changed')) }
  const load = () => api.get('/setup/state').then(apply).catch(() => flash('err', 'Could not load setup.'))
  useEffect(() => {
    api.get('/setup/state').then((s) => {
      apply(s)
      // Arriving from a marketplace install or vertical deploy → orient the user on what's left.
      const from = params.get('from'); const name = params.get('name')
      const left = s.complete ? 'Just a couple of optional touches left.' : "Let's finish the remaining steps."
      if (from === 'marketplace')
        flash('ok', `${name ? `“${name}” installed` : 'Industry installed'} — that set your skin. ` +
          (s.steps.find((x) => x.key === 'staff')?.done ? left : "Next, let's staff your AI team so your office actually runs."))
      else if (from === 'vertical')
        flash('ok', `${name ? `“${name}” deployed` : 'Vertical deployed'} — your team, workflows and automations are live. ${left}`)
      else if (from === 'demo')
        flash('ok', `Demo workspace loaded — agents, pipelines and a chatbot are ready. ${left}`)
      else if (from === 'company')
        flash('ok', `Your AI org is adopted. ${left}`)
    }).catch(() => flash('err', 'Could not load setup.'))
  }, []) // eslint-disable-line

  const saveRequirement = async () => {
    if (!industry) { flash('err', 'Pick your industry first.'); return }
    setBusy('req')
    try { const r = await api.post('/setup/requirement', { industry, goal }); apply(r); flash('ok', r.message); speak(r.message) }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not save.') }
    finally { setBusy(null) }
  }
  const doStep = async (key) => {
    const step = state.steps.find((s) => s.key === key)
    if (step && !step.auto) { nav(step.route); return }
    setBusy(key)
    try { const r = await api.post(`/setup/do/${key}`, { industry, goal }); apply(r); flash('ok', r.message); speak(r.message); if (r.navigate) nav(r.navigate) }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'That step failed.') }
    finally { setBusy(null) }
  }
  const skipStep = async (key) => {
    try { const r = await api.post(`/setup/skip/${key}`); apply(r); flash('ok', r.message) }
    catch (e) { flash('err', e?.message || 'Could not skip.') }
  }
  const resetAll = async () => { if (!window.confirm('Reset guided setup?')) return; try { const r = await api.post('/setup/reset'); apply(r); flash('ok', r.message) } catch (e) { flash('err', 'Could not reset.') } }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/setup/resolve', { transcript: phrase })
      switch (r.action) {
        case 'requirement': if (r.industry) { setIndustry(r.industry); const x = await api.post('/setup/requirement', { industry: r.industry }); apply(x); flash('ok', x.message); speak(x.message) } break
        case 'do': await doStep(r.key); break
        case 'skip': await skipStep(r.key); break
        case 'next': { const nk = stateRef.current?.next_key; if (nk) await doStep(nk); else flash('ok', "You're all set!") } break
        case 'dismiss': { const x = await api.post('/setup/dismiss'); apply(x); flash('ok', x.message) } break
        case 'reset': await resetAll(); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__setupVoice = (t) => { runCommand(t); return true }; return () => { if (window.__setupVoice) delete window.__setupVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!state) return <Loading />
  const pct = state.progress.pct
  return (
    <>
      <PageHead title="Guided Setup" sub="We'll set up your AI office step by step — tell us your business, and we'll do the heavy lifting.">
        <button className="btn ghost sm" onClick={resetAll}>Reset</button>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "set up my company for healthcare", "staff my team", "what\'s next"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="card mb">
        <div className="between mb"><strong>{state.complete ? "🎉 You're all set up!" : `Setup progress — ${pct}%`}</strong>
          <span className="muted" style={{ fontSize: 12 }}>{state.progress.done}/{state.progress.total} core steps · {state.counts.agents} agents · {state.counts.workflows} workflows</span></div>
        <div className="bar"><span style={{ width: `${pct}%`, background: state.complete ? 'var(--green)' : undefined }} /></div>
        {state.complete && <div className="row-actions mt"><button className="btn green sm" onClick={() => nav('/')}>Go to dashboard</button></div>}
      </div>

      {!state.requirement.industry && (
        <div className="card mb" style={{ borderTop: '3px solid var(--primary)' }}>
          <h3 style={{ marginTop: 0 }}><Icon name="rocket" size={17} /> First, tell us about your business</h3>
          <p className="muted" style={{ fontSize: 13 }}>Your industry tailors everything — the agents we hire, the workflows we build, even the words the product uses.</p>
          <div className="grid cols-2" style={{ gap: 12 }}>
            <div className="field"><label>Your industry</label>
              <select value={industry} onChange={(e) => setIndustry(e.target.value)}>
                <option value="">Choose…</option>
                {state.industries.map((i) => <option key={i} value={i}>{i}</option>)}</select></div>
            <div className="field"><label>Main goal (optional)</label>
              <input value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="e.g. answer leads faster, automate billing" /></div>
          </div>
          <button className="btn" onClick={saveRequirement} disabled={!industry || busy === 'req'}>{busy === 'req' ? 'Saving…' : 'Start my setup'}</button>
        </div>
      )}

      <div className="grid" style={{ gap: 12 }}>
        {state.steps.map((s, i) => {
          const active = !s.done && !s.skipped && state.next_key === s.key
          return (
            <div className="card" key={s.key} style={{
              borderColor: s.done ? 'var(--green)' : active ? 'var(--primary)' : 'var(--border)',
              opacity: s.skipped ? 0.65 : 1 }}>
              <div className="flex" style={{ gap: 12, alignItems: 'flex-start' }}>
                <div className="ix" style={{ width: 32, height: 32, borderRadius: 9, flexShrink: 0,
                  background: s.done ? 'var(--green)' : active ? 'var(--grad)' : 'var(--panel-2)',
                  color: s.done || active ? '#fff' : 'var(--muted)', display: 'grid', placeItems: 'center', fontWeight: 700 }}>
                  {s.done ? <Icon name="check" size={16} /> : i + 1}</div>
                <div style={{ flex: 1 }}>
                  <div className="between">
                    <h3 style={{ margin: 0, fontSize: 15 }}>{s.title}
                      {!s.required && <span className="tag" style={{ marginLeft: 6, fontSize: 10 }}>optional</span>}
                      {s.skipped && <span className="tag" style={{ marginLeft: 6, fontSize: 10, color: 'var(--amber)' }}>skipped</span>}</h3>
                    {s.done && <span className="tag" style={{ color: 'var(--green)' }}>✓ done</span>}
                  </div>
                  <p className="muted" style={{ fontSize: 12.5, margin: '6px 0' }}>{s.why}</p>
                  {!s.done && <div className="row-actions">
                    <button className="btn sm" disabled={busy === s.key} onClick={() => doStep(s.key)}>
                      {busy === s.key ? 'Working…' : (s.auto ? `✨ ${s.cta} for me` : s.cta)}</button>
                    {s.auto && <button className="btn ghost sm" onClick={() => nav(s.route)}>Take me there</button>}
                    {!s.skipped && <button className="btn ghost sm" onClick={() => skipStep(s.key)}>Skip</button>}
                  </div>}
                  {s.done && <button className="btn ghost sm" onClick={() => nav(s.route)}>Review</button>}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}
