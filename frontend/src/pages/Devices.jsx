import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead, Pill } from '../components/ui'

export default function Devices() {
  const [devices, setDevices] = useState(null)
  const load = () => api.get('/devices').then(setDevices)
  useEffect(() => { load() }, [])
  if (!devices) return <Loading />

  const deactivate = async (id) => { await api.del(`/devices/${id}`); load() }

  return (
    <>
      <PageHead title="Devices" sub="Activated desktop machines (OAuth device flow). Deactivate to free a slot." />
      <div className="card">
        <table>
          <thead><tr><th>Device</th><th>OS</th><th>App version</th><th>Last seen</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {devices.map((d) => (
              <tr key={d.id}>
                <td><strong>{d.name}</strong></td>
                <td>{d.os}</td>
                <td>{d.app_version}</td>
                <td className="muted">{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : '—'}</td>
                <td><Pill status={d.status} /></td>
                <td>{d.status === 'active' &&
                  <button className="btn ghost sm" onClick={() => deactivate(d.id)}>Deactivate</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {devices.length === 0 && <div className="empty">No devices activated yet.</div>}
      </div>
      <div className="card mt">
        <h3>Download desktop app</h3>
        <p className="muted">Install the local Core Service (Electron). All business data stays on your machine.</p>
        <div className="row-actions">
          <button className="btn secondary"><Icon name="download" size={15} /> Windows</button>
          <button className="btn secondary"><Icon name="download" size={15} /> macOS</button>
          <button className="btn secondary"><Icon name="download" size={15} /> Linux</button>
        </div>
      </div>
    </>
  )
}
