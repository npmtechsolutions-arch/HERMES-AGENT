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

  const activate = async (e, tier) => {
    const t = (tier || 'personal').toLowerCase()
    if (!window.confirm(`Activate “${e.name}”${tier ? ` on the ${tier} plan` : ''}? This sets up its agents and tailors your workspace — your left panel reflects this product and plan.`)) return
    setBusy(e.slug)
    try {
      const r = await api.post(`/editions/${e.slug}/activate?tier=${encodeURIComponent(t)}`)
      flash('ok', r.message)
      await load()
      window.dispatchEvent(new Event('hermus:skin-changed'))   // re-skin + re-gate the shell immediately
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
                  <button key={p.name} className="stat" disabled={busy === e.slug}
                    onClick={() => activate(e, p.name)} title={p.scope || `Activate on ${p.name}`}
                    style={{ padding: 8, display: 'block', minWidth: 92, textAlign: 'left', cursor: 'pointer', border: '1px solid var(--border)' }}>
                    <div className="label">{p.name}</div>
                    <div className="value" style={{ fontSize: 16 }}>{p.price_inr ? `₹${p.price_inr}` : 'Free'}</div>
                  </button>
                ))}
              </div>
            )}

            {e.active
              ? <button className="btn ghost" disabled>Currently active — pick a plan above to change tier</button>
              : <button className="btn" disabled={busy === e.slug} onClick={() => activate(e, 'personal')}>
                  {busy === e.slug ? 'Activating…' : 'Activate this product'}</button>}
          </div>
        ))}
        {items.length === 0 && <div className="muted" style={{ fontSize: 13, padding: 10 }}>No products available yet.</div>}
      </div>
    </>
  )
}
