import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead, Stat } from '../components/ui'

export default function Universal() {
  const [params] = useSearchParams()
  const [tab, setTab] = useState(['rules', 'model', 'score'].includes(params.get('tab')) ? params.get('tab') : 'core')
  const [msg, setMsg] = useState(null)            // { kind, text }
  const [refresh, setRefresh] = useState(0)
  const [listening, setListening] = useState(false)
  const [cmd, setCmd] = useState('')
  const recogRef = useRef(null)
  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const bump = () => setRefresh((r) => r + 1)

  // ── one voice/command handler for the whole page ───────────────────────────
  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    try {
      const r = await api.post('/universal/resolve', { transcript: phrase })
      switch (r.action) {
        case 'deploy_engine':
          if (r.deployed) { flash('err', `${r.name} engine is already deployed.`); break }
          { const x = await api.post(`/universal/engines/${r.eid}/deploy`); flash('ok', x.message); setTab('core'); bump() } break
        case 'undeploy_engine':
          if (r.deployed === false) { flash('err', `${r.name} engine isn't deployed.`); break }
          { const x = await api.post(`/universal/engines/${r.eid}/undeploy`); flash('ok', x.message); setTab('core'); bump() } break
        case 'open_engine': setTab('core'); flash('ok', `Showing ${r.name}.`); break
        case 'deploy_roster': { const x = await api.post('/universal/deploy'); flash('ok', x.message); setTab('core'); bump() } break
        case 'undeploy_roster':
          try { const x = await api.post('/universal/undeploy'); flash('ok', x.message); setTab('core'); bump() }
          catch (e) { flash('err', e?.message || 'Roster not deployed.') } break
        case 'reskin': { const x = await api.post('/universal/reskin/apply', { industry: r.industry }); flash('ok', x.message); window.dispatchEvent(new Event('hermus:skin-changed')); setTab('core'); bump() } break
        case 'toggle_rule':
          try { const x = await api.patch(`/universal/rules/${r.rule_id}`, { enabled: r.enabled }); flash('ok', x.message); setTab('rules'); bump() }
          catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not change that rule.') } break
        default: flash('err', r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.message || 'Could not run that command.') }
    setCmd('')
  }
  useEffect(() => { window.__universalVoice = (t) => { runCommand(t); return true }; return () => { if (window.__universalVoice) delete window.__universalVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  return (
    <>
      <PageHead title="Universal Core"
        sub="Build once at 100% quality — every industry inherits. Switch engines on or off; verticals add only words, templates & thresholds.">
        <div className="tabs" style={{ margin: 0, width: 520 }}>
          {[['core', 'Engines & Roster'], ['rules', '12 Rules'], ['model', 'Model & Grammar'], ['score', 'Scoreboard']].map(([k, l]) => (
            <button key={k} className={tab === k ? 'active' : ''} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "deploy the appointment engine", "undeploy the roster", "re-skin to healthcare", "turn off rule U5"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}>
            <Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {tab === 'core' && <Core refresh={refresh} onFlash={flash} />}
      {tab === 'rules' && <Rules refresh={refresh} onFlash={flash} />}
      {tab === 'model' && <ModelGrammar />}
      {tab === 'score' && <Scoreboard />}
    </>
  )
}

const STATUS = { live: ['var(--green)', 'live'], partial: ['var(--amber)', 'partial'], roadmap: ['var(--muted)', 'roadmap'] }

function Core({ refresh, onFlash }) {
  const [engines, setEngines] = useState(null)
  const [agents, setAgents] = useState([])
  const [industry, setIndustry] = useState('Healthcare')
  const [industries, setIndustries] = useState([])
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(null)

  const load = () => Promise.all([api.get('/universal/engines'), api.get('/universal/agents'),
    api.get('/company/industries')]).then(([e, a, i]) => { setEngines(e); setAgents(a); setIndustries(i.industries) })
    .catch(() => onFlash('err', "Couldn't load the universal core."))
  useEffect(() => { load() }, [refresh])
  useEffect(() => { if (industry) api.get(`/universal/reskin?industry=${encodeURIComponent(industry)}`).then(setPreview) }, [industry])
  if (!engines) return <Loading />

  const deployedEngines = engines.filter((e) => e.deployed).length

  const deployEngine = async (e) => {
    if (busy) return; setBusy(e.id)
    try { const r = await api.post(`/universal/engines/${e.id}/deploy`); onFlash('ok', r.message); await load(); window.dispatchEvent(new Event('hermus:skin-changed')) }
    catch (err) { onFlash('err', err?.message || `Couldn't deploy ${e.name}.`) } finally { setBusy(null) }
  }
  const undeployEngine = async (e) => {
    if (busy) return; setBusy(e.id)
    try { const r = await api.post(`/universal/engines/${e.id}/undeploy`); onFlash('ok', r.message); await load() }
    catch (err) { onFlash('err', err?.message || `Couldn't undeploy ${e.name}.`) } finally { setBusy(null) }
  }
  const deployRoster = async () => {
    if (busy) return; setBusy('roster')
    try { const r = await api.post('/universal/deploy'); onFlash('ok', r.message); await load() }
    catch (err) { onFlash('err', err?.message || 'Could not deploy roster.') } finally { setBusy(null) }
  }
  const undeployRoster = async () => {
    if (busy) return; setBusy('roster')
    try { const r = await api.post('/universal/undeploy'); onFlash('ok', r.message); await load() }
    catch (err) { onFlash('err', err?.detail?.message || err?.message || 'Roster not deployed.') } finally { setBusy(null) }
  }
  const applyReskin = async () => {
    try { const r = await api.post('/universal/reskin/apply', { industry }); onFlash('ok', r.message); window.dispatchEvent(new Event('hermus:skin-changed')); await load() }
    catch (err) { onFlash('err', err?.message || 'Could not re-skin.') }
  }

  return (
    <>
      <div className="between mb">
        <div className="flex"><Icon name="zap" size={16} /><strong>The 8 universal engines</strong>
          <span className="muted" style={{ fontSize: 12 }}>— switch on the ones you want; everything decomposes into these</span></div>
        <span className="muted" style={{ fontSize: 12 }}>{deployedEngines}/8 deployed</span>
      </div>
      <div className="grid cols-4 mb">
        {engines.map((e) => (
          <div className="card" key={e.id} style={e.deployed ? { borderColor: 'var(--green)' } : {}}>
            <div className="between mb"><span className="tag">{e.id}</span>
              <span className="tag" style={{ color: STATUS[e.status][0] }}>● {STATUS[e.status][1]}</span></div>
            <h3 style={{ fontSize: 14, margin: 0 }}>{e.name}</h3>
            <div className="muted" style={{ fontSize: 12, margin: '4px 0' }}>{e.what}</div>
            <div className="cite" style={{ fontSize: 11 }}>{e.example}</div>
            {e.recipes?.length > 0 && <div className="flex wrap mt" style={{ gap: 3 }}>
              {e.recipes.map((r) => <span key={r} className="tag" style={{ fontSize: 9 }}>{r}</span>)}</div>}
            <div className="mt">
              {e.deployed
                ? <div className="flex between">
                    <span className="pill st-active" style={{ fontSize: 10 }}><span className="dot" /> on</span>
                    <button className="btn ghost sm" disabled={busy === e.id} onClick={() => undeployEngine(e)}>
                      {busy === e.id ? '…' : 'Undeploy'}</button></div>
                : <button className="btn sm" style={{ width: '100%' }} disabled={busy === e.id} onClick={() => deployEngine(e)}>
                    <Icon name="zap" size={12} /> {busy === e.id ? 'Deploying…' : 'Deploy engine'}</button>}
            </div>
          </div>
        ))}
      </div>

      <div className="grid" style={{ gridTemplateColumns: '1fr 360px', alignItems: 'start' }}>
        <div className="card">
          <div className="between mb"><h3 style={{ margin: 0 }}><Icon name="users" size={17} /> The 7 universal agents</h3>
            <div className="flex" style={{ gap: 6 }}>
              <button className="btn sm" disabled={busy === 'roster'} onClick={deployRoster}>
                <Icon name="zap" size={14} /> {busy === 'roster' ? '…' : 'Deploy roster'}</button>
              <button className="btn ghost sm" disabled={busy === 'roster'} onClick={undeployRoster}>Undeploy</button></div></div>
          {agents.map((a) => (
            <div key={a.role} className="between" style={{ padding: '9px 0', borderBottom: '1px solid var(--border)' }}>
              <div><div style={{ fontWeight: 600, fontSize: 13 }}>{a.universal_name}
                {a.vertical_name !== a.universal_name && <span className="muted"> → <span style={{ color: 'var(--primary)' }}>{a.vertical_name}</span></span>}</div>
                <div className="muted" style={{ fontSize: 12 }}>{a.job}</div></div>
              <div className="flex">{a.engines.map((e) => <span key={e} className="tag" style={{ fontSize: 10 }}>{e}</span>)}</div>
            </div>
          ))}
        </div>

        <div className="card" style={{ background: 'var(--grad-soft)' }}>
          <h3><Icon name="sparkles" size={17} /> Re-skin live</h3>
          <p className="muted" style={{ fontSize: 12.5 }}>The same roster & stages, re-labelled into any industry — the "watch, now it's a clinic" demo. Pure vocabulary; the engines don't change.</p>
          <div className="field"><label>Industry</label>
            <select value={industry} onChange={(e) => setIndustry(e.target.value)}>
              {industries.map((i) => <option key={i} value={i}>{i}</option>)}</select></div>
          {preview && <>
            <div className="card" style={{ background: 'var(--panel)', boxShadow: 'none', padding: 12 }}>
              {preview.roster.map((r) => (
                <div key={r.role} style={{ fontSize: 12.5, padding: '2px 0' }}>
                  <span className="muted">{r.from}</span> → <strong>{r.to}</strong></div>
              ))}
            </div>
            <div className="flex wrap mt" style={{ gap: 4 }}>{preview.stages.map((s, i) => (
              <span key={s} className="flex" style={{ gap: 0 }}><span className="tag" style={{ fontSize: 10 }}>{s}</span>
                {i < preview.stages.length - 1 && <span className="muted" style={{ margin: '0 3px' }}>→</span>}</span>))}</div>
          </>}
          <button className="btn mt" style={{ width: '100%' }} onClick={applyReskin}>Apply re-skin live</button>
        </div>
      </div>
    </>
  )
}

function Rules({ refresh, onFlash }) {
  const [rules, setRules] = useState(null)
  const [ctx, setCtx] = useState({ opt_out: false, first_contact: true, human_active: false, destructive: false, confidence: 1.0, amount: 0, hour: 14 })
  const [result, setResult] = useState(null)
  const load = () => api.get('/universal/rules').then(setRules)
  useEffect(() => { load() }, [refresh])
  if (!rules) return <Loading />

  const toggle = async (r) => {
    try { const x = await api.patch(`/universal/rules/${r.rule_id}`, { enabled: !r.enabled }); onFlash?.('ok', x.message); load() }
    catch (e) { onFlash?.('err', e.detail?.message || e.message) }
  }
  const evaluate = async () => setResult(await api.post('/universal/rules/evaluate', { message: ctx.amount ? `Pay ₹${ctx.amount}` : 'Following up', ...ctx }))
  const DEC = { block: 'var(--red)', human_only: 'var(--red)', hold: 'var(--amber)', require_approval: 'var(--amber)',
    escalate: 'var(--amber)', clarify: 'var(--blue)', defer: 'var(--blue)', queue: 'var(--muted)', audit: 'var(--muted)', allow: 'var(--green)' }

  return (
    <div className="grid" style={{ gridTemplateColumns: '1fr 360px', alignItems: 'start' }}>
      <div className="card">
        <h3><Icon name="shield" size={17} /> The 12 universal rules (every vertical keeps)</h3>
        {rules.map((r) => (
          <div key={r.rule_id} className="between" style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
            <div>
              <div className="flex" style={{ gap: 7 }}><span className="tag">{r.rule_id}</span>
                <strong style={{ fontSize: 13 }}>{r.title}</strong>
                {r.locked && <span className="tag" style={{ color: 'var(--red)' }}>🔒 locked</span>}
                {Object.keys(r.threshold).length > 0 && <span className="tag">{Object.entries(r.threshold).map(([k, v]) => `${k}:${v}`).join(' ')}</span>}</div>
              <div className="muted" style={{ fontSize: 12 }}>{r.why}</div>
            </div>
            <button className={'btn sm ' + (r.enabled ? 'green' : 'ghost')} onClick={() => toggle(r)} disabled={r.locked}>
              {r.enabled ? 'on' : 'off'}</button>
          </div>
        ))}
      </div>
      <div className="card" style={{ position: 'sticky', top: 0 }}>
        <h3><Icon name="zap" size={17} /> Cross-vertical decision point</h3>
        <p className="muted" style={{ fontSize: 12.5 }}>Run an action through all 12 rules — works identically in any vertical.</p>
        {[['first_contact', 'First contact (new party)'], ['opt_out', 'Recipient opted out'],
          ['human_active', 'Human active on thread'], ['destructive', 'Destructive op (delete/refund)']].map(([k, l]) => (
          <label key={k} className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer', padding: '4px 0' }}>
            <input type="checkbox" checked={ctx[k]} style={{ width: 16 }} onChange={(e) => setCtx({ ...ctx, [k]: e.target.checked })} /> {l}
          </label>
        ))}
        <div className="field mt"><label>Confidence ({ctx.confidence})</label>
          <input type="range" min="0" max="1" step="0.1" value={ctx.confidence} onChange={(e) => setCtx({ ...ctx, confidence: Number(e.target.value) })} /></div>
        <div className="field"><label>Amount (₹)</label><input type="number" value={ctx.amount} onChange={(e) => setCtx({ ...ctx, amount: Number(e.target.value) })} /></div>
        <div className="field"><label>Hour (0-23)</label><input type="number" min="0" max="23" value={ctx.hour} onChange={(e) => setCtx({ ...ctx, hour: Number(e.target.value) })} /></div>
        <button className="btn" style={{ width: '100%' }} onClick={evaluate}>Evaluate</button>
        {result && <div className="card mt" style={{ background: 'var(--panel-2)', boxShadow: 'none' }}>
          <div className="flex mb"><strong>Verdict:</strong><span className="tag" style={{ color: DEC[result.verdict] }}>{result.verdict}</span></div>
          {result.decisions.filter(d => d.applies).map((d) => (
            <div key={d.rule_id} className="between" style={{ fontSize: 12, padding: '3px 0' }}>
              <span>{d.rule_id} {d.title}</span><span className="tag" style={{ color: DEC[d.decision] }}>{d.decision}</span></div>
          ))}
        </div>}
      </div>
    </div>
  )
}

function ModelGrammar() {
  const [grammar, setGrammar] = useState(null)
  useEffect(() => { api.get('/universal/grammar').then(setGrammar) }, [])
  const ENTITIES = [['PARTY', 'person/org: customer, patient, client, vendor, partner'],
    ['ITEM', 'the thing transacted: property, treatment, service, case, product, course'],
    ['ENGAGEMENT', 'the relationship lifecycle: lead → … → closed (stages template-defined)'],
    ['EVENT', 'appointment, visit, hearing, call — anything with a time'],
    ['DOCUMENT', 'anything generated or received, with source citations'],
    ['MONEY', 'invoice, payment, due, commission — anything with an amount']]
  return (
    <div className="grid cols-2" style={{ alignItems: 'start' }}>
      <div className="card">
        <h3><Icon name="graph" size={17} /> Universal data model (6 entities)</h3>
        <p className="muted" style={{ fontSize: 12.5 }}>Templates add typed attributes, never new structure.
          Relations: <code>PARTY engages-in ENGAGEMENT about ITEM</code>; <code>ENGAGEMENT has EVENTs / DOCUMENTs / MONEY</code>.</p>
        {ENTITIES.map(([e, d]) => (
          <div key={e} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
            <span className="tag" style={{ fontFamily: 'monospace' }}>{e}</span>
            <span className="muted" style={{ fontSize: 12.5, marginLeft: 8 }}>{d}</span>
          </div>
        ))}
      </div>
      <div className="card">
        <h3><Icon name="mic" size={17} /> Universal voice grammar (20 commands)</h3>
        {!grammar ? <Loading /> : Object.entries(grammar).map(([group, cmds]) => (
          <div key={group} style={{ marginBottom: 12 }}>
            <div className="org-dept-label" style={{ marginBottom: 6 }}>{group}</div>
            <div className="flex wrap">{cmds.map((c) => <span key={c} className="tag">"{c}"</span>)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Scoreboard() {
  const [m, setM] = useState(null)
  useEffect(() => { api.get('/universal/metrics').then(setM) }, [])
  if (!m) return <Loading />
  return (
    <>
      <div className="flex mb"><Icon name="chart" size={16} /><strong>Owner scoreboard (the weekly value note)</strong></div>
      <div className="grid cols-4 mb">
        <Stat icon="users" label="Inquiries answered" value={m.owner.inquiries_answered} />
        <Stat icon="send" tint="blue" label="Follow-ups" value={m.owner.follow_ups} />
        <Stat icon="tasks" tint="green" label="Events booked" value={m.owner.events_booked} delta={`${m.owner.no_show_rate}% no-show`} />
        <Stat icon="clock" tint="amber" label="Staff-hours replaced" value={m.owner.staff_hours_replaced} delta={`${m.owner.after_hours_actions} after-hours`} />
      </div>
      <div className="flex mb"><Icon name="shield" size={16} /><strong>Health (internal)</strong></div>
      <div className="grid cols-3">
        {[['Validator-block rate', m.health.validator_block_rate, 'U4 catches before send'],
          ['Clarification rate', m.health.clarification_rate, 'U3 ask-don\'t-guess'],
          ['Human-takeover rate', m.health.human_takeover_rate, 'U2 no double-texting'],
          ['Opt-out rate', m.health.opt_out_rate, 'U7 sequence opt-outs'],
          ['Golden-task pass rate', m.health.golden_task_pass_rate ?? '—', 'GAP-2 release gate']].map(([t, v, d]) => (
          <div className="card" key={t}>
            <div className="label" style={{ fontSize: 12, color: 'var(--muted)' }}>{t}</div>
            <div className="value" style={{ fontSize: 24, fontWeight: 800 }}>{v}{typeof v === 'number' ? '%' : ''}</div>
            <div className="muted" style={{ fontSize: 11 }}>{d}</div>
          </div>
        ))}
      </div>
    </>
  )
}
