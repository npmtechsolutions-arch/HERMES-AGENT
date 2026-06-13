import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead, Pill } from '../components/ui'

// Desktop installers, hosted as GitHub Release assets (tag v1.0.0).
const REL = 'https://github.com/npmtechsolutions-arch/HERMES-AGENT/releases/download/v1.0.0'
const DL = {
  win: `${REL}/HERMUS-Setup-1.0.0.exe`,
  mac: `${REL}/HERMUS-1.0.0.dmg`,
  linux: `${REL}/HERMUS-1.0.0.AppImage`,
  deb: `${REL}/hermus-desktop_1.0.0_amd64.deb`,
}

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
        <p className="muted">Install the HERMUS desktop app (Electron). It runs the AI runtime locally and connects to your HERMUS account.</p>
        <div className="row-actions">
          <a className="btn secondary" href={DL.win} download><Icon name="download" size={15} /> Windows (.exe)</a>
          <a className="btn secondary" href={DL.mac} download><Icon name="download" size={15} /> macOS (.dmg)</a>
          <a className="btn secondary" href={DL.linux} download><Icon name="download" size={15} /> Linux (.AppImage)</a>
          <a className="btn ghost" href={DL.deb} download><Icon name="download" size={15} /> Linux (.deb)</a>
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          After installing, sign in with your account. On first run it installs the local AI models (one-time download).
        </p>
      </div>
    </>
  )
}
