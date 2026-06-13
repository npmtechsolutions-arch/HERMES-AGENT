import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, PageHead, Pill } from '../components/ui'

export default function AdminReleases() {
  const [rels, setRels] = useState(null)
  const [msg, setMsg] = useState(null)
  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const load = () => api.get('/admin/releases').then(setRels).catch(() => flash('err', 'Could not load releases.'))
  useEffect(() => { load() }, [])
  if (!rels) return <Loading />

  const setRollout = async (id, pct) => {
    try { const r = await api.patch(`/admin/releases/${id}/rollout`, { rollout_percent: pct }); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not set rollout.') }
  }

  return (
    <>
      <PageHead title="Desktop Releases" sub="Staged rollout %, crash-gate auto-pause (PA-05), force-update floor." />
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}
      <div className="grid">
        {rels.map((r) => (
          <div className="card" key={r.id}>
            <div className="between mb">
              <div><h3 style={{ margin: 0 }}>v{r.version} <span className="tag">{r.channel}</span></h3>
                <div className="muted" style={{ fontSize: 12 }}>{r.notes_md}</div></div>
              <Pill status={r.state} />
            </div>
            <div className="between" style={{ fontSize: 13, marginBottom: 6 }}>
              <span>Rollout</span><span className="muted">{r.rollout_percent}%</span></div>
            <div className="bar mb"><span style={{ width: `${r.rollout_percent}%` }} /></div>
            <div className="row-actions">
              {[0, 25, 50, 100].map((p) => (
                <button key={p} className="btn secondary sm" onClick={() => setRollout(r.id, p)}>{p}%</button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
