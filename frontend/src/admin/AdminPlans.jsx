import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, Modal, PageHead } from '../components/ui'

export default function AdminPlans() {
  const [plans, setPlans] = useState(null)
  const [edit, setEdit] = useState(null)
  const load = () => api.get('/admin/plans').then(setPlans)
  useEffect(() => { load() }, [])
  if (!plans) return <Loading />

  return (
    <>
      <PageHead title="Plans & Feature Flags" sub="Edit limits and flags — no code deploy (SRS-F-011)." />
      <div className="grid cols-4">
        {plans.map((p) => (
          <div className="card" key={p.id}>
            <div className="between"><h3 style={{ margin: 0 }}>{p.name}</h3>
              {!p.is_public && <span className="tag">private</span>}</div>
            <div style={{ fontSize: 22, fontWeight: 700, margin: '8px 0' }}>
              {p.price ? `₹${p.price.toLocaleString()}` : 'Free'}
              <span className="muted" style={{ fontSize: 12 }}>/{p.billing_period}</span></div>
            <div style={{ fontSize: 13, lineHeight: 1.9 }}>
              <div className="muted">Limits</div>
              {Object.entries(p.limits).map(([k, v]) => (
                <div key={k} className="between"><span>{k}</span>
                  <span className="tag">{Array.isArray(v) ? v.join(',') : String(v)}</span></div>
              ))}
            </div>
            <div className="mt" style={{ fontSize: 13 }}>
              <div className="muted">Flags</div>
              <div className="flex wrap">
                {Object.entries(p.feature_flags).map(([k, v]) => (
                  <span key={k} className="tag" style={{ color: v ? 'var(--green)' : 'var(--muted)' }}>
                    {k}: {String(v)}</span>
                ))}
              </div>
            </div>
            <button className="btn secondary sm mt" style={{ width: '100%' }} onClick={() => setEdit(p)}>Edit</button>
          </div>
        ))}
      </div>
      {edit && <EditPlan plan={edit} onClose={() => setEdit(null)} onSaved={load} />}
    </>
  )
}

function EditPlan({ plan, onClose, onSaved }) {
  const [price, setPrice] = useState(plan.price)
  const [limits, setLimits] = useState(JSON.stringify(plan.limits, null, 2))
  const [flags, setFlags] = useState(JSON.stringify(plan.feature_flags, null, 2))
  const [err, setErr] = useState('')

  const save = async () => {
    setErr('')
    try {
      await api.patch(`/admin/plans/${plan.id}`, {
        price: Number(price), limits: JSON.parse(limits), feature_flags: JSON.parse(flags),
      })
      onSaved(); onClose()
    } catch (e) { setErr(e.detail?.message || e.message) }
  }
  return (
    <Modal title={`Edit ${plan.name}`} onClose={onClose}>
      {err && <div className="error-box">{err}</div>}
      <div className="field"><label>Price (₹)</label><input type="number" value={price} onChange={(e) => setPrice(e.target.value)} /></div>
      <div className="field"><label>Limits (JSON)</label><textarea rows={6} value={limits} onChange={(e) => setLimits(e.target.value)} /></div>
      <div className="field"><label>Feature flags (JSON)</label><textarea rows={5} value={flags} onChange={(e) => setFlags(e.target.value)} /></div>
      <button className="btn" style={{ width: '100%' }} onClick={save}>Save plan</button>
    </Modal>
  )
}
