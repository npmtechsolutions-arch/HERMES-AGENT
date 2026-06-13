import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Empty, Loading, Modal, PageHead, Pill } from '../components/ui'

export default function Approvals() {
  const [items, setItems] = useState(null)
  const [filter, setFilter] = useState('pending')
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const [rejecting, setRejecting] = useState(null)   // approval being rejected (reason modal)
  const [busy, setBusy] = useState(false)
  const recogRef = useRef(null)
  const filterRef = useRef(filter)
  filterRef.current = filter

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = (f = filterRef.current) => api.get(`/approvals?state=${f}`).then(setItems).catch(() => flash('err', 'Could not load approvals.'))
  useEffect(() => { load(filter) }, [filter])

  const decide = async (a, decision, reason = '') => {
    setBusy(true)
    try { const r = await api.post(`/approvals/${a.id}/decide`, { decision, reason }); flash('ok', r.message); speak(r.message); await load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not record the decision.') }
    finally { setBusy(false) }
  }
  const decideAll = async (decision) => {
    if (!window.confirm(`${decision === 'approve' ? 'Approve' : 'Reject'} ALL pending approvals?`)) return
    setBusy(true)
    try { const r = await api.post('/approvals/decide_all', { decision }); flash('ok', r.message); speak(r.message); await load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Bulk decision failed.') }
    finally { setBusy(false) }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/approvals/resolve', { transcript: phrase })
      const a = r.id ? (items || []).find((x) => x.id === r.id) : null
      switch (r.action) {
        case 'filter': setFilter(r.state); flash('ok', r.message); break
        case 'approve': if (a || r.id) await decide(a || { id: r.id }, 'approve'); break
        case 'reject': if (a || r.id) await decide(a || { id: r.id }, 'reject', r.reason || ''); break
        case 'approve_all': await decideAll('approve'); break
        case 'reject_all': await decideAll('reject'); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__approvalsVoice = (t) => { runCommand(t); return true }; return () => { if (window.__approvalsVoice) delete window.__approvalsVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!items) return <Loading />
  const pendingCount = filter === 'pending' ? items.length : null
  return (
    <>
      <PageHead title="Approvals Inbox"
        sub="Multi-tier chain: Specialist → Manager → CEO Agent → Human (AC-01..12).">
        <div className="tabs" style={{ margin: 0, width: 280 }}>
          {['pending', 'approved', 'rejected'].map((s) => (
            <button key={s} className={filter === s ? 'active' : ''} onClick={() => setFilter(s)}>{s}</button>
          ))}
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "approve the vendor payment", "reject the first one because risky", "approve everything", "show approved"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {filter === 'pending' && items.length > 0 && (
        <div className="card mb between" style={{ alignItems: 'center' }}>
          <span className="muted" style={{ fontSize: 13 }}>{items.length} pending approval{items.length > 1 ? 's' : ''} awaiting your decision.</span>
          <div className="row-actions">
            <button className="btn green sm" onClick={() => decideAll('approve')} disabled={busy}>✓ Approve all</button>
            <button className="btn danger sm" onClick={() => decideAll('reject')} disabled={busy}>✕ Reject all</button>
          </div>
        </div>
      )}

      {items.length === 0 && <Empty>Nothing in “{filter}”.</Empty>}
      <div className="grid">
        {items.map((a) => (
          <div className="card" key={a.id}>
            <div className="between mb">
              <div>
                <h3 style={{ margin: 0 }}>{a.summary}</h3>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                  Requested by {a.requester_agent_id || 'an agent'} · Tier reached: <strong>{a.current_tier}</strong>
                  {' · '}Rule <span className="tag">{a.rule_id}</span>
                  {a.payload?.amount && <> · 💰 ₹{a.payload.amount.toLocaleString()}</>}
                </div>
              </div>
              <Pill status={a.state} />
            </div>
            {a.chain?.length > 0 && (
              <div className="card" style={{ background: 'var(--bg-2)', padding: 12 }}>
                {a.chain.map((c, i) => (
                  <div key={i} style={{ fontSize: 12 }} className="muted">
                    {c.tier} · {c.actor} → <strong style={{ color: 'var(--text)' }}>{c.decision}</strong>
                    {c.reason && ` (${c.reason})`}{c.batch && ' · batch'}
                  </div>
                ))}
              </div>
            )}
            {a.state === 'pending' && (
              <div className="row-actions mt">
                <button className="btn green" onClick={() => decide(a, 'approve')} disabled={busy}>✓ Approve</button>
                <button className="btn danger" onClick={() => setRejecting(a)} disabled={busy}>✕ Reject</button>
              </div>
            )}
          </div>
        ))}
      </div>

      {rejecting && <RejectModal approval={rejecting} onClose={() => setRejecting(null)}
        onConfirm={(reason) => { const a = rejecting; setRejecting(null); decide(a, 'reject', reason) }} />}
    </>
  )
}

function RejectModal({ approval, onClose, onConfirm }) {
  const [reason, setReason] = useState('')
  return (
    <Modal title="Reject approval" onClose={onClose}>
      <p className="muted" style={{ fontSize: 13 }}>“{approval.summary}”</p>
      <div className="field">
        <label>Reason (recorded in the audit chain)</label>
        <textarea rows={3} autoFocus value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Over budget — re-quote first." />
      </div>
      <div className="row-actions mt">
        <button className="btn danger" onClick={() => onConfirm(reason.trim())}>✕ Confirm reject</button>
        <button className="btn secondary" onClick={onClose}>Cancel</button>
      </div>
    </Modal>
  )
}
