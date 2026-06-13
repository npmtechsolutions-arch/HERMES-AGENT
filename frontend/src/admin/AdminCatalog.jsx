import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead } from '../components/ui'

const SECTIONS = [
  ['verticals', 'Verticals', 'Turnkey full-business packages'],
  ['solutions', 'Solutions', 'Single-purpose focused agents'],
  ['engines', 'Universal Engines', 'The shared engines under everything'],
  ['marketplace', 'Marketplace', 'Installable packs (you can publish new ones)'],
]
const PACK_TYPES = ['skill', 'agent_pack', 'workflow', 'integration', 'industry_template']

export default function AdminCatalog() {
  const [cat, setCat] = useState(null)
  const [tab, setTab] = useState('verticals')
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(null)
  const [create, setCreate] = useState(false)
  const [msg, setMsg] = useState(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const load = () => api.get('/admin/catalog').then(setCat).catch(() => flash('err', 'Could not load the catalog.'))
  useEffect(() => { load() }, [])

  const toggle = async (section, item, enabled) => {
    setBusy(item.id)
    try { const r = await api.post(`/admin/catalog/${section}/${item.id}/toggle`, { enabled }); flash(enabled ? 'ok' : 'err', r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not change visibility.') }
    finally { setBusy(null) }
  }

  if (!cat) return <Loading />
  const items = cat[tab] || []
  const shown = items.filter((it) => !q || `${it.name} ${it.id}`.toLowerCase().includes(q.toLowerCase()))
  const enabledCount = items.filter((i) => i.enabled).length

  return (
    <>
      <PageHead title="Catalog Control"
        sub="The master switches. Disable anything to hide it from every tenant; enable to publish it. Admin owns what users can see and use.">
        {tab === 'marketplace' && <button className="btn" onClick={() => setCreate(true)}><Icon name="plus" size={16} /> Publish a pack</button>}
      </PageHead>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="card mb">
        <div className="flex wrap" style={{ gap: 8, alignItems: 'center' }}>
          {SECTIONS.map(([k, label]) => (
            <button key={k} className={'btn sm ' + (tab === k ? '' : 'ghost')} onClick={() => { setTab(k); setQ('') }}>
              {label} <span className="tag" style={{ marginLeft: 4 }}>{cat[k].filter((i) => i.enabled).length}/{cat[k].length}</span></button>
          ))}
          <input style={{ marginLeft: 'auto', maxWidth: 240 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Search ${tab}…`} />
        </div>
      </div>

      <div className="card">
        <div className="between mb">
          <h3 style={{ margin: 0 }}>{SECTIONS.find(([k]) => k === tab)[1]} <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>· {enabledCount}/{items.length} enabled · {SECTIONS.find(([k]) => k === tab)[2]}</span></h3>
        </div>
        <div style={{ maxHeight: 560, overflowY: 'auto' }}>
          {shown.map((it) => (
            <div key={it.id} className="between" style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{it.name}
                  {it.type && <span className="tag" style={{ marginLeft: 6, fontSize: 10 }}>{it.type.replace('_', ' ')}</span>}
                  {it.status && it.status !== 'approved' && <span className="tag" style={{ marginLeft: 6, fontSize: 10, color: 'var(--amber)' }}>{it.status}</span>}</div>
                <div className="muted" style={{ fontSize: 11, fontFamily: 'monospace' }}>{it.id}{it.industry ? ` · ${it.industry}` : ''}{it.target ? ` · ${it.target}` : ''}</div>
              </div>
              <div className="flex" style={{ gap: 8 }}>
                <span className="tag" style={{ color: it.enabled ? 'var(--green)' : 'var(--muted)' }}>{it.enabled ? '● live' : '○ hidden'}</span>
                <button className={'btn sm ' + (it.enabled ? 'ghost' : 'green')} disabled={busy === it.id}
                  onClick={() => toggle(tab, it, !it.enabled)}>{it.enabled ? 'Disable' : 'Enable'}</button>
              </div>
            </div>
          ))}
          {shown.length === 0 && <div className="muted" style={{ fontSize: 13, padding: 10 }}>Nothing matches.</div>}
        </div>
      </div>

      {create && <CreatePack onClose={() => setCreate(false)} onDone={load} onFlash={flash} />}
    </>
  )
}

function CreatePack({ onClose, onDone, onFlash }) {
  const [f, setF] = useState({ name: '', type: 'skill', description: '', is_free: true, publish: true })
  const submit = async () => {
    if (!f.name.trim()) { onFlash('err', 'Give the pack a name.'); return }
    try { const r = await api.post('/admin/marketplace', f); onFlash('ok', r.message); onDone(); onClose() }
    catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not publish.') }
  }
  return (
    <Modal title="Publish a marketplace pack" onClose={onClose}>
      <p className="muted" style={{ fontSize: 13 }}>Authored by you, instantly available to every tenant (or held for review).</p>
      <div className="field"><label>Name</label><input autoFocus value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
      <div className="grid cols-2" style={{ gap: 12 }}>
        <div className="field"><label>Type</label>
          <select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}>{PACK_TYPES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}</select></div>
        <div className="field"><label>Pricing</label>
          <select value={f.is_free ? 'free' : 'paid'} onChange={(e) => setF({ ...f, is_free: e.target.value === 'free' })}>
            <option value="free">Free</option><option value="paid">Paid</option></select></div>
      </div>
      <div className="field"><label>Description</label><textarea rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></div>
      <label className="flex mb" style={{ width: 'auto', fontSize: 13, cursor: 'pointer' }}>
        <input type="checkbox" checked={f.publish} style={{ width: 16 }} onChange={(e) => setF({ ...f, publish: e.target.checked })} /> Publish live now (uncheck to hold for review)
      </label>
      <button className="btn" style={{ width: '100%' }} onClick={submit}>{f.publish ? 'Publish to all tenants' : 'Create (in review)'}</button>
    </Modal>
  )
}
