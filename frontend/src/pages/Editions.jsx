import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// User-facing product picker. Editions are the sub-products the admin publishes;
// activating one sets up its roster and skins the workspace to it.
export default function Editions() {
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(null)
  const [msg, setMsg] = useState(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 9000) }
  const load = () => api.get('/editions').then(setData).catch(() => flash('err', 'Could not load products.'))
  useEffect(() => { load() }, [])

  const activate = async (e) => {
    if (!window.confirm(`Activate “${e.name}”? This sets up its agents and tailors your workspace to it.`)) return
    setBusy(e.slug)
    try {
      const r = await api.post(`/editions/${e.slug}/activate`)
      flash('ok', r.message)
      await load()
      // re-skin the app shell immediately
      window.dispatchEvent(new Event('hermus:skin-changed'))
    } catch (err) { flash('err', err?.detail?.message || err?.message || 'Could not activate.') }
    finally { setBusy(null) }
  }

  if (!data) return <Loading />
  const items = data.items || []

  return (
    <>
      <PageHead title="Products" sub="The HERMUS product you're running. Each is a complete assistant tailored to a purpose — activate one to set it up." />
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="grid cols-2">
        {items.map((e) => (
          <div key={e.id} className="card" style={{ borderColor: e.active ? 'var(--violet)' : undefined }}>
            <div className="between">
              <h3 style={{ margin: 0 }}><Icon name="sparkles" size={17} /> {e.name}</h3>
              {e.active
                ? <span className="pill st-completed"><span className="dot" /> active</span>
                : <span className="tag">{e.layer.replace('_', ' ')}</span>}
            </div>
            <p className="muted" style={{ fontSize: 13, minHeight: 38 }}>{e.tagline}</p>

            <div className="flex wrap" style={{ gap: 5, marginBottom: 10 }}>
              {(e.modules_detail || []).slice(0, 8).map((m) => (
                <span key={m.id} className="tag" style={{ fontSize: 10 }}>{m.name.split(' ')[0]}</span>
              ))}
              {(e.enabled_modules || []).length > 8 && <span className="tag" style={{ fontSize: 10 }}>+{e.enabled_modules.length - 8}</span>}
            </div>

            {(e.price_book?.plans || []).length > 0 && (
              <div className="flex wrap" style={{ gap: 8, marginBottom: 12 }}>
                {e.price_book.plans.map((p) => (
                  <div key={p.name} className="stat" style={{ padding: 8, display: 'block', minWidth: 92 }}>
                    <div className="label">{p.name}</div>
                    <div className="value" style={{ fontSize: 16 }}>{p.price_inr ? `₹${p.price_inr}` : 'Free'}</div>
                  </div>
                ))}
              </div>
            )}

            <button className={'btn ' + (e.active ? 'ghost' : '')} disabled={busy === e.slug || e.active}
              onClick={() => activate(e)}>
              {e.active ? 'Currently active' : busy === e.slug ? 'Activating…' : 'Activate this product'}
            </button>
          </div>
        ))}
        {items.length === 0 && <div className="muted" style={{ fontSize: 13, padding: 10 }}>No products available yet.</div>}
      </div>
    </>
  )
}
