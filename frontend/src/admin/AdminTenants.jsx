import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, Modal, PageHead, Pill } from '../components/ui'

export default function AdminTenants() {
  const [tenants, setTenants] = useState(null)
  const [filter, setFilter] = useState('')
  const [search, setSearch] = useState('')

  const load = () => {
    const qs = new URLSearchParams()
    if (filter) qs.set('status', filter)
    if (search) qs.set('search', search)
    return api.get('/admin/tenants?' + qs).then(setTenants)
  }
  useEffect(() => { load() }, [filter])

  const act = async (id, action) => { await api.post(`/admin/tenants/${id}/${action}`); load() }
  const [cert, setCert] = useState(null)
  const offboard = async (id, name) => {
    if (!confirm(`Offboard "${name}"? This runs the deletion saga and issues a certificate. ` +
      `The tenant's local business data stays on their machine.`)) return
    const r = await api.post(`/admin/tenant-offboard/${id}`); setCert(r); load()
  }
  if (!tenants) return <Loading />

  return (
    <>
      <PageHead title="Tenants" sub="Onboarding, lifecycle & support actions.">
        <input style={{ width: 220 }} placeholder="Search company…" value={search}
          onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && load()} />
      </PageHead>
      <div className="tabs mb" style={{ width: 420 }}>
        {['', 'active', 'pending_approval', 'suspended'].map((s) => (
          <button key={s} className={filter === s ? 'active' : ''} onClick={() => setFilter(s)}>
            {s === '' ? 'All' : s.replace('_', ' ')}</button>
        ))}
      </div>

      <div className="card">
        <table>
          <thead><tr><th>Company</th><th>Industry</th><th>Owner</th><th>Plan</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id}>
                <td><strong>{t.company_name}</strong><div className="muted" style={{ fontSize: 11 }}>{t.region}</div></td>
                <td>{t.industry}</td>
                <td className="muted">{t.owner_email}</td>
                <td><span className="tag">{t.plan}</span></td>
                <td><Pill status={t.status} /></td>
                <td>
                  <div className="row-actions">
                    {t.status === 'pending_approval' && <button className="btn green sm" onClick={() => act(t.id, 'approve')}>Approve</button>}
                    {t.status === 'active' && <button className="btn ghost sm" onClick={() => act(t.id, 'suspend')}>Suspend</button>}
                    {t.status === 'suspended' && <button className="btn green sm" onClick={() => act(t.id, 'reactivate')}>Reactivate</button>}
                    {t.status !== 'closed' && <button className="btn danger sm" onClick={() => offboard(t.id, t.company_name)}>Offboard</button>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {tenants.length === 0 && <div className="empty">No tenants match.</div>}
      </div>

      {cert && (
        <Modal title="Deletion Certificate" onClose={() => setCert(null)}>
          <div className="card" style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)' }}>
            <strong style={{ color: 'var(--success-fg)' }}>✓ Offboarding completed (deletion saga)</strong>
          </div>
          <div className="muted mt" style={{ fontSize: 12 }}>{cert.note}</div>
          <h4>Steps executed</h4>
          <div className="flex wrap">{cert.steps.map((s) => <span key={s.system} className="tag">{s.system}</span>)}</div>
          <h4 className="mt">Certificate</h4>
          <div className="card" style={{ background: 'var(--panel-2)', boxShadow: 'none', fontSize: 12, fontFamily: 'monospace' }}>
            <div>tenant: {cert.deletion_certificate.tenant_id} ({cert.deletion_certificate.company})</div>
            <div>issued: {new Date(cert.deletion_certificate.issued_at).toLocaleString()}</div>
            <div>SLA: {cert.deletion_certificate.sla}</div>
            <div style={{ wordBreak: 'break-all', marginTop: 6 }}>hash: {cert.certificate_hash}</div>
          </div>
          <div className="muted mt" style={{ fontSize: 12 }}>GDPR/DPDP Art. 17 evidence — hash-chained into the admin audit.</div>
        </Modal>
      )}
    </>
  )
}
