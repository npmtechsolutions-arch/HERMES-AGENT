import { useEffect, useRef, useState } from 'react'
import { api, IS_DESKTOP } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

export default function SystemHealth() {
  const h = typeof window !== 'undefined' ? window.hermus : null
  const [hw, setHw] = useState(null)        // desktop hardware/services
  const [be, setBe] = useState(null)        // backend /models (web fallback)
  const [at, setAt] = useState(null)
  const timer = useRef(null)

  const refresh = async () => {
    if (h?.systemHealth) { try { setHw(await h.systemHealth()) } catch {} }
    try { setBe(await api.get('/models')) } catch {}
    setAt(new Date())
  }
  useEffect(() => { refresh(); timer.current = setInterval(refresh, 5000); return () => clearInterval(timer.current) }, []) // eslint-disable-line

  if (!hw && !be) return <Loading />
  const online = hw ? hw.services.runtime : be?.online
  const models = hw ? hw.services.models : (be?.models || []).length

  const Service = ({ ok, label, sub }) => (
    <div className="between" style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
      <div><div style={{ fontSize: 13, fontWeight: 600 }}>{label}</div>
        {sub && <div className="muted" style={{ fontSize: 12 }}>{sub}</div>}</div>
      <span className={'pill ' + (ok ? 'st-online' : 'st-error')}><span className="dot" />{ok ? 'healthy' : 'down'}</span>
    </div>
  )
  const Meter = ({ label, used, detail }) => (
    <div style={{ marginBottom: 12 }}>
      <div className="between" style={{ fontSize: 13, marginBottom: 4 }}><span>{label}</span><span className="muted">{detail}</span></div>
      <div className="bar"><span style={{ width: `${used}%`, background: used >= 90 ? 'var(--red)' : used >= 75 ? 'var(--amber)' : undefined }} /></div>
    </div>
  )

  return (
    <>
      <PageHead title="System Health" sub="Live status of this machine and the local HERMUS services — all on-device.">
        <span className="muted" style={{ fontSize: 12 }}>{at ? `updated ${at.toLocaleTimeString()}` : ''}</span>
      </PageHead>

      {/* Services — works in web (backend) and desktop (full) */}
      <div className="grid cols-2 mb">
        <div className="card">
          <h3><Icon name="shield" size={17} /> Services</h3>
          <Service ok={hw ? hw.services.core : true} label="Core service" sub="Local agents, tasks, memory (FastAPI)" />
          <Service ok={online} label="Local AI runtime — Ollama" sub={`${models} model(s) installed`} />
          {hw && <Service ok={hw.services.postgres} label="Database (Postgres)" sub="Encrypted local data store" />}
        </div>

        <div className="card">
          <h3><Icon name="cpu" size={17} /> This machine</h3>
          {!hw && <p className="muted" style={{ fontSize: 13 }}>Live hardware (CPU, memory, disk) is shown in the <strong>HERMUS desktop app</strong>. In the browser, only service status is available.</p>}
          {hw && <>
            <div className="muted mb" style={{ fontSize: 12 }}>{hw.cpuModel || 'CPU'} · {hw.cpus} cores · {hw.platform} ({hw.arch})</div>
            <Meter label="Memory" used={hw.ram.usedPct} detail={`${(hw.ram.totalGB - hw.ram.freeGB).toFixed(1)} / ${hw.ram.totalGB} GB`} />
            {hw.disk && <Meter label="Disk" used={hw.disk.usedPct} detail={`${(hw.disk.totalGB - hw.disk.freeGB).toFixed(0)} / ${hw.disk.totalGB} GB used · ${hw.disk.freeGB} GB free`} />}
            <Meter label="CPU load (1 min avg)" used={Math.min(100, Math.round((hw.loadavg / hw.cpus) * 100))} detail={`${hw.loadavg}`} />
          </>}
        </div>
      </div>

      {hw && <div className="card">
        <h3><Icon name="check" size={17} /> Diagnostics</h3>
        <div className="grid cols-3" style={{ gap: 10 }}>
          <Mini label="App uptime" v={`${hw.appUptimeMin} min`} />
          <Mini label="System uptime" v={`${hw.uptimeMin} min`} />
          <Mini label="Models installed" v={hw.services.models} />
          <Mini label="Free memory" v={`${hw.ram.freeGB} GB`} />
          {hw.disk && <Mini label="Free disk" v={`${hw.disk.freeGB} GB`} />}
          <Mini label="CPU cores" v={hw.cpus} />
        </div>
        <p className="muted mt" style={{ fontSize: 12 }}>Manage the runtime & models in <strong>Runtime &amp; Models</strong>. Everything here runs locally — nothing is sent to the cloud.</p>
      </div>}
    </>
  )
}

function Mini({ label, v }) {
  return <div className="stat" style={{ padding: 10, display: 'block' }}>
    <div className="label">{label}</div><div className="value" style={{ fontSize: 18 }}>{v}</div></div>
}
