import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, PageHead, Pill } from '../components/ui'

export default function Billing() {
  const [sub, setSub] = useState(null)
  const [plans, setPlans] = useState([])
  const [invoices, setInvoices] = useState([])
  const [msg, setMsg] = useState('')

  const load = () => Promise.all([
    api.get('/subscription'), api.get('/plans'), api.get('/invoices'),
  ]).then(([s, p, i]) => { setSub(s); setPlans(p); setInvoices(i) })
  useEffect(() => { load() }, [])
  if (!sub) return <Loading />

  const checkout = async (planId) => {
    const r = await api.post('/subscription/checkout', { plan_id: planId })
    setMsg(`✅ Now on ${r.plan.name}. Invoice ${r.invoice_id} issued.`); load()
    setTimeout(() => setMsg(''), 3500)
  }

  const usageRow = (label, u) => {
    const limit = u.limit === 'unlimited' || u.limit == null ? '∞' : u.limit
    const pct = typeof u.limit === 'number' ? Math.min(100, (u.used / u.limit) * 100) : 10
    return (
      <div style={{ marginBottom: 12 }}>
        <div className="between" style={{ fontSize: 13, marginBottom: 4 }}>
          <span>{label}</span><span className="muted">{u.used} / {limit}</span></div>
        <div className="bar"><span style={{ width: `${pct}%` }} /></div>
      </div>
    )
  }

  return (
    <>
      <PageHead title="Subscription & Billing" sub="Usage vs plan limits, invoices, and upgrades." />
      {msg && <div className="card mb" style={{ borderColor: 'var(--green)' }}>{msg}</div>}

      <div className="grid cols-2 mb">
        <div className="card">
          <div className="between mb">
            <h3 style={{ margin: 0 }}>Current plan: {sub.plan?.name}</h3>
            <Pill status={sub.status} />
          </div>
          <div className="muted mb" style={{ fontSize: 13 }}>
            ₹{sub.plan?.price?.toLocaleString()}/{sub.plan?.billing_period}
            {sub.current_period_end && ` · renews ${new Date(sub.current_period_end).toLocaleDateString()}`}
          </div>
          {usageRow('AI Agents', sub.usage.agents)}
          {usageRow('Workflows', sub.usage.workflows)}
          {usageRow('Devices', sub.usage.devices)}
          {usageRow('Seats', sub.usage.seats)}
        </div>

        <div className="card">
          <h3>Invoices</h3>
          <table><thead><tr><th>Number</th><th>Total</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>{invoices.map((i) => (
              <tr key={i.id}><td>{i.number}</td><td>₹{i.total.toLocaleString()}</td>
                <td><Pill status={i.status} /></td>
                <td className="muted">{i.issued_at ? new Date(i.issued_at).toLocaleDateString() : '—'}</td></tr>
            ))}</tbody></table>
          {invoices.length === 0 && <div className="muted">No invoices yet.</div>}
        </div>
      </div>

      <h3 className="mb">Available plans</h3>
      <div className="grid cols-4">
        {plans.map((p) => {
          const current = p.id === sub.plan?.id
          return (
            <div className="card" key={p.id} style={current ? { borderColor: 'var(--primary)' } : {}}>
              <h3 style={{ margin: 0 }}>{p.name}</h3>
              <div style={{ fontSize: 24, fontWeight: 700, margin: '8px 0' }}>
                {p.price ? `₹${p.price.toLocaleString()}` : 'Free'}
                <span className="muted" style={{ fontSize: 12 }}>/{p.billing_period}</span></div>
              <ul style={{ paddingLeft: 16, fontSize: 13, lineHeight: 1.8, minHeight: 120 }}>
                <li>{p.limits.agents} agents</li>
                <li>{p.limits.workflows} workflows</li>
                <li>{p.limits.seats} seat(s)</li>
                <li>Channels: {(p.limits.channels || []).join(', ')}</li>
                {p.feature_flags.call_center && <li>AI Call Center</li>}
                {p.feature_flags.offline_mode && <li>Offline Enterprise</li>}
              </ul>
              <button className="btn sm" style={{ width: '100%' }} disabled={current}
                onClick={() => checkout(p.id)}>
                {current ? 'Current plan' : 'Switch to ' + p.name}</button>
            </div>
          )
        })}
      </div>
    </>
  )
}
