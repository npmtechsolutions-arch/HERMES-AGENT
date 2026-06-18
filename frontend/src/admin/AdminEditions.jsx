import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead } from '../components/ui'

// The admin "Edition factory" — define a sub-product (roster + module flags +
// skin + price book) and publish it for users (Docs 19/20).
const BLANK = {
  slug: '', name: '', layer: 'role_app', template_key: '', tagline: '', description: '',
  enabled_engines: [], enabled_modules: [], skin: { brand: '', color: 'violet', hidden_nav: [], onboarding: '' },
  price_book: { plans: [] }, locked_rules: [], is_default: false, sort: 100,
}

export default function AdminEditions() {
  const [rows, setRows] = useState(null)
  const [cat, setCat] = useState(null)
  const [edit, setEdit] = useState(null)   // edition being edited (or BLANK for new)
  const [busy, setBusy] = useState(null)
  const [msg, setMsg] = useState(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const load = () => api.get('/admin/editions').then((d) => setRows(d.items)).catch(() => flash('err', 'Could not load editions.'))
  useEffect(() => {
    load()
    api.get('/admin/editions/catalog').then(setCat).catch(() => {})
  }, [])

  const publish = async (e) => {
    setBusy(e.id)
    try { const r = await api.post(`/admin/editions/${e.id}/publish`); flash('ok', r.message); load() }
    catch (err) { flash('err', err?.detail?.message || err?.message || 'Could not change status.') }
    finally { setBusy(null) }
  }
  const remove = async (e) => {
    if (!window.confirm(`Delete edition “${e.name}”? This cannot be undone.`)) return
    setBusy(e.id)
    try { const r = await api.del(`/admin/editions/${e.id}`); flash('ok', r.message); load() }
    catch (err) { flash('err', err?.detail?.message || err?.message || 'Could not delete.') }
    finally { setBusy(null) }
  }

  if (!rows) return <Loading />
  const live = rows.filter((r) => r.status === 'published').length

  return (
    <>
      <PageHead title="Editions"
        sub="Your sub-product factory. Each edition = roster + module flags + branding skin + price book — published to users, no code fork (Docs 19/20).">
        <button className="btn" onClick={() => setEdit({ ...BLANK })}><Icon name="plus" size={16} /> New edition</button>
      </PageHead>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="card">
        <div className="between mb"><h3 style={{ margin: 0 }}>All editions <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>· {live}/{rows.length} published</span></h3></div>
        {rows.map((e) => (
          <div key={e.id} className="between" style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{e.name}
                <span className="tag" style={{ marginLeft: 6, fontSize: 10 }}>{e.layer}</span>
                {e.is_default && <span className="tag" style={{ marginLeft: 4, fontSize: 10, color: 'var(--violet)' }}>default</span>}
                <span className="tag" style={{ marginLeft: 4, fontSize: 10, color: e.status === 'published' ? 'var(--green)' : 'var(--muted)' }}>
                  {e.status === 'published' ? '● live' : '○ ' + e.status}</span>
              </div>
              <div className="muted" style={{ fontSize: 12 }}>{e.tagline}</div>
              <div className="muted" style={{ fontSize: 11, fontFamily: 'monospace' }}>
                {e.slug} · {(e.enabled_modules || []).length} modules · {(e.enabled_engines || []).length} engines · {(e.price_book?.plans || []).length} plans</div>
            </div>
            <div className="flex" style={{ gap: 8 }}>
              <button className="btn ghost sm" onClick={() => setEdit(e)}>Edit</button>
              <button className={'btn sm ' + (e.status === 'published' ? 'ghost' : 'green')} disabled={busy === e.id}
                onClick={() => publish(e)}>{e.status === 'published' ? 'Unpublish' : 'Publish'}</button>
              <button className="btn ghost sm" disabled={busy === e.id} onClick={() => remove(e)} title="Delete edition">Delete</button>
            </div>
          </div>
        ))}
        {rows.length === 0 && <div className="muted" style={{ fontSize: 13, padding: 10 }}>No editions yet. Create your first sub-product.</div>}
      </div>

      {edit && <EditionEditor edition={edit} cat={cat} onClose={() => setEdit(null)} onDone={load} onFlash={flash} />}
    </>
  )
}

function EditionEditor({ edition, cat, onClose, onDone, onFlash }) {
  const isNew = !edition.id
  const [f, setF] = useState({
    ...BLANK, ...edition,
    skin: { ...BLANK.skin, ...(edition.skin || {}) },
    price_book: { plans: [], ...(edition.price_book || {}) },
  })
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }))
  const setSkin = (k, v) => setF((x) => ({ ...x, skin: { ...x.skin, [k]: v } }))
  const toggleArr = (k, id) => setF((x) => ({ ...x, [k]: x[k].includes(id) ? x[k].filter((i) => i !== id) : [...x[k], id] }))

  const save = async () => {
    if (!f.slug.trim() || !f.name.trim()) { onFlash('err', 'Slug and name are required.'); return }
    const body = {
      slug: f.slug.trim(), name: f.name.trim(), layer: f.layer, template_key: f.template_key || null,
      tagline: f.tagline, description: f.description, enabled_engines: f.enabled_engines,
      enabled_modules: f.enabled_modules, skin: f.skin, price_book: f.price_book,
      locked_rules: f.locked_rules, is_default: !!f.is_default, sort: Number(f.sort) || 100,
    }
    try {
      const r = isNew ? await api.post('/admin/editions', body) : await api.patch(`/admin/editions/${edition.id}`, body)
      onFlash('ok', r.message); onDone(); onClose()
    } catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not save.') }
  }

  // group modules for the toggle grid
  const groups = {}
  for (const m of (cat?.modules || [])) (groups[m.group] = groups[m.group] || []).push(m)

  return (
    <Modal title={isNew ? 'New edition' : `Edit — ${edition.name}`} onClose={onClose} wide>
      <div className="grid cols-2" style={{ gap: 12 }}>
        <div className="field"><label>Name</label><input autoFocus value={f.name} onChange={(e) => set('name', e.target.value)} placeholder="HERMUS Personal" /></div>
        <div className="field"><label>Slug</label><input value={f.slug} onChange={(e) => set('slug', e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} placeholder="personal" disabled={!isNew} /></div>
      </div>
      <div className="grid cols-2" style={{ gap: 12 }}>
        <div className="field"><label>Layer</label>
          <select value={f.layer} onChange={(e) => set('layer', e.target.value)}>
            {(cat?.layers || ['universal', 'edition', 'role_app']).map((l) => <option key={l} value={l}>{l}</option>)}</select></div>
        <div className="field"><label>Roster template</label>
          <select value={f.template_key || ''} onChange={(e) => set('template_key', e.target.value)}>
            <option value="">— none —</option>
            {(cat?.templates || []).map((t) => <option key={t} value={t}>{t}</option>)}</select></div>
      </div>
      <div className="field"><label>Tagline</label><input value={f.tagline || ''} onChange={(e) => set('tagline', e.target.value)} /></div>
      <div className="field"><label>Description</label><textarea rows={2} value={f.description || ''} onChange={(e) => set('description', e.target.value)} /></div>

      <label style={{ fontSize: 12, fontWeight: 600, marginTop: 6 }}>Engines ({f.enabled_engines.length})</label>
      <div className="flex wrap" style={{ gap: 6, margin: '4px 0 10px' }}>
        {(cat?.engines || []).map((en) => (
          <button key={en.id} className={'btn sm ' + (f.enabled_engines.includes(en.id) ? '' : 'ghost')}
            onClick={() => toggleArr('enabled_engines', en.id)} title={en.name}>{en.id}</button>
        ))}
      </div>

      <label style={{ fontSize: 12, fontWeight: 600 }}>Modules ({f.enabled_modules.length})</label>
      <div style={{ maxHeight: 180, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 8, padding: 8, margin: '4px 0 10px' }}>
        {Object.entries(groups).map(([g, ms]) => (
          <div key={g} style={{ marginBottom: 6 }}>
            <div className="muted" style={{ fontSize: 10, textTransform: 'uppercase', letterSpacing: 1 }}>{g}</div>
            <div className="flex wrap" style={{ gap: 5, marginTop: 3 }}>
              {ms.map((m) => (
                <button key={m.id} className={'btn sm ' + (f.enabled_modules.includes(m.id) ? '' : 'ghost')}
                  style={{ fontSize: 11 }} onClick={() => toggleArr('enabled_modules', m.id)} title={m.name}>
                  {m.id} {m.name.split(' ')[0]}</button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="grid cols-2" style={{ gap: 12 }}>
        <div className="field"><label>Brand (skin)</label><input value={f.skin.brand || ''} onChange={(e) => setSkin('brand', e.target.value)} placeholder="HERMUS Personal" /></div>
        <div className="field"><label>Accent color</label>
          <select value={f.skin.color || 'violet'} onChange={(e) => setSkin('color', e.target.value)}>
            {['violet', 'blue', 'green', 'amber', 'rose', 'teal'].map((c) => <option key={c} value={c}>{c}</option>)}</select></div>
      </div>
      <div className="field"><label>Hidden nav (comma-separated paths)</label>
        <input value={(f.skin.hidden_nav || []).join(', ')} onChange={(e) => setSkin('hidden_nav', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
          placeholder="/leads, /compliance, /gateway" /></div>
      <div className="field"><label>Locked rules (comma-separated ids)</label>
        <input value={(f.locked_rules || []).join(', ')} onChange={(e) => set('locked_rules', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
          placeholder="PP-R2, PP-R3, PP-R4" /></div>
      <div className="field"><label>Price book (JSON)</label>
        <textarea rows={4} style={{ fontFamily: 'monospace', fontSize: 11 }} value={JSON.stringify(f.price_book, null, 1)}
          onChange={(e) => { try { set('price_book', JSON.parse(e.target.value)) } catch { /* keep typing */ } }} /></div>

      <label className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer', margin: '4px 0 12px' }}>
        <input type="checkbox" checked={!!f.is_default} style={{ width: 16 }} onChange={(e) => set('is_default', e.target.checked)} />
        Default edition (new users land on this)
      </label>
      <button className="btn" style={{ width: '100%' }} onClick={save}>{isNew ? 'Create draft' : 'Save changes'}</button>
    </Modal>
  )
}
