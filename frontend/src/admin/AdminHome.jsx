import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { Loading, PageHead, Stat } from '../components/ui'
import Icon from '../components/Icon'

export default function AdminHome() {
  const [a, setA] = useState(null)
  useEffect(() => { api.get('/admin/analytics').then(setA) }, [])
  if (!a) return <Loading />

  return (
    <>
      <PageHead title="Platform Overview" sub="Aggregate, privacy-safe metrics — no tenant business data." />
      <div className="grid cols-4 mb">
        <Stat icon="chart" label="MRR" value={`₹${a.mrr.toLocaleString()}`} delta={`ARR ₹${a.arr.toLocaleString()}`} />
        <Stat icon="card" tint="green" label="Total revenue" value={`₹${a.total_revenue.toLocaleString()}`} />
        <Stat icon="building" tint="blue" label="Tenants" value={a.tenants} delta={`${a.active_tenants} active`} />
        <Stat icon="shield" tint="amber" label="Pending approvals" value={a.pending_approval + a.open_admin_approvals} />
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>Plan mix</h3>
          {Object.entries(a.plan_mix).map(([k, v]) => (
            <div key={k} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span>{k}</span><span className="tag">{v} tenant(s)</span>
            </div>
          ))}
        </div>
        <div className="card">
          <h3>Quick actions</h3>
          <div className="grid" style={{ gap: 10 }}>
            <Link to="/admin/hermes" className="btn">Tune Hermes agent defaults</Link>
            <Link to="/admin/catalog" className="btn">Control catalog (verticals, solutions, packs)</Link>
            <Link to="/admin/tenants" className="btn secondary">Review tenants & onboarding</Link>
            <Link to="/admin/plans" className="btn secondary">Edit plans & feature flags</Link>
            <Link to="/admin/config" className="btn secondary">Publish common configuration</Link>
            <Link to="/admin/releases" className="btn secondary">Manage desktop rollout</Link>
          </div>
        </div>
      </div>
    </>
  )
}
