import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead, Pill } from '../components/ui'

export default function Company() {
  const [company, setCompany] = useState(null)
  const [industries, setIndustries] = useState([])
  const [focusAreas, setFocusAreas] = useState([])
  const [products, setProducts] = useState([])
  const [params] = useSearchParams()
  const [tab, setTab] = useState(params.get('tab') === 'suggest' ? 'suggest' : 'profile')
  const [msg, setMsg] = useState(null)              // { kind, text }
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const [suggestReq, setSuggestReq] = useState(null) // { industry, focus, ai, run }
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const load = () => Promise.all([
    api.get('/company'), api.get('/company/industries'), api.get('/products'), api.get('/company/focus-areas'),
  ]).then(([c, i, p, f]) => { setCompany(c); setIndustries(i.industries); setProducts(p); setFocusAreas(f.focus_areas) })
    .catch(() => flash('err', 'Could not load your company.'))
  useEffect(() => { load() }, [])

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    try {
      const r = await api.post('/company/resolve', { transcript: phrase })
      switch (r.action) {
        case 'rename_company': { const x = await api.patch('/company', { company_name: r.name }); flash('ok', x.message || 'Company renamed.'); await load() } break
        case 'set_industry': { const x = await api.patch('/company', { industry: r.industry }); flash('ok', x.message || `Industry set to ${r.industry}.`); window.dispatchEvent(new Event('hermus:skin-changed')); await load() } break
        case 'add_product': { await api.post('/products', { name: r.name }); flash('ok', `Added product “${r.name}”.`); await load() } break
        case 'delete_product': { const x = await api.del(`/products/${r.id}`); flash('ok', x.message || `Removed “${r.name}”.`); await load() } break
        case 'suggest': setTab('suggest'); setSuggestReq({ industry: r.industry || company.industry, focus: r.focus || '', ai: r.ai, run: Date.now() }); flash('ok', 'Building a suggested org…'); break
        case 'set_focus': setTab('suggest'); setSuggestReq({ focus: r.focus, run: Date.now() }); flash('ok', `Focus set to ${r.focus}.`); break
        case 'apply':
          if (window.__companyApply) { const m = await window.__companyApply(); flash('ok', m || 'Adopted into your org.') }
          else { setTab('suggest'); flash('err', 'Generate a suggestion first, then say "adopt the org".') } break
        default: flash('err', r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
    setCmd('')
  }
  useEffect(() => { window.__companyVoice = (t) => { runCommand(t); return true }; return () => { if (window.__companyVoice) delete window.__companyVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!company) return <Loading />

  return (
    <>
      <PageHead title="Your Company" sub="Set up your company, capture product ideas, and let AI staff your org — by click or by voice.">
        <div className="tabs" style={{ margin: 0, width: 380 }}>
          {[['profile', 'Profile & Products'], ['suggest', 'AI Org Builder']].map(([k, l]) => (
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
            placeholder={listening ? 'Listening…' : 'Say or type: "set industry to healthcare", "add a product called GST Filing", "build my org focused on sales", "adopt the org"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}>
            <Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {tab === 'profile'
        ? <Profile company={company} industries={industries} products={products} onChange={load} onFlash={flash} />
        : <Suggestions company={company} industries={industries} products={products} focusAreas={focusAreas}
            initialIndustry={params.get('industry')} suggestReq={suggestReq} onApplied={load} onFlash={flash} />}
    </>
  )
}

function Profile({ company, industries, products, onChange, onFlash }) {
  const [f, setF] = useState({ company_name: company.company_name, industry: company.industry,
    description: company.description || '' })
  const [saving, setSaving] = useState(false)
  const [edit, setEdit] = useState(null)        // product being edited, or {} for new
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  // keep the form in sync when the company changes elsewhere (e.g. via voice)
  useEffect(() => { setF({ company_name: company.company_name, industry: company.industry, description: company.description || '' }) },
    [company.company_name, company.industry, company.description])

  const save = async () => {
    setSaving(true)
    try { const r = await api.patch('/company', f); onFlash('ok', r.message || 'Company saved.'); window.dispatchEvent(new Event('hermus:skin-changed')); onChange() }
    catch (e) { onFlash('err', e?.message || 'Could not save the company.') }
    finally { setSaving(false) }
  }
  const removeProduct = async (pr) => {
    if (!window.confirm(`Delete “${pr.name}”? This can't be undone.`)) return
    try { const r = await api.del(`/products/${pr.id}`); onFlash('ok', r.message || `Removed “${pr.name}”.`); onChange() }
    catch (e) { onFlash('err', e?.message || 'Could not delete the product.') }
  }

  return (
    <div className="grid" style={{ gridTemplateColumns: '1fr 1fr' }}>
      <div className="card">
        <h3><Icon name="building" size={17} /> Company profile</h3>
        <div className="field"><label>Company name</label>
          <input value={f.company_name} onChange={set('company_name')} /></div>
        <div className="field"><label>Industry</label>
          <select value={f.industry || ''} onChange={set('industry')}>
            <option value="">— none (generic) —</option>
            {industries.map((i) => <option key={i} value={i}>{i}</option>)}
          </select></div>
        <div className="field"><label>What does your company do?</label>
          <textarea rows={3} value={f.description} onChange={set('description')} /></div>
        <button className="btn" onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save company'}</button>
      </div>

      <div className="card">
        <div className="between mb">
          <h3 style={{ margin: 0 }}><Icon name="bag" size={17} /> Products & ideas</h3>
          <button className="btn sm" onClick={() => setEdit({})}><Icon name="plus" size={15} /> Add</button>
        </div>
        {products.length === 0 && <div className="muted" style={{ fontSize: 13 }}>
          No products yet. Add a product idea to build an AI crew around it.</div>}
        {products.map((pr) => (
          <div key={pr.id} className="between" style={{ padding: '11px 0', borderBottom: '1px solid var(--border)' }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{pr.name}</div>
              <div className="muted" style={{ fontSize: 12 }}>{pr.description}</div>
            </div>
            <div className="flex">
              <Pill status={pr.stage} />
              <button className="icon-btn" style={{ width: 30, height: 30 }} onClick={() => setEdit(pr)} title="Edit">
                <Icon name="settings" size={13} /></button>
              <button className="icon-btn" style={{ width: 30, height: 30 }} onClick={() => removeProduct(pr)} title="Delete">
                <Icon name="x" size={14} /></button>
            </div>
          </div>
        ))}
      </div>

      {edit && <ProductModal product={edit.id ? edit : null} onClose={() => setEdit(null)}
        onSaved={onChange} onFlash={onFlash} />}
    </div>
  )
}

function ProductModal({ product, onClose, onSaved, onFlash }) {
  const editing = !!product
  const [f, setF] = useState({ name: product?.name || '', description: product?.description || '', stage: product?.stage || 'idea' })
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try {
      if (editing) { await api.patch(`/products/${product.id}`, f); onFlash('ok', `Updated “${f.name}”.`) }
      else { await api.post('/products', f); onFlash('ok', `Added “${f.name}”.`) }
      onSaved(); onClose()
    } catch (e) { onFlash('err', e?.message || 'Could not save the product.') }
    finally { setBusy(false) }
  }
  return (
    <Modal title={editing ? 'Edit product' : 'Add a product / idea'} onClose={onClose}>
      <div className="field"><label>Name</label>
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })}
          placeholder="e.g. Monthly GST Filing Service" autoFocus /></div>
      <div className="field"><label>Description</label>
        <textarea rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></div>
      <div className="field"><label>Stage</label>
        <select value={f.stage} onChange={(e) => setF({ ...f, stage: e.target.value })}>
          <option value="idea">Idea</option><option value="building">Building</option>
          <option value="launched">Launched</option></select></div>
      <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={!f.name || busy}>
        {busy ? 'Saving…' : editing ? 'Save changes' : 'Add product'}</button>
    </Modal>
  )
}

function Suggestions({ company, industries, products, focusAreas, initialIndustry, suggestReq, onApplied, onFlash }) {
  const nav = useNavigate()
  const [industry, setIndustry] = useState(initialIndustry || company.industry || 'Small Business Owners')
  const [focus, setFocus] = useState('')
  const [sug, setSug] = useState(null)
  const [busy, setBusy] = useState(false)
  const [adopt, setAdopt] = useState({ agents: true, pipelines: true, tasks: true })

  const fetchSug = async (ai, opts = {}) => {
    const ind = opts.industry || industry
    const foc = opts.focus !== undefined ? opts.focus : focus
    setBusy(true); setSug(null)
    try {
      const q = new URLSearchParams({ industry: ind, ai: ai ? 'true' : 'false' })
      if (foc) q.set('product', foc)
      const s = await api.get('/suggestions?' + q)
      setSug(s)
      return s
    } catch (e) { onFlash('err', e?.message || 'Could not generate suggestions.') }
    finally { setBusy(false) }
  }

  useEffect(() => { if (initialIndustry) fetchSug(false) }, [])
  // voice-driven: { industry, focus, ai, run }
  useEffect(() => {
    if (!suggestReq) return
    if (suggestReq.industry) setIndustry(suggestReq.industry)
    if (suggestReq.focus !== undefined) setFocus(suggestReq.focus)
    fetchSug(!!suggestReq.ai, { industry: suggestReq.industry, focus: suggestReq.focus })
  }, [suggestReq?.run])

  const applyNow = async () => {
    if (!sug) { onFlash('err', 'Generate a suggestion first.'); return '' }
    setBusy(true)
    try {
      const r = await api.post('/suggestions/apply', {
        suggestion: sug, adopt_agents: adopt.agents, adopt_pipelines: adopt.pipelines,
        adopt_tasks: adopt.tasks, product_name: focus || undefined,
      })
      onApplied(); onFlash('ok', r.message || 'Adopted into your org.')
      // Adopting an org is a whole-business setup action → continue in Guided Setup.
      window.dispatchEvent(new Event('hermus:skin-changed'))
      nav('/guided-setup?from=company')
      return r.message
    } catch (e) { onFlash('err', e?.message || 'Could not adopt the org.'); return '' }
    finally { setBusy(false) }
  }
  // let the page-level voice handler trigger "adopt"
  useEffect(() => { window.__companyApply = applyNow; return () => { if (window.__companyApply) delete window.__companyApply } })

  return (
    <div className="grid" style={{ gridTemplateColumns: sug ? '320px 1fr' : '1fr' }}>
      <div className="card" style={{ alignSelf: 'start' }}>
        <h3><Icon name="sparkles" size={17} /> Describe your needs</h3>
        <div className="field"><label>Industry</label>
          <select value={industry} onChange={(e) => setIndustry(e.target.value)}>
            {industries.map((i) => <option key={i} value={i}>{i}</option>)}
          </select></div>
        <div className="field"><label>Product / focus (optional)</label>
          <select value={focus} onChange={(e) => setFocus(e.target.value)}>
            <optgroup label="Focus areas">
              {focusAreas.map((fa) => <option key={fa} value={fa === 'General operations' ? '' : fa}>{fa}</option>)}
            </optgroup>
            {products.length > 0 && <optgroup label="Your products">
              {products.map((p) => <option key={p.id} value={p.name}>{p.name}</option>)}
            </optgroup>}
          </select></div>
        <div className="row-actions">
          <button className="btn secondary" onClick={() => fetchSug(false)} disabled={busy}>
            <Icon name="layers" size={15} /> Suggest</button>
          <button className="btn" onClick={() => fetchSug(true)} disabled={busy}>
            <Icon name="sparkles" size={15} /> Generate with AI</button>
        </div>
        {busy && <div className="muted mt" style={{ fontSize: 12 }}>Working… AI generation runs on-device and can take a moment.</div>}
      </div>

      {sug && (
        <div>
          {sug.focus && <div className="card mb" style={{ borderColor: 'var(--primary)' }}>
            <Icon name="sparkles" size={14} style={{ color: 'var(--primary)' }} /> Tailored for <strong>{sug.focus}</strong> — note the focus pipeline at the top.</div>}
          {sug.lifecycle?.length > 0 && (
            <div className="card mb">
              <h3><Icon name="workflow" size={17} /> Lifecycle stages</h3>
              <div className="flex wrap" style={{ gap: 0 }}>
                {sug.lifecycle.map((st, i) => (
                  <span key={st} className="flex" style={{ gap: 0 }}>
                    <span className="tag" style={{ background: 'var(--grad-soft)', color: 'var(--primary)', borderColor: 'transparent', fontWeight: 600 }}>{st}</span>
                    {i < sug.lifecycle.length - 1 && <span className="muted" style={{ margin: '0 6px' }}>→</span>}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="card mb">
            <div className="between mb">
              <h3 style={{ margin: 0 }}><Icon name="users" size={17} /> Suggested AI organization
                <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}> · {sug.agents.length} agents</span>
                <span className="tag" style={{ marginLeft: 8, color: sug.source === 'ai' ? 'var(--accent)' : 'var(--muted)' }}>
                  {sug.source === 'ai' ? '🧠 AI-tailored' : 'curated template'}</span></h3>
            </div>
            {(sug.departments || []).map((dept) => {
              const list = sug.agents.filter((a) => a.department === dept)
              if (!list.length) return null
              return (
                <div key={dept} style={{ marginBottom: 14 }}>
                  <div className="org-dept-label" style={{ marginBottom: 8 }}>{dept}</div>
                  <div className="grid cols-3" style={{ gap: 10 }}>
                    {list.map((a) => (
                      <div key={a.name + a.designation} className="wf-node" style={{ alignItems: 'flex-start' }}>
                        <div className="ix" style={{ background: a.is_ceo ? 'var(--grad-2)' : 'var(--grad)' }}>{a.name[0]}</div>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{a.name}</div>
                          <div className="muted" style={{ fontSize: 12 }}>{a.designation}</div>
                          {a.reports_to && <div className="muted" style={{ fontSize: 11 }}>↳ {a.reports_to}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}
          </div>

          <div className="card mb">
            <h3><Icon name="workflow" size={17} /> Suggested pipelines ({sug.pipelines.length} options)</h3>
            {sug.pipelines.map((pl, idx) => (
              <div key={pl.name + idx} className="card mb" style={{ background: 'var(--panel-2)', boxShadow: 'none',
                ...(sug.focus && idx === 0 ? { borderColor: 'var(--primary)' } : {}) }}>
                <div className="between">
                  <strong>{pl.name}{sug.focus && idx === 0 && <span className="tag" style={{ marginLeft: 6, color: 'var(--primary)' }}>focus</span>}</strong>
                  {pl.approvals && <span className="tag"><Icon name="shield" size={12} /> approvals on</span>}
                </div>
                <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>{pl.description}</div>
                {pl.steps.map((st, i) => (
                  <div key={i} style={{ fontSize: 12.5, padding: '3px 0' }}>
                    <span className="tag" style={{ marginRight: 6 }}>{i + 1}</span>
                    <strong>{st.agent_name}</strong> — {st.instruction}
                  </div>
                ))}
              </div>
            ))}
          </div>

          <div className="grid cols-2 mb">
            {sug.kg_entities?.length > 0 && (
              <div className="card">
                <h3><Icon name="graph" size={17} /> Knowledge-graph entities</h3>
                <div className="flex wrap">
                  {sug.kg_entities.map((e) => <span key={e} className="tag">{e}</span>)}
                </div>
              </div>
            )}
            {sug.rules?.length > 0 && (
              <div className="card">
                <h3><Icon name="shield" size={17} /> Industry rules ({sug.rules.length})</h3>
                {sug.rules.map((r) => (
                  <div key={r.id} style={{ padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                    <div className="flex" style={{ gap: 7 }}>
                      <span className="tag">{r.id}</span>
                      {r.locked && <span className="tag" style={{ color: 'var(--red)' }}>🔒 locked</span>}
                      <strong style={{ fontSize: 12.5 }}>{r.condition}</strong>
                    </div>
                    <div className="muted" style={{ fontSize: 12, marginLeft: 2 }}>→ {r.behavior}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <h3><Icon name="tasks" size={17} /> Task library ({sug.tasks.length})</h3>
            <div className="flex wrap mb">
              {sug.tasks.map((t, i) => <span key={i} className="tag">{t.title} · {t.agent_name}</span>)}
            </div>
            <div className="between" style={{ borderTop: '1px solid var(--border)', paddingTop: 14 }}>
              <div className="flex wrap">
                {[['agents', 'Agents'], ['pipelines', 'Pipelines'], ['tasks', 'Tasks']].map(([k, l]) => (
                  <label key={k} className="flex" style={{ fontSize: 13, width: 'auto', cursor: 'pointer' }}>
                    <input type="checkbox" checked={adopt[k]} style={{ width: 16 }}
                      onChange={(e) => setAdopt({ ...adopt, [k]: e.target.checked })} /> {l}
                  </label>
                ))}
              </div>
              <button className="btn" onClick={applyNow} disabled={busy}>
                <Icon name="check" size={15} /> Adopt into my org</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
