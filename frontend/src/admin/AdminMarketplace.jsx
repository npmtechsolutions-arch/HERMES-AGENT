import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, PageHead, Pill } from '../components/ui'

export default function AdminMarketplace() {
  const [items, setItems] = useState(null)
  const [msg, setMsg] = useState(null)
  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const load = () => api.get('/admin/marketplace').then(setItems).catch(() => flash('err', 'Could not load marketplace.'))
  useEffect(() => { load() }, [])
  if (!items) return <Loading />

  const review = async (id, decision) => {
    if (decision === 'reject' && !window.confirm('Reject / take down this package?')) return
    try { const r = await api.post(`/admin/marketplace/${id}/review?decision=${decision}`); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not review the item.') }
  }

  return (
    <>
      <PageHead title="Marketplace Administration" sub="Publisher queue, package review/signing, takedowns (PA-06)." />
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}
      <div className="card">
        <table>
          <thead><tr><th>Item</th><th>Type</th><th>Publisher</th><th>Installs</th><th>Status</th><th>Review</th></tr></thead>
          <tbody>
            {items.map((m) => (
              <tr key={m.id}>
                <td><strong>{m.name}</strong></td>
                <td><span className="tag">{m.type.replace('_', ' ')}</span></td>
                <td className="muted">{m.publisher}</td>
                <td>{m.installs.toLocaleString()}</td>
                <td><Pill status={m.status} /></td>
                <td>
                  {m.status === 'in_review' && (
                    <div className="row-actions">
                      <button className="btn green sm" onClick={() => review(m.id, 'approve')}>Approve & sign</button>
                      <button className="btn danger sm" onClick={() => review(m.id, 'reject')}>Reject</button>
                    </div>
                  )}
                  {m.status === 'approved' && <button className="btn ghost sm" onClick={() => review(m.id, 'reject')}>Take down</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
