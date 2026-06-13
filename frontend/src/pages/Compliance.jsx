import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

const EFFECT = { deny: 'var(--red)', require_approval: 'var(--amber)', redact: 'var(--blue)', allow: 'var(--green)' }

export default function Compliance() {
  const [params] = useSearchParams()
  const [tab, setTab] = useState(['policies', 'isolation'].includes(params.get('tab')) ? params.get('tab') : 'identity')
  // shared data
  const [model, setModel] = useState(null)
  const [chain, setChain] = useState([])
  const [anchors, setAnchors] = useState([])
  const [verify, setVerify] = useState(null)
  const [packs, setPacks] = useState([])
  const [ctx, setCtx] = useState({ cross_border: false, pii: false, medical_advice: false, ad_publish: false })
  const [result, setResult] = useState(null)
  const [leases, setLeases] = useState([])
  const [ceilings, setCeilings] = useState([])
  const [last, setLast] = useState(null)
  const [pattern, setPattern] = useState('')
  // voice / flash
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const ceilRef = useRef(null); ceilRef.current = ceilings

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([
    api.get('/identity/model'), api.get('/audit/chain'), api.get('/audit/anchors'),
    api.get('/policies'), api.get('/sandbox/leases'), api.get('/tenant/ceilings'),
  ]).then(([m, c, a, pk, l, ce]) => { setModel(m); setChain(c); setAnchors(a); setPacks(pk); setLeases(l); setCeilings(ce) })
    .catch(() => flash('err', 'Could not load compliance data.'))
  useEffect(() => { load() }, [])

  const doVerify = async () => {
    try { const r = await api.get('/audit/verify'); setVerify(r); flash(r.intact ? 'ok' : 'err', r.message); speak(r.message) }
    catch (e) { flash('err', e?.message || 'Verify failed.') }
  }
  const doAnchor = async () => {
    try { const r = await api.post('/audit/anchor'); flash('ok', r.message || 'Anchored.'); speak(r.message || ''); load() }
    catch (e) { flash('err', e?.message || 'Anchor failed.') }
  }
  const evaluate = async (context = ctx) => {
    try { const r = await api.post('/policies/evaluate', { scope: 'all', context }); setResult(r); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.message || 'Evaluate failed.') }
  }
  const lease = async () => {
    try { const r = await api.post('/sandbox/lease', { task_ref: 'demo-batch' }); setLast(r); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.message || 'Lease failed.') }
  }
  const addCeiling = async (pat = pattern, effect = 'deny') => {
    if (!pat.trim()) { flash('err', 'Enter a tool pattern.'); return }
    try { const r = await api.post('/tenant/ceilings', { tool_pattern: pat.trim(), effect }); flash('ok', r.message); speak(r.message); setPattern(''); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not add the ceiling.') }
  }
  const removeCeiling = async (c) => {
    try { const r = await api.del(`/tenant/ceilings/${c.id}`); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not remove the ceiling.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/compliance/resolve', { transcript: phrase })
      switch (r.action) {
        case 'tab': setTab(r.tab); flash('ok', r.message); break
        case 'verify': setTab('identity'); await doVerify(); break
        case 'anchor': setTab('identity'); await doAnchor(); break
        case 'lease': setTab('isolation'); await lease(); break
        case 'add_ceiling': setTab('isolation'); await addCeiling(r.pattern, r.effect); break
        case 'remove_ceiling': { const c = (ceilRef.current || []).find((x) => x.id === r.id); if (c) await removeCeiling(c) } break
        case 'evaluate': setTab('policies'); setCtx({ ...ctx, ...r.context }); await evaluate({ ...ctx, ...r.context }); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__complianceVoice = (t) => { runCommand(t); return true }; return () => { if (window.__complianceVoice) delete window.__complianceVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!model) return <Loading />
  return (
    <>
      <PageHead title="Compliance & Isolation"
        sub="Isolation by architecture. Governance by design. Compliance you can verify.">
        <div className="tabs" style={{ margin: 0, width: 460 }}>
          {[['identity', 'Identity & Audit'], ['policies', 'Policies'], ['isolation', 'Isolation']].map(([k, l]) => (
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
            placeholder={listening ? 'Listening…' : 'Say or type: "verify the audit chain", "anchor now", "lease a sandbox", "add a ceiling for payments.execute", "evaluate a cross-border PII scenario"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {tab === 'identity' && (
        <div className="grid" style={{ gridTemplateColumns: '380px 1fr', alignItems: 'start' }}>
          <div>
            <div className="card mb">
              <h3><Icon name="users" size={17} /> Five-layer identity</h3>
              <p className="muted" style={{ fontSize: 12.5 }}>Every action is attributed to a complete chain —
                not a single principal. A record is invalid unless all five layers are present (fail-closed).</p>
              {model.layers.map((l) => (
                <div key={l.id} className="flex" style={{ padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                  <span className="tag" style={{ minWidth: 28, justifyContent: 'center' }}>{l.id}</span>
                  <div><div style={{ fontSize: 13, fontWeight: 600 }}>{l.name}</div>
                    <div className="muted" style={{ fontSize: 11, fontFamily: 'monospace' }}>{l.example}</div></div>
                </div>
              ))}
            </div>
            <div className="card">
              <h3><Icon name="link" size={17} /> Audit anchors</h3>
              <p className="muted" style={{ fontSize: 12.5 }}>Content-free signed head-hashes — even a root-privileged
                attacker can't rewrite anchors already sent.</p>
              <button className="btn secondary sm mb" onClick={doAnchor}>Anchor now</button>
              {anchors.map((a, i) => (
                <div key={i} className="muted" style={{ fontSize: 11, fontFamily: 'monospace', padding: '3px 0' }}>
                  ⚓ {a.head_hash} → #{a.range_to_id}</div>
              ))}
              {anchors.length === 0 && <div className="muted" style={{ fontSize: 12 }}>No anchors yet.</div>}
            </div>
          </div>

          <div className="card">
            <div className="between mb">
              <h3 style={{ margin: 0 }}><Icon name="shield" size={17} /> Tamper-evident audit chain</h3>
              <button className="btn green" onClick={doVerify}><Icon name="check" size={15} /> Verify integrity</button>
            </div>
            {verify && (
              <div className="card mb" style={{ background: verify.intact ? 'var(--success-bg)' : 'var(--danger-bg)',
                border: `1px solid ${verify.intact ? 'var(--success-border)' : 'var(--danger-border)'}` }}>
                <strong style={{ color: verify.intact ? 'var(--success-fg)' : 'var(--danger-fg)' }}>
                  {verify.intact ? `✓ Chain intact — ${verify.count} records verified by SHA-256 hash chain`
                    : `✕ Tampering detected at record #${verify.first_break}`}</strong>
              </div>
            )}
            <table>
              <thead><tr><th>#</th><th>Action</th><th>Identity chain</th><th>Hash</th></tr></thead>
              <tbody>
                {chain.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td><strong>{r.action}</strong></td>
                    <td style={{ fontSize: 11, fontFamily: 'monospace' }}>
                      {r.identity_chain ? `${r.identity_chain.L1_tenant?.slice(0, 10)} · ${r.identity_chain.L2_human} · ${r.identity_chain.L3_agent}` : '—'}</td>
                    <td className="muted" style={{ fontSize: 11, fontFamily: 'monospace' }}>{r.this_hash}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'policies' && (
        <div className="grid" style={{ gridTemplateColumns: '1fr 360px', alignItems: 'start' }}>
          <div>
            <div className="flex mb"><Icon name="shield" size={16} /><strong>Compliance-as-Code policy packs</strong>
              <span className="muted" style={{ fontSize: 12 }}>— evaluated before every tool/gateway call; decisions are audited evidence</span></div>
            {packs.map((pk) => (
              <div className="card mb" key={pk.id}>
                <div className="between mb">
                  <h3 style={{ margin: 0 }}>{pk.name} <span className="muted" style={{ fontSize: 12 }}>v{pk.version}</span></h3>
                  <div className="flex">{pk.platform && <span className="tag">platform</span>}
                    {pk.locked && <span className="tag" style={{ color: 'var(--red)' }}>🔒 locked</span>}
                    <span className="tag">{pk.scope}</span></div>
                </div>
                {pk.rules.map((r) => (
                  <div key={r.policy_id} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                    <div className="flex" style={{ gap: 7 }}>
                      <span className="tag">{r.policy_id}</span>
                      <span className="tag" style={{ color: EFFECT[r.effect] }}>{r.effect}</span>
                      <strong style={{ fontSize: 12.5 }}>if {r.condition.if}</strong></div>
                    <div className="muted" style={{ fontSize: 12 }}>{r.evidence}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div className="card" style={{ position: 'sticky', top: 0 }}>
            <h3><Icon name="zap" size={17} /> Policy Decision Point</h3>
            <p className="muted" style={{ fontSize: 12.5 }}>Dry-run a scenario through the PDP (writes an audited decision).</p>
            {Object.keys(ctx).map((k) => (
              <label key={k} className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer', padding: '5px 0' }}>
                <input type="checkbox" checked={ctx[k]} style={{ width: 16 }}
                  onChange={(e) => setCtx({ ...ctx, [k]: e.target.checked })} /> {k}
              </label>
            ))}
            <button className="btn mt" style={{ width: '100%' }} onClick={() => evaluate()}>Evaluate</button>
            {result && (
              <div className="card mt" style={{ background: 'var(--panel-2)', boxShadow: 'none' }}>
                <div className="flex"><span className="tag" style={{ color: EFFECT[result.effect] }}>{result.effect}</span>
                  {result.policy_id && <span className="tag">{result.policy_id}</span>}</div>
                <div className="muted mt" style={{ fontSize: 12.5 }}>{result.evidence || 'No policy matched — allowed.'}</div>
                {result.pack && <div className="cite" style={{ fontSize: 11 }}>pack: {result.pack}</div>}
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'isolation' && (
        <>
          <div className="card mb" style={{ background: 'var(--grad)', color: '#fff', border: 'none' }}>
            <h3 style={{ color: '#fff', margin: 0 }}>Isolation by architecture, not by promise</h3>
            <p style={{ color: 'rgba(255,255,255,.9)', fontSize: 13.5 }}>Each tenant's agents execute on the tenant's
              own hardware (Z1) — cross-tenant data bleed is structurally impossible. Everything that must be shared
              (control plane, gateway, hosted runtime) is budget-gated, policy-checked, identity-chained and hash-anchored.</p>
          </div>

          <div className="grid cols-2 mb">
            <div className="card">
              <h3><Icon name="cpu" size={17} /> Tenant-aware execution sandbox (§4)</h3>
              <p className="muted" style={{ fontSize: 12.5 }}>“Golden snapshot, ephemeral overlay”: lease from a warm pool,
                run a batch, then <strong>recycle</strong> — destroy overlay + shred per-lease key + GPU VRAM scrub +
                restore the measured golden snapshot. Sanitization is subtractive & provable.</p>
              <button className="btn" onClick={lease}><Icon name="zap" size={15} /> Lease & recycle a sandbox</button>
              {last && (
                <div className="card mt" style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)' }}>
                  <div style={{ fontSize: 13 }}>✓ Recycled in <strong>{last.sanitize_ms} ms</strong> (target ≤ 250 ms)</div>
                  <div className="muted" style={{ fontSize: 11, fontFamily: 'monospace', marginTop: 4 }}>golden: {last.golden_hash}</div>
                  <div className="muted" style={{ fontSize: 11, fontFamily: 'monospace' }}>scrub: {last.scrub_proof}</div>
                </div>
              )}
              {leases.length > 0 && <div className="muted mt" style={{ fontSize: 11 }}>
                {leases.length} recent lease(s) · all recycled with scrub proof</div>}
            </div>

            <div className="card">
              <h3><Icon name="shield" size={17} /> Tool-policy ceilings (§P1)</h3>
              <p className="muted" style={{ fontSize: 12.5 }}>Hard limits agent grants can never exceed. Effective permission
                = agent_grant ∩ department_policy ∩ <strong>tenant_ceiling</strong> ∩ plan_flag.</p>
              <div className="flex mb">
                <input value={pattern} onChange={(e) => setPattern(e.target.value)} placeholder="e.g. payments.execute"
                  onKeyDown={(e) => { if (e.key === 'Enter') addCeiling() }} />
                <button className="btn" onClick={() => addCeiling()}>Add</button>
              </div>
              {ceilings.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No ceilings set.</div>}
              {ceilings.map((c) => (
                <div key={c.id} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontFamily: 'monospace', fontSize: 13 }}>{c.tool_pattern}</span>
                  <div className="flex"><span className="tag" style={{ color: EFFECT[c.effect] || 'var(--red)' }}>{c.effect}</span>
                    <button className="icon-btn" style={{ width: 28, height: 28 }}
                      onClick={() => removeCeiling(c)}><Icon name="x" size={13} /></button></div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid cols-3">
            {[['Namespace-isolated RAG (Z5)', 'RLS on memory + a mandatory retrieval middleware injects namespace filters; agent code cannot call the vector store directly. Agencies get per-client walls.'],
              ['Shadow-agent detection (Z5)', 'The Org Chart is a complete live inventory; unregistered nodes, sideloaded skills and third-party agent tools are detected → quarantine → approval chain.'],
              ['Confidential Gateway (roadmap)', 'CVM (AMD SEV-SNP) + confidential H100 GPUs with remote attestation — protects prompts/outputs in-use. Marketed as a roadmap commitment; attestation when real, never theater.']]
              .map(([t, d]) => (
              <div className="card" key={t}>
                <h3 style={{ fontSize: 14 }}>{t}</h3>
                <div className="muted" style={{ fontSize: 12.5 }}>{d}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  )
}
