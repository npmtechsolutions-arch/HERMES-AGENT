import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useMode } from '../mode'
import Icon from '../components/Icon'
import { Empty, Loading, PageHead } from '../components/ui'

export default function Rehearsal() {
  const [leads, setLeads] = useState(null)
  const [summary, setSummary] = useState(null)
  const mode = useMode()
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const [busy, setBusy] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([
    api.get('/leads').then((d) => setLeads(d.filter((l) => l.source === 'rehearsal'))),
    api.get('/rehearsal/summary').then(setSummary).catch(() => {}),
  ]).catch(() => flash('err', 'Could not load the rehearsal.'))
  useEffect(() => { load() }, [])

  const act = async (fn, okSpeak = true) => {
    setBusy(true)
    try { const r = await fn(); if (r?.message) { flash('ok', r.message); if (okSpeak) speak(r.message) }; await load(); return r }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Something went wrong.') }
    finally { setBusy(false) }
  }
  const start = () => act(() => api.post('/rehearsal/start'))
  const finish = () => act(() => api.post('/rehearsal/finish'))
  const reset = () => { if (window.confirm('Clear the simulated cast without going live?')) act(() => api.post('/rehearsal/reset')) }
  const qualifyAll = () => act(() => api.post('/rehearsal/qualify_all'))
  const playAll = () => act(() => api.post('/rehearsal/play_all'))

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/rehearsal/resolve', { transcript: phrase })
      switch (r.action) {
        case 'start': await start(); break
        case 'finish': await finish(); break
        case 'reset': if (window.confirm('Clear the simulated cast without going live?')) await act(() => api.post('/rehearsal/reset')); break
        case 'qualify_all': await qualifyAll(); break
        case 'play_all': await playAll(); break
        case 'qualify': if (r.id) await act(() => api.post(`/leads/${r.id}/qualify`).then((x) => ({ ...x, message: `Agent qualified ${r.name} — ${x.status === 'held' ? 'held by validators (no real egress)' : x.status}.` }))); break
        case 'play': if (r.id) await act(() => api.post(`/rehearsal/${r.id}/play`)); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__rehearsalVoice = (t) => { runCommand(t); return true }; return () => { if (window.__rehearsalVoice) delete window.__rehearsalVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!leads) return <Loading />
  return (
    <>
      <PageHead title="Rehearsal Mode"
        sub="Watch your AI team practice on simulated contacts — nothing real is ever sent.">
        {leads.length === 0
          ? <button className="btn" onClick={start} disabled={busy}><Icon name="play" size={16} /> Start rehearsal</button>
          : <div className="flex" style={{ gap: 8 }}>
              <button className="btn secondary" onClick={qualifyAll} disabled={busy}>Qualify all</button>
              <button className="btn secondary" onClick={playAll} disabled={busy}>Play all</button>
              <button className="btn ghost" onClick={reset} disabled={busy}>Reset</button>
              <button className="btn green" onClick={finish} disabled={busy}><Icon name="check" size={16} /> Go live</button>
            </div>}
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "start rehearsal", "qualify everyone", "play the eager contact", "go live"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="card mb" style={{ background: 'var(--success-bg)', border: '1px solid var(--success-border)' }}>
        <div className="flex"><Icon name="shield" size={16} style={{ color: 'var(--success-fg)' }} />
          <strong style={{ color: 'var(--success-fg)' }}>Safe sandbox</strong></div>
        <div style={{ fontSize: 13, marginTop: 4 }}>The channel layer is swapped for a simulator — validators verify
          <strong> zero real egress</strong>. {mode === 'advanced' && 'Rehearsal transcripts seed the golden-task eval suite on "Go live".'}</div>
        {summary && summary.cast > 0 && (
          <div className="flex mt" style={{ gap: 16, fontSize: 12.5 }}>
            <span><strong>{summary.cast}</strong> contacts</span>
            <span><strong>{summary.agent_messages}</strong> agent messages</span>
            <span style={{ color: 'var(--amber)' }}><strong>{summary.held}</strong> held by validators</span>
            <span style={{ color: 'var(--success-fg)' }}><strong>{summary.real_egress}</strong> real sends ✓</span>
          </div>
        )}
      </div>

      {leads.length === 0
        ? <Empty>Start a rehearsal to meet your simulated cast (eager, rude, haggling, silent, off-topic) and let your agents practice.</Empty>
        : <div className="grid cols-2">
            {leads.map((l) => <RehearsalCard key={l.id} lead={l} mode={mode} onChange={load} onFlash={flash} onSpeak={speak} />)}
          </div>}
    </>
  )
}

function RehearsalCard({ lead, mode, onChange, onFlash, onSpeak }) {
  const [detail, setDetail] = useState(null)
  const [busy, setBusy] = useState(false)
  const load = () => api.get(`/leads/${lead.id}`).then(setDetail).catch(() => {})
  useEffect(() => { load() }, [lead.id])

  const qualify = async () => {
    setBusy(true)
    try { const r = await api.post(`/leads/${lead.id}/qualify`); const m = `Agent qualified ${lead.name} — ${r.status === 'held' ? 'held by validators (no real egress)' : r.status}.`; onFlash('ok', m); onSpeak(m); await load(); onChange() }
    catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Qualify failed.') }
    finally { setBusy(false) }
  }
  const play = async () => {
    setBusy(true)
    try { const r = await api.post(`/rehearsal/${lead.id}/play`); onFlash('ok', r.message || `${lead.name} replied.`); await load(); onChange() }
    catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not play this contact.') }
    finally { setBusy(false) }
  }

  return (
    <div className="card">
      <div className="between mb">
        <h3 style={{ margin: 0 }}>{lead.name}</h3>
        <span className="tag" style={{ color: lead.score === 'hot' ? 'var(--red)' : 'var(--amber)' }}>● {lead.score}</span>
      </div>
      <div className="card" style={{ background: 'var(--panel-2)', boxShadow: 'none', maxHeight: 180, overflowY: 'auto', padding: 12 }}>
        {(detail?.interactions || []).map((m) => (
          <div key={m.id} style={{ display: 'flex', justifyContent: m.direction === 'out' ? 'flex-end' : 'flex-start', marginBottom: 8 }}>
            <span style={{ padding: '6px 11px', borderRadius: 11, fontSize: 12.5, maxWidth: '85%',
              background: m.direction === 'out' ? (m.status === 'held' ? 'var(--danger-bg)' : 'var(--grad)') : 'var(--panel)',
              color: m.direction === 'out' && m.status !== 'held' ? '#fff' : 'var(--text)',
              border: m.direction === 'out' && m.status !== 'held' ? 'none' : '1px solid var(--border)' }}>
              {m.body}{m.status === 'held' && ' 🚫'}
            </span>
          </div>
        ))}
        {!detail?.interactions?.length && <div className="muted" style={{ fontSize: 12 }}>No messages yet.</div>}
      </div>
      <div className="row-actions mt">
        <button className="btn sm" onClick={qualify} disabled={busy}>Agent: qualify</button>
        <button className="btn secondary sm" onClick={play} disabled={busy}>Play this contact</button>
        {mode === 'advanced' && <span className="tag" style={{ fontSize: 10 }}>channel: rehearsal-sim</span>}
      </div>
    </div>
  )
}
