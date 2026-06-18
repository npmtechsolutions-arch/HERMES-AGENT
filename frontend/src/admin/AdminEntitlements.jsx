import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, PageHead } from '../components/ui'

// Admin tier-gating: decide which module GROUP unlocks at which plan tier, and
// globally kill-switch any module. This + the Edition builder = full control of
// what every user sees on every plan.
export default function AdminEntitlements() {
  const [data, setData] = useState(null)
  const [cfg, setCfg] = useState(null)
  const [msg, setMsg] = useState(null)

  const flash = (kind, t) => { setMsg({ kind, t }); setTimeout(() => setMsg(null), 8000) }
  const load = () => api.get('/admin/entitlements').then((d) => { setData(d); setCfg(d.config) }).catch(() => flash('err', 'Could not load.'))
  useEffect(() => { load() }, [])

  const setGroupTier = (g, tier) => setCfg((c) => ({ ...c, group_min_tier: { ...c.group_min_tier, [g]: tier } }))
  const toggleDisabled = (mid) => setCfg((c) => {
    const d = new Set(c.disabled_modules || [])
    d.has(mid) ? d.delete(mid) : d.add(mid)
    return { ...c, disabled_modules: [...d] }
  })
  const save = async () => {
    try { const r = await api.patch('/admin/entitlements', { config: cfg }); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not save.') }
  }
  const reset = () => data && setCfg(data.defaults)

  if (!data || !cfg) return <Loading />
  const tiers = data.tiers
  const disabled = new Set(cfg.disabled_modules || [])

  return (
    <>
      <PageHead title="Plan Gating"
        sub="What each plan tier unlocks (by module group) + global module kill-switches. With the Edition builder, this decides exactly what every user sees.">
        <button className="btn ghost" onClick={reset}>Reset defaults</button>
      </PageHead>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.t}</div>}

      <div className="grid cols-2">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Module group → minimum tier</h3>
          <p className="muted" style={{ fontSize: 12 }}>A module unlocks once the user's plan is at or above its group's tier.</p>
          {data.groups.map((g) => (
            <div key={g} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 13, fontWeight: 600, textTransform: 'capitalize' }}>{g}</span>
              <select value={cfg.group_min_tier[g] || 'personal'} onChange={(e) => setGroupTier(g, e.target.value)} style={{ width: 'auto' }}>
                {tiers.map((t) => <option key={t} value={t}>{t}</option>)}</select>
            </div>
          ))}
          <button className="btn mt" onClick={save}>Save gating</button>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>Global module kill-switch</h3>
          <p className="muted" style={{ fontSize: 12 }}>Disabled modules are hidden from EVERY tenant, regardless of product or plan.</p>
          <div style={{ maxHeight: 460, overflowY: 'auto' }}>
            {data.modules.map((m) => (
              <label key={m.id} className="between" style={{ padding: '6px 0', borderBottom: '1px solid var(--border)', cursor: 'pointer' }}>
                <span style={{ fontSize: 12.5 }}>{m.id} · {m.name} <span className="tag" style={{ fontSize: 10 }}>{m.group}</span></span>
                <input type="checkbox" checked={!disabled.has(m.id)} onChange={() => toggleDisabled(m.id)}
                  title={disabled.has(m.id) ? 'Disabled' : 'Enabled'} style={{ width: 16 }} />
              </label>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
