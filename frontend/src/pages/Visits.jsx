import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Empty, Loading, Modal, PageHead, Pill } from '../components/ui'

export default function Visits() {
  const [visits, setVisits] = useState(null)
  const [skin, setSkin] = useState(null)
  const [outcomeFor, setOutcomeFor] = useState(null)
  const load = () => Promise.all([api.get('/visits'), api.get('/universal/skin')])
    .then(([v, s]) => { setVisits(v); setSkin(s) })
  useEffect(() => { load() }, [])
  if (!visits) return <Loading />
  const v = skin || { appointments: 'Appointments', appointment: 'appointment' }

  const confirm = async (id) => { await api.post(`/visits/${id}/confirm`); load() }
  const fmt = (s) => s ? new Date(s).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'

  return (
    <>
      <PageHead title={v.appointments}
        sub={`Slots from your calendar, confirmed and reminded (T-24h, T-2h) automatically. (Universal engine E3, skinned to ${v.industry || 'your industry'}.)`} />
      {visits.length === 0
        ? <Empty>No visits yet. Offer a site visit from a lead's conversation.</Empty>
        : <div className="card">
            <table>
              <thead><tr><th>Lead</th><th>When</th><th>Reminders</th><th>Status</th><th>Outcome</th><th></th></tr></thead>
              <tbody>
                {visits.map((v) => (
                  <tr key={v.id}>
                    <td><strong>{v.lead}</strong></td>
                    <td>{fmt(v.slot)}</td>
                    <td>{(v.reminders || []).map((r) => <span key={r.when} className="tag" style={{ marginRight: 4 }}>{r.when}</span>)}</td>
                    <td><Pill status={v.status === 'confirmed' ? 'active' : v.status === 'done' ? 'completed' : 'pending'} /></td>
                    <td className="muted" style={{ fontSize: 12 }}>{v.outcome || '—'}</td>
                    <td><div className="row-actions">
                      {v.status === 'offered' && <button className="btn green sm" onClick={() => confirm(v.id)}>Confirm</button>}
                      {v.status !== 'done' && <button className="btn secondary sm" onClick={() => setOutcomeFor(v)}>
                        <Icon name="mic" size={13} /> Capture outcome</button>}
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
      {outcomeFor && <OutcomeModal visit={outcomeFor} onClose={() => setOutcomeFor(null)} onDone={load} />}
    </>
  )
}

function OutcomeModal({ visit, onClose, onDone }) {
  const [text, setText] = useState('')
  const supported = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)
  const dictate = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition; if (!SR) return
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = true
    r.onresult = (e) => { let t = ''; for (const x of e.results) t += x[0].transcript; setText(t) }
    r.start()
  }
  const save = async () => { await api.post(`/visits/${visit.id}/outcome`, { outcome: text }); onDone(); onClose() }
  return (
    <Modal title={`Visit outcome · ${visit.lead}`} onClose={onClose}>
      <p className="muted">Dictate in the car — "Kumar liked B-1204, concerned about east facing, budget stretch 5L."</p>
      <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Visit notes…" />
      <div className="row-actions mt">
        {supported && <button className="btn secondary" onClick={dictate}><Icon name="mic" size={15} /> Dictate</button>}
        <button className="btn" onClick={save} disabled={!text.trim()}>Save → CRM note + next step</button>
      </div>
    </Modal>
  )
}
