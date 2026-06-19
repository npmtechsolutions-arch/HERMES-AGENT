import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

// Doc 21 Part 7.1 / Part 4.2 — the plain-language "what happened & why" stream
// (a simplified Glass-Box). Reads the local audit chain and humanizes it.
const VERB = {
  'memory.ingest': ['Saved to your memory', 'brain'],
  'memory.forget': ['Forgot a memory', 'brain'],
  'task.create': ['Created a task', 'tasks'],
  'task.execute': ['Ran a task', 'zap'],
  'task.status_changed': ['Updated a task', 'tasks'],
  'comms.send': ['Sent a reply', 'send'],
  'edition.activate': ['Switched product', 'layers'],
  'tier.set': ['Changed plan', 'card'],
  'auth.login': ['Signed in', 'shield'],
  'vertical.deploy': ['Set up a workspace', 'sparkles'],
  'recipe.changed': ['Changed an automation', 'zap'],
  'workflow.changed': ['Updated a workflow', 'workflow'],
  'backup.run': ['Backed up your data', 'shield'],
}
function humanize(a) {
  if (VERB[a.action]) return VERB[a.action]
  const t = (a.action || '').replace(/[._]/g, ' ')
  return [t.charAt(0).toUpperCase() + t.slice(1), 'check']
}
const ago = (iso) => {
  if (!iso) return ''
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export default function Activity() {
  const [rows, setRows] = useState(null)
  useEffect(() => { api.get('/audit/chain?limit=80').then((d) => setRows(Array.isArray(d) ? d : [])).catch(() => setRows([])) }, [])
  if (!rows) return <Loading />

  return (
    <>
      <PageHead title="Activity" sub="Everything your assistant did — in plain language, with the why. All of it stays on your machine." />
      <div className="card">
        {rows.length === 0 && <div className="muted" style={{ fontSize: 13, padding: 10 }}>Nothing yet — your assistant's actions will show up here.</div>}
        {rows.map((r) => {
          const [label, icon] = humanize(r)
          return (
            <div key={r.id} className="flex" style={{ gap: 12, padding: '10px 0', borderBottom: '1px solid var(--border)', alignItems: 'center' }}>
              <span className="stat-ico" style={{ width: 30, height: 30, borderRadius: 9, background: 'var(--panel-2)', flex: '0 0 auto' }}>
                <Icon name={icon} size={15} /></span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{label}{r.target ? <span className="muted" style={{ fontWeight: 400 }}> · {r.target}</span> : ''}</div>
                <div className="muted" style={{ fontSize: 11 }}>{(r.actor || '').replace('user:', 'you · ').replace('agent:', '')}</div>
              </div>
              <span className="muted" style={{ fontSize: 11, flex: '0 0 auto' }}>{ago(r.created_at || r.ts)}</span>
            </div>
          )
        })}
      </div>
    </>
  )
}
