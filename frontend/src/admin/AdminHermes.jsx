import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

export default function AdminHermes() {
  const [data, setData] = useState(null)
  const [draft, setDraft] = useState({})
  const [dirty, setDirty] = useState({})
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const load = () => api.get('/admin/hermes').then((d) => { setData(d); setDraft({ ...d.effective }); setDirty({}) }).catch(() => flash('err', 'Could not load Hermes defaults.'))
  useEffect(() => { load() }, [])

  const set = (k, v) => { setDraft((d) => ({ ...d, [k]: v })); setDirty((x) => ({ ...x, [k]: true })) }
  const save = async () => {
    const changed = Object.keys(dirty)
    if (!changed.length) { flash('err', 'No changes to save.'); return }
    setBusy(true)
    try { const r = await api.patch('/admin/hermes', { config: Object.fromEntries(changed.map((k) => [k, draft[k]])) }); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not save.') }
    finally { setBusy(false) }
  }
  const reset = async () => {
    if (!window.confirm('Reset fleet Hermes defaults to the built-in baseline? (Tenants keep their own overrides.)')) return
    try { const r = await api.post('/admin/hermes/reset'); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.message || 'Could not reset.') }
  }

  if (!data) return <Loading />
  const o = data.options
  const overridden = (k) => JSON.stringify(data.platform[k]) !== undefined && k in data.platform
  const Field = ({ k, label, children }) => (
    <div className="field">
      <label>{label}{overridden(k) && <span className="tag" style={{ marginLeft: 6, fontSize: 10, color: 'var(--amber)' }}>fleet override</span>}</label>
      {children}
      <div className="muted" style={{ fontSize: 11 }}>baseline: {String(data.code_defaults[k])}</div>
    </div>
  )
  const Num = ({ k }) => <input type="number" value={draft[k] ?? ''} onChange={(e) => set(k, e.target.value === '' ? '' : Number(e.target.value))} />
  const Sel = ({ k, opts }) => <select value={draft[k] ?? ''} onChange={(e) => set(k, e.target.value)}>
    {opts.map((op) => typeof op === 'string' ? <option key={op} value={op}>{op}</option> : <option key={op.value} value={op.value}>{op.label}</option>)}</select>
  const Bool = ({ k }) => <label className="flex" style={{ width: 'auto', cursor: 'pointer', fontSize: 13 }}>
    <input type="checkbox" checked={!!draft[k]} style={{ width: 16 }} onChange={(e) => set(k, e.target.checked)} /> enabled</label>

  return (
    <>
      <PageHead title="Hermes Agent — Fleet Defaults"
        sub="The default agent configuration EVERY tenant inherits. Tenants may override these per-tenant in Settings. Tune for better output across the whole fleet.">
        <div className="row-actions">
          <button className="btn ghost sm" onClick={reset}>Reset to baseline</button>
          <button className="btn" onClick={save} disabled={busy || !Object.keys(dirty).length}>{busy ? 'Saving…' : `Save fleet defaults${Object.keys(dirty).length ? ` (${Object.keys(dirty).length})` : ''}`}</button>
        </div>
      </PageHead>

      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="card mb" style={{ background: data.customized ? 'var(--panel-2)' : 'var(--success-bg)', boxShadow: 'none', border: '1px solid var(--border)' }}>
        <div className="flex" style={{ fontSize: 13 }}>
          <span className={'pill ' + (data.runtime_online ? 'st-online' : 'st-error')}><span className="dot" />
            {data.runtime_online ? 'runtime online' : 'runtime offline'}</span>
          <span className="muted">Config layers: <strong>code baseline → fleet defaults (here) → per-tenant override</strong>. {data.customized ? `${Object.keys(data.platform).length} field(s) customized.` : 'Currently all baseline.'}</span>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3><Icon name="cpu" size={17} /> Reasoning & models</h3>
          <Field k="reasoning_model" label="Reasoning (smart) model">
            {data.installed_models.length
              ? <Sel k="reasoning_model" opts={data.installed_models.map((m) => m.name)} />
              : <input value={draft.reasoning_model ?? ''} onChange={(e) => set('reasoning_model', e.target.value)} />}</Field>
          <Field k="fast_model" label="Fast model">
            {data.installed_models.length
              ? <Sel k="fast_model" opts={data.installed_models.map((m) => m.name)} />
              : <input value={draft.fast_model ?? ''} onChange={(e) => set('fast_model', e.target.value)} />}</Field>
          <Field k="embed_model" label="Embedding model"><input value={draft.embed_model ?? ''} onChange={(e) => set('embed_model', e.target.value)} /></Field>
        </div>

        <div className="card">
          <h3><Icon name="zap" size={17} /> Generation</h3>
          <Field k="temperature" label={`Creativity (temperature) — ${draft.temperature}`}>
            <input type="range" min="0" max="1" step="0.05" value={draft.temperature ?? 0.3} onChange={(e) => set('temperature', Number(e.target.value))} style={{ width: '100%' }} /></Field>
          <Field k="max_tokens" label="Max response tokens"><Num k="max_tokens" /></Field>
          <Field k="context_window" label="Context window"><Num k="context_window" /></Field>
        </div>

        <div className="card">
          <h3><Icon name="sparkles" size={17} /> Behaviour & output quality</h3>
          <Field k="autonomy" label="Autonomy"><Sel k="autonomy" opts={o.autonomy} /></Field>
          <Field k="tone" label="Default tone"><Sel k="tone" opts={o.tone} /></Field>
          <Field k="verbosity" label="Verbosity"><Sel k="verbosity" opts={o.verbosity} /></Field>
          <Field k="grounding" label="Grounding (hallucination control)"><Sel k="grounding" opts={o.grounding} /></Field>
          <Field k="language" label="Default language"><Sel k="language" opts={o.language} /></Field>
        </div>

        <div className="card">
          <h3><Icon name="shield" size={17} /> Safety & limits</h3>
          <Field k="approval_threshold_inr" label="Approval threshold (₹) — money above this needs approval"><Num k="approval_threshold_inr" /></Field>
          <Field k="retry_count" label="Retries on failure"><Num k="retry_count" /></Field>
          <Field k="failover_managed" label="Failover to managed gateway on local failure"><Bool k="failover_managed" /></Field>
          <Field k="telemetry" label="Telemetry (anonymous usage)"><Bool k="telemetry" /></Field>
        </div>
      </div>
    </>
  )
}
