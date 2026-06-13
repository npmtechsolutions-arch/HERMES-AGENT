import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, Modal, PageHead } from '../components/ui'

const SCOPE_COLOR = { locked: 'var(--red)', overridable: 'var(--amber)', suggestion: 'var(--green)' }
const SCOPES = ['locked', 'overridable', 'suggestion']

export default function AdminConfig() {
  const [cfg, setCfg] = useState(null)
  const [bundles, setBundles] = useState([])
  const [edit, setEdit] = useState(null)   // { domain, key, valueText, scope }
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const load = () => Promise.all([api.get('/admin/configs'), api.get('/admin/configs/bundles').catch(() => [])])
    .then(([c, b]) => { setCfg(c); setBundles(b) }).catch(() => flash('err', 'Could not load config.'))
  useEffect(() => { load() }, [])

  const publish = async (stage) => {
    setBusy(true)
    try { const r = await api.post('/admin/configs/publish', { stage }); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not publish.') }
    finally { setBusy(false) }
  }
  const saveItem = async (item) => {
    let value
    try { value = JSON.parse(item.valueText) } catch { flash('err', 'Value must be valid JSON.'); return }
    try { const r = await api.put('/admin/configs', { domain: item.domain, key: item.key, value, scope: item.scope }); flash('ok', r.message); setEdit(null); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not save.') }
  }

  if (!cfg) return <Loading />
  return (
    <>
      <PageHead title="Common Configuration Studio"
        sub="Signed, versioned bundles pushed to all desktops — locked / overridable / suggestion." />
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="grid cols-2">
        {Object.entries(cfg).map(([domain, items]) => (
          <div className="card" key={domain}>
            <h3 style={{ textTransform: 'capitalize' }}>{domain.replace(/_/g, ' ')}</h3>
            {items.map((it) => (
              <div key={it.id} className="between" style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{it.key}</div>
                  <div className="muted" style={{ fontSize: 12, wordBreak: 'break-all' }}>{JSON.stringify(it.value)}</div>
                </div>
                <div className="flex" style={{ gap: 6 }}>
                  <span className="tag" style={{ color: SCOPE_COLOR[it.scope] }}>{it.scope}</span>
                  <button className="btn ghost sm" disabled={it.scope === 'locked'} title={it.scope === 'locked' ? 'Locked items are platform-enforced' : 'Edit'}
                    onClick={() => setEdit({ domain, key: it.key, valueText: JSON.stringify(it.value, null, 2), scope: it.scope })}>Edit</button>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="card mt">
        <div className="between">
          <div><strong>Publish bundle</strong>
            <div className="muted" style={{ fontSize: 12 }}>Canary → publish → rollback. Auto-halt if canary error rate exceeds threshold (PA-04).</div></div>
          <div className="row-actions">
            <button className="btn secondary sm" disabled={busy} onClick={() => publish('canary')}>Canary (5%)</button>
            <button className="btn sm" disabled={busy} onClick={() => publish('publish')}>Publish to fleet</button>
          </div>
        </div>
        {bundles.length > 0 && <div className="mt">
          {bundles.map((b) => (
            <div key={b.version} className="between" style={{ fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--border)' }}>
              <span>Bundle v{b.version} · <span className="tag">{b.state}</span></span>
              <span className="muted" style={{ fontFamily: 'monospace' }}>{b.sha256}…{b.published_at ? ` · ${new Date(b.published_at).toLocaleString()}` : ''}</span>
            </div>
          ))}
        </div>}
      </div>

      {edit && <Modal title={`Edit ${edit.domain}/${edit.key}`} onClose={() => setEdit(null)}>
        <div className="field"><label>Value (JSON)</label>
          <textarea rows={5} value={edit.valueText} onChange={(e) => setEdit({ ...edit, valueText: e.target.value })} style={{ fontFamily: 'monospace' }} /></div>
        <div className="field"><label>Scope</label>
          <select value={edit.scope} onChange={(e) => setEdit({ ...edit, scope: e.target.value })}>
            {SCOPES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
        <button className="btn" style={{ width: '100%' }} onClick={() => saveItem(edit)}>Save</button>
      </Modal>}
    </>
  )
}
