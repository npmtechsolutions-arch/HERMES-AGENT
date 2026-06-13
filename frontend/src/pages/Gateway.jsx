import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead, Pill } from '../components/ui'

const TIER_COLOR = { local: 'var(--green)', managed: 'var(--amber)' }
const Mini = ({ label, v }) => (
  <div className="stat" style={{ padding: 10, display: 'block' }}>
    <div className="label">{label}</div><div className="value" style={{ fontSize: 18 }}>{v}</div></div>
)

export default function Gateway() {
  const [g, setG] = useState(null)
  const [budget, setBudget] = useState(null)
  const [usage, setUsage] = useState(null)
  const [routing, setRouting] = useState(null)
  const [capDraft, setCapDraft] = useState('')
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const gRef = useRef(null); gRef.current = g

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([api.get('/gateway'), api.get('/budget'),
    api.get('/gateway/usage'), api.get('/routing')])
    .then(([gg, b, u, r]) => { setG(gg); setBudget(b); setUsage(u); setRouting(r); setCapDraft(String(b.limit)) })
    .catch(() => flash('err', 'Could not load the gateway.'))
  useEffect(() => { load() }, [])

  const setTier = async (agent, tier) => {
    if (agent.model_tier === tier) return
    try { const r = await api.post(`/gateway/agents/${agent.id}/tier`, { tier }); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not change the tier.') }
  }
  const setAll = async (tier) => {
    if (!window.confirm(`Move ALL agents to ${tier === 'local' ? 'Local (private, offline)' : 'Managed Gateway (metered)'}?`)) return
    try { const r = await api.post('/gateway/agents/tier-all', { tier }); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not change tiers.') }
  }
  const saveCap = async () => {
    const v = parseFloat(capDraft)
    if (isNaN(v) || v < 0) { flash('err', 'Enter a valid amount.'); return }
    try { const r = await api.patch('/budget', { limit: v }); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not set the cap.') }
  }
  const simulate = async () => {
    const a = gRef.current?.agents[0]
    try { const r = await api.post('/gateway/simulate', { agent_id: a?.id, task_profile: 'drafting' })
      flash(r.allowed ? 'ok' : 'err', r.message || (r.allowed ? 'Managed call settled.' : 'Call blocked.')); speak(r.message || ''); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Simulation failed.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/gateway/resolve', { transcript: phrase })
      const find = (id) => (gRef.current?.agents || []).find((a) => a.id === id)
      switch (r.action) {
        case 'tier': { const a = find(r.id); if (a) await setTier(a, r.tier) } break
        case 'tier_all': await setAll(r.tier); break
        case 'simulate': await simulate(); break
        case 'budget': setCapDraft(String(r.limit)); { try { const x = await api.patch('/budget', { limit: r.limit }); flash('ok', x.message); speak(x.message); load() } catch (e) { flash('err', e?.message || 'Could not set the cap.') } } break
        case 'usage': document.getElementById('gw-usage')?.scrollIntoView({ behavior: 'smooth' }); flash('ok', r.message); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__gatewayVoice = (t) => { runCommand(t); return true }; return () => { if (window.__gatewayVoice) delete window.__gatewayVoice } })

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
  return (
    <>
      <PageHead title="Model Gateway"
        sub="Per-agent model tier — privacy-labeled. Our local LLM by default; our managed cloud is opt-in and clearly marked.">
        <div className="flex" style={{ gap: 8 }}>
          <button className="btn green sm" onClick={() => setAll('local')}><Icon name="shield" size={14} /> All Local</button>
          <button className="btn secondary sm" onClick={() => setAll('managed')}>All Managed</button>
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "put the sales agent on local", "move everyone to local", "simulate a managed call", "set the budget to 5000"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="grid cols-2 mb">
        {g.tiers.map((t) => (
          <div className="card" key={t.id} style={{ borderTop: `3px solid ${TIER_COLOR[t.id]}` }}>
            <div className="between mb">
              <h3 style={{ margin: 0 }}>{t.label}</h3>
              <span className="pill" style={{ color: TIER_COLOR[t.id] }}>
                <span className="dot" />{t.id === 'local' ? 'private' : 'leaves machine · our key'}</span>
            </div>
            <div className="muted" style={{ fontSize: 13, minHeight: 40 }}>{t.desc}</div>
            <div className="tag mt">{g.distribution[t.id] || 0} agent(s)</div>
          </div>
        ))}
      </div>

      <div className="card mb" style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)' }}>
        <div className="flex"><Icon name="shield" size={18} style={{ color: 'var(--success-fg)' }} />
          <strong style={{ color: 'var(--success-fg)' }}>Hardened privacy rule ({g.pii_rule.id})</strong></div>
        <div style={{ fontSize: 13.5, marginTop: 6 }}>{g.pii_rule.text}</div>
        <div className="muted mt" style={{ fontSize: 12 }}>{g.pii_rule.protected_items} memory item(s) currently protected.</div>
      </div>

      {budget && (
        <div className="grid cols-2 mb">
          <div className="card">
            <div className="between mb"><h3 style={{ margin: 0 }}><Icon name="card" size={17} /> Pre-dispatch budget gate</h3>
              <Pill status={budget.state === 'ok' ? 'active' : budget.state === 'warn' ? 'waiting' : 'error'} /></div>
            <p className="muted" style={{ fontSize: 12.5 }}>Cost is reserved <strong>before</strong> every managed-gateway
              call (never after). {budget.period}: ₹{budget.spent} of ₹{budget.limit} ({budget.pct}%).</p>
            <div className="bar mb"><span style={{ width: `${Math.min(100, budget.pct)}%`,
              background: budget.pct >= 100 ? 'var(--red)' : budget.pct >= 80 ? 'var(--amber)' : undefined }} /></div>
            <div className="muted" style={{ fontSize: 11.5 }}>80% → warn · 100% → per-call human approval · hard cap → local-model fallback</div>
            <div className="flex mt" style={{ gap: 6, alignItems: 'center' }}>
              <span className="muted" style={{ fontSize: 12 }}>Monthly cap ₹</span>
              <input type="number" value={capDraft} onChange={(e) => setCapDraft(e.target.value)} style={{ width: 100 }} />
              <button className="btn sm" onClick={saveCap} disabled={capDraft === String(budget.limit)}>Set cap</button>
              <button className="btn secondary sm" onClick={simulate}><Icon name="zap" size={14} /> Simulate</button>
            </div>
          </div>
          <div className="card" id="gw-usage">
            <h3><Icon name="chart" size={17} /> Gateway usage (content-free)</h3>
            <div className="grid cols-3" style={{ gap: 8 }}>
              <Mini label="Calls" v={usage.calls} /><Mini label="Spend" v={`₹${usage.spend}`} />
              <Mini label="Avg latency" v={`${usage.avg_latency_ms}ms`} />
            </div>
            {usage.recent.slice(0, 4).map((r, i) => (
              <div key={i} className="between" style={{ fontSize: 12, padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                <span>{r.model} · {r.profile}</span>
                <span className="muted">{r.tokens} tok · ₹{r.cost} · {r.policy}</span>
              </div>
            ))}
            {usage.recent.length === 0 && <div className="muted mt" style={{ fontSize: 12 }}>No managed calls yet — everything ran locally.</div>}
          </div>
        </div>
      )}

      {routing && (
        <div className="card mb">
          <h3><Icon name="workflow" size={17} /> Per-tenant routing & failover ({routing.source})</h3>
          {routing.policies.map((pl) => (
            <div key={pl.task_profile} className="flex" style={{ padding: '7px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
              <span className="tag" style={{ minWidth: 90 }}>{pl.task_profile}</span>
              {pl.chain.map((c, i) => (
                <span key={i} className="flex" style={{ gap: 4 }}>
                  <span className="tag" style={{ color: c.tier === 'local' ? 'var(--green)' : 'var(--amber)' }}>{c.model}</span>
                  {i < pl.chain.length - 1 && <span className="muted">→</span>}
                </span>
              ))}
            </div>
          ))}
          {routing.note && <div className="muted mt" style={{ fontSize: 12 }}>{routing.note}</div>}
        </div>
      )}

      <div className="card">
        <h3><Icon name="users" size={17} /> Agents & their model tier</h3>
        {g.agents.length === 0 && <div className="muted">No agents yet. Hire agents or build your AI org first.</div>}
        {g.agents.map((a) => (
          <div key={a.id} className="between" style={{ padding: '11px 0', borderBottom: '1px solid var(--border)' }}>
            <div><div style={{ fontWeight: 600, fontSize: 14 }}>{a.name}</div>
              <div className="muted" style={{ fontSize: 12 }}>{a.designation} · {a.model_id}</div></div>
            <div className="flex">
              {g.tiers.map((t) => (
                <button key={t.id} className={'btn sm ' + (a.model_tier === t.id ? '' : 'ghost')}
                  onClick={() => setTier(a, t.id)}
                  style={a.model_tier === t.id ? { background: TIER_COLOR[t.id], borderColor: 'transparent', color: '#fff' } : {}}>
                  {t.label}</button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
