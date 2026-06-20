import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 27 Part 4.4 — every agent action, plain language, with ✅ / ❌ markers.
// Filter by agent and by status; each entry explains "Why?"; failures get Retry.
const MARK = { success: { i: '✅', c: 'var(--green)' }, failed: { i: '❌', c: 'var(--red)' } }

export default function AgentActivity() {
  const [rows, setRows] = useState(null)
  const [agents, setAgents] = useState([])
  const [agent, setAgent] = useState('')
  const [status, setStatus] = useState('')
  const [why, setWhy] = useState(null)

  const load = () => {
    const q = new URLSearchParams()
    if (agent) q.set('agent', agent)
    if (status) q.set('status', status)
    api.get('/agent-activity?' + q.toString()).then((r) => setRows(r.activity)).catch(() => setRows([]))
  }
  useEffect(() => { api.get('/agents').then(setAgents).catch(() => {}) }, [])
  useEffect(() => { load() }, [agent, status])

  const retry = async (a) => {
    // re-issue the same action through the assistant (transient/hard-fail recovery)
    try { await api.post('/assistant', { text: a.summary }); load() } catch {}
  }

  if (!rows) return <Loading />
  return (
    <>
      <PageHead title="Agent Activity" subtitle="What your agents did — successes and failures, in plain words." />
      <div className="flex wrap mb" style={{ gap: 8 }}>
        <select value={agent} onChange={(e) => setAgent(e.target.value)}>
          <option value="">All agents</option>
          {[...new Set(agents.map((a) => a.name))].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <div className="tabs" style={{ margin: 0 }}>
          {[['', 'All'], ['success', '✅ Success'], ['failed', '❌ Failed']].map(([k, l]) => (
            <button key={k} className={status === k ? 'active' : ''} onClick={() => setStatus(k)}>{l}</button>
          ))}
        </div>
      </div>
      <div className="card">
        {rows.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No activity yet — give your assistant something to do.</div>}
        {rows.map((a) => {
          const m = MARK[a.marker] || MARK.success
          return (
            <div key={a.id} style={{ padding: '10px 2px', borderBottom: '1px solid var(--border)' }}>
              <div className="flex between" style={{ alignItems: 'flex-start' }}>
                <div className="flex" style={{ gap: 9, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 14 }}>{m.i}</span>
                  <div>
                    <div style={{ fontSize: 13.5 }}>{a.summary}</div>
                    <div className="muted" style={{ fontSize: 11 }}>
                      <strong>{a.agent}</strong>{a.tool ? ` · ${a.tool}` : ''}{a.at ? ` · ${new Date(a.at).toLocaleString()}` : ''}
                    </div>
                  </div>
                </div>
                <div className="flex" style={{ gap: 6 }}>
                  <button className="btn sm ghost" onClick={() => setWhy(why === a.id ? null : a.id)}>Why?</button>
                  {a.marker === 'failed' && <button className="btn sm" onClick={() => retry(a)}>Retry</button>}
                </div>
              </div>
              {why === a.id && <div className="muted" style={{ fontSize: 12, marginTop: 6, paddingLeft: 23 }}>{a.why}</div>}
            </div>
          )
        })}
      </div>
    </>
  )
}
