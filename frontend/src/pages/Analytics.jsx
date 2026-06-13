import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead, Stat } from '../components/ui'

const SUGGESTIONS = [
  'How many tasks did we complete?', 'How many hours saved?',
  'How many approvals are pending?', 'How many leads do we have?',
]

export default function Analytics() {
  const [s, setS] = useState(null)
  const [q, setQ] = useState('')
  const [ans, setAns] = useState(null)
  const [msg, setMsg] = useState(null)
  const [listening, setListening] = useState(false)
  const [busy, setBusy] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = (announce) => api.get('/analytics/summary').then((d) => { setS(d); if (announce) flash('ok', 'Metrics refreshed.') }).catch(() => flash('err', 'Could not load analytics.'))
  useEffect(() => { load() }, [])

  const ask = async (question = q) => {
    const term = (question || '').trim()
    if (!term) { flash('err', 'Type or say a question.'); return }
    setBusy(true)
    try { const r = await api.post('/analytics/query', { question: term }); setAns(r); flash('ok', r.answer); speak(r.answer) }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not answer that.') }
    finally { setBusy(false) }
  }
  const exportReport = async () => {
    try {
      const r = await api.post('/analytics/export')
      const blob = new Blob([JSON.stringify(r.report, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = r.filename || 'analytics-report.json'
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url)
      flash('ok', r.message); speak(r.message)
    } catch (e) { flash('err', e?.message || 'Could not export the report.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? q).trim()
    if (!phrase) return
    try {
      const r = await api.post('/analytics/resolve', { transcript: phrase })
      switch (r.action) {
        case 'ask': setQ(r.question); await ask(r.question); break
        case 'export': await exportReport(); break
        case 'refresh': await load(true); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__analyticsVoice = (t) => { runCommand(t); return true }; return () => { if (window.__analyticsVoice) delete window.__analyticsVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type your question instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setQ(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!s) return <Loading />
  const maxVal = Math.max(1, ...Object.values(s.tasks_by_status))

  return (
    <>
      <PageHead title="Analytics" sub="Productivity, automation value, and voice-queryable insights (FR-A2).">
        <div className="flex" style={{ gap: 8 }}>
          <button className="btn secondary sm" onClick={() => load(true)}><Icon name="refresh" size={14} /> Refresh</button>
          <button className="btn sm" onClick={exportReport}><Icon name="download" size={14} /> Export</button>
        </div>
      </PageHead>

      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="grid cols-4 mb">
        <Stat icon="users" label="Active agents" value={s.agents} />
        <Stat icon="tasks" tint="blue" label="Tasks completed" value={s.tasks_completed} delta={`${s.success_rate}% success`} />
        <Stat icon="clock" tint="green" label="Hours saved" value={s.hours_saved} />
        <Stat icon="card" tint="amber" label="Cost savings" value={`₹${s.cost_savings_inr.toLocaleString()}`} />
        <Stat icon="shield" label="Pending approvals" value={s.pending_approvals} />
        <Stat icon="users" tint="blue" label="Leads" value={s.leads_total} />
        <Stat icon="workflow" tint="green" label="Active workflows" value={s.active_workflows} />
        <Stat icon="tasks" label="Tasks total" value={s.tasks_total} />
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3>Tasks by status</h3>
          {Object.entries(s.tasks_by_status).map(([k, v]) => (
            <div key={k} style={{ marginBottom: 10 }}>
              <div className="between" style={{ fontSize: 13, marginBottom: 4 }}>
                <span style={{ textTransform: 'capitalize' }}>{k}</span><span className="muted">{v}</span></div>
              <div className="bar"><span style={{ width: `${(v / maxVal) * 100}%` }} /></div>
            </div>
          ))}
          {Object.keys(s.tasks_by_status).length === 0 && <div className="muted" style={{ fontSize: 13 }}>No tasks yet.</div>}
        </div>

        <div className="card">
          <h3><Icon name="mic" size={17} /> Voice-queryable analytics</h3>
          <p className="muted" style={{ fontSize: 13 }}>Ask a question, or say "export the report" / "refresh".</p>
          <div className="flex" style={{ gap: 8 }}>
            <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a question"
              onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
              <Icon name="mic" size={18} /></button>
            <input style={{ flex: 1 }} value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runCommand()}
              placeholder={listening ? 'Listening…' : 'Ask a question…'} />
            <button className="btn" onClick={() => runCommand()} disabled={!q.trim() || busy}>{busy ? '…' : 'Ask'}</button>
          </div>
          <div className="flex wrap mt" style={{ gap: 5 }}>
            {SUGGESTIONS.map((sg) => (
              <button key={sg} type="button" className="tag" style={{ cursor: 'pointer' }}
                onClick={() => { setQ(sg); ask(sg) }}>{sg}</button>))}
          </div>
          {ans && <div className="card mt" style={{ background: 'var(--bg-2)' }}>
            <div className="between">
              <div className="muted" style={{ fontSize: 12 }}>You asked: {ans.question}</div>
              {ans.engine && <span className="tag" style={{
                color: ans.engine === 'local-llm' ? 'var(--accent)' : 'var(--muted)' }}>🧠 {ans.engine}</span>}
            </div>
            <div style={{ fontSize: 16, marginTop: 6 }}>🔊 {ans.answer}</div>
          </div>}
        </div>
      </div>
    </>
  )
}
