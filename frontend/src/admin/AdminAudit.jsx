import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, PageHead } from '../components/ui'

export default function AdminAudit() {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.get('/admin/audit?limit=150').then(setRows) }, [])
  if (!rows) return <Loading />

  return (
    <>
      <PageHead title="Audit Log" sub="Append-only trail across both planes (cloud + local)." />
      <div className="card">
        <table>
          <thead><tr><th>Time</th><th>Plane</th><th>Actor</th><th>Action</th><th>Target</th><th>Meta</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="muted" style={{ whiteSpace: 'nowrap' }}>{new Date(r.at).toLocaleString()}</td>
                <td><span className="tag">{r.plane}</span></td>
                <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{r.actor}</td>
                <td><strong>{r.action}</strong></td>
                <td className="muted" style={{ fontFamily: 'monospace', fontSize: 12 }}>{r.target || '—'}</td>
                <td className="muted" style={{ fontSize: 11 }}>{r.meta && Object.keys(r.meta).length ? JSON.stringify(r.meta) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
