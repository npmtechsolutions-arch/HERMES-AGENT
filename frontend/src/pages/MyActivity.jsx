import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 27 Part 6 — what the USER did (distinct from agent activity): commands
// issued, decisions made, agents created. For "what did I ask it last week?"
const KIND_ICON = { Asked: 'mic', Decided: 'check', 'Created an agent': 'plus', 'Edited an agent': 'settings' }

export default function MyActivity() {
  const [rows, setRows] = useState(null)
  const [q, setQ] = useState('')
  useEffect(() => { api.get('/my-activity').then((r) => setRows(r.activity)).catch(() => setRows([])) }, [])
  if (!rows) return <Loading />
  const filtered = rows.filter((r) => !q || `${r.kind} ${r.detail}`.toLowerCase().includes(q.toLowerCase()))

  return (
    <>
      <PageHead title="My Activity" subtitle="Everything you've asked and decided — private, on your machine." />
      <input className="mb" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search your activity…" style={{ width: '100%' }} />
      <div className="card">
        {filtered.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Nothing yet — your commands and decisions will appear here.</div>}
        {filtered.map((r) => (
          <div key={r.id} className="flex" style={{ gap: 10, padding: '9px 2px', borderBottom: '1px solid var(--border)', alignItems: 'flex-start' }}>
            <Icon name={KIND_ICON[r.kind] || 'scroll'} size={15} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13 }}><strong>{r.kind}</strong>{r.detail ? <> — {r.detail}</> : ''}</div>
              <div className="muted" style={{ fontSize: 11 }}>{r.at ? new Date(r.at).toLocaleString() : ''}{r.tool ? ` · ${r.tool}` : ''}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}
