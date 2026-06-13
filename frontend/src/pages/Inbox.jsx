import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead, Pill } from '../components/ui'

const CATS = [['', 'All'], ['urgent', 'Urgent'], ['action', 'Action'], ['fyi', 'FYI'], ['spam', 'Spam']]
const TONES = ['formal', 'friendly', 'firm']

export default function Inbox() {
  const [threads, setThreads] = useState(null)
  const [summary, setSummary] = useState(null)
  const [cat, setCat] = useState('')
  const [q, setQ] = useState('')
  const [sel, setSel] = useState(null)
  const [detail, setDetail] = useState(null)
  const [draft, setDraft] = useState(null)
  const [instructions, setInstructions] = useState('')
  const [tone, setTone] = useState('formal')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const catRef = useRef(cat); catRef.current = cat
  const selRef = useRef(sel); selRef.current = sel
  const draftRef = useRef(draft); draftRef.current = draft

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = (c = catRef.current) => Promise.all([
    api.get(`/comms/threads${c ? `?category=${c}` : ''}`).then(setThreads),
    api.get('/comms/summary').then(setSummary).catch(() => {}),
  ]).catch(() => flash('err', 'Could not load the inbox.'))
  useEffect(() => { load(cat) }, [cat])
  const openThread = (id) => { setSel(id); setDraft(null); api.get(`/comms/threads/${id}`).then(setDetail).catch(() => flash('err', 'Could not open the conversation.')) }
  useEffect(() => { if (sel) openThread(sel) }, []) // eslint-disable-line

  const loadDemo = async () => {
    try { const r = await api.post('/comms/demo'); flash('ok', r.message); speak(r.message); await load() }
    catch (e) { flash('err', e?.message || 'Could not load the demo inbox.') }
  }
  const makeDraft = async (tid = sel, instr = instructions, tn = tone) => {
    if (!tid) { flash('err', 'Open a conversation first.'); return null }
    setBusy(true)
    try { const d = await api.post(`/comms/threads/${tid}/draft`, { instructions: instr, tone: tn }); setDraft(d); flash('ok', `Draft ready (${d.engine}). Review and send.`); return d }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not draft a reply.'); return null }
    finally { setBusy(false) }
  }
  const send = async (tid = sel, dr = draft) => {
    if (!dr) { flash('err', 'Nothing to send — draft a reply first.'); return }
    setBusy(true)
    try { const r = await api.post(`/comms/threads/${tid}/send`, { body: dr.body }); flash('ok', r.message); speak(r.message); setDraft(null); setInstructions(''); openThread(tid); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Send failed.') }
    finally { setBusy(false) }
  }
  const recategorize = async (tid, category) => {
    try { const r = await api.patch(`/comms/threads/${tid}`, { category }); flash('ok', r.message); speak(r.message); if (detail && detail.id === tid) setDetail({ ...detail, category }); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not re-triage.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/comms/resolve', { transcript: phrase, thread_id: selRef.current || undefined })
      switch (r.action) {
        case 'demo': await loadDemo(); break
        case 'filter': setCat(r.category); flash('ok', r.message); break
        case 'open': if (r.id) { openThread(r.id); flash('ok', r.message) } break
        case 'draft': if (r.id) { if (r.id !== selRef.current) openThread(r.id); setInstructions(r.instructions); setTone(r.tone); await makeDraft(r.id, r.instructions, r.tone) } break
        case 'send': await send(r.id || selRef.current, draftRef.current); break
        case 'recategorize': if (r.id) await recategorize(r.id, r.category); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__inboxVoice = (t) => { runCommand(t); return true }; return () => { if (window.__inboxVoice) delete window.__inboxVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!threads) return <Loading />
  const shown = threads.filter((t) => !q || `${t.counterpart} ${t.subject}`.toLowerCase().includes(q.toLowerCase()))
  const countFor = (k) => summary ? (k ? summary.by_category[k] || 0 : summary.total) : null
  return (
    <>
      <PageHead title="Communication Hub" sub="Unified inbox with AI triage — Urgent / Action / FYI / Spam.">
        <div className="tabs" style={{ margin: 0, width: 380 }}>
          {CATS.map(([k, l]) => <button key={k} className={cat === k ? 'active' : ''} onClick={() => setCat(k)}>
            {l}{countFor(k) ? ` (${countFor(k)})` : ''}</button>)}
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "show urgent", "open the Acme thread", "draft a reply saying payment Tuesday", "mark this as spam", "send it"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {threads.length === 0 && !cat && (
        <div className="card mb between" style={{ alignItems: 'center' }}>
          <span className="muted" style={{ fontSize: 13 }}>No conversations yet. Connect a channel, or load a sample inbox to try triage.</span>
          <button className="btn sm" onClick={loadDemo}><Icon name="plus" size={14} /> Load demo inbox</button>
        </div>
      )}

      <div className="grid" style={{ gridTemplateColumns: '340px 1fr' }}>
        <div className="card" style={{ padding: 8 }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search conversations…"
            style={{ width: '100%', marginBottom: 6 }} />
          {shown.map((t) => (
            <div key={t.id} className={'thread-item' + (sel === t.id ? ' sel' : '')} onClick={() => openThread(t.id)}>
              <div className="between">
                <strong style={{ fontSize: 13 }}>{t.unread && <span style={{ color: 'var(--primary)' }}>● </span>}{t.counterpart}</strong>
                <Pill status={t.category} />
              </div>
              <div style={{ fontSize: 13, margin: '2px 0' }}>{t.subject}</div>
              <div className="muted" style={{ fontSize: 12 }}>{t.channel} · {t.preview}</div>
            </div>
          ))}
          {shown.length === 0 && <div className="muted" style={{ fontSize: 12, padding: 8 }}>No conversations match.</div>}
        </div>

        <div className="card">
          {!detail && <div className="empty">Select a conversation to triage.</div>}
          {detail && <>
            <div className="between mb">
              <div><h3 style={{ margin: 0 }}>{detail.subject}</h3>
                <div className="muted" style={{ fontSize: 12 }}>{detail.counterpart} · {detail.channel}</div></div>
              <div className="flex" style={{ gap: 6, alignItems: 'center' }}>
                <select value={detail.category} onChange={(e) => recategorize(detail.id, e.target.value)}
                  title="Re-triage this conversation" style={{ fontSize: 12, padding: '4px 6px' }}>
                  {CATS.filter(([k]) => k).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </div>
            </div>
            {detail.messages.map((m, i) => (
              <div key={i} className="card mb" style={{
                background: m.direction === 'in' ? 'var(--bg-2)' : 'var(--panel-2)', padding: 12 }}>
                <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>
                  {m.direction === 'in' ? '⬅ Received' : '➡ Sent'} · {new Date(m.sent_at).toLocaleString()}</div>
                <div style={{ fontSize: 13 }}>{m.body}</div>
              </div>
            ))}

            <h4 className="mt">Voice triage — draft a reply</h4>
            <div className="flex" style={{ gap: 8 }}>
              <input style={{ flex: 1 }} value={instructions} onChange={(e) => setInstructions(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && instructions) makeDraft() }}
                placeholder='e.g. "payment will be released Tuesday"' />
              <select value={tone} onChange={(e) => setTone(e.target.value)} style={{ width: 110 }}>
                {TONES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <button className="btn secondary mt sm" onClick={() => makeDraft()} disabled={!instructions || busy}>
              {busy ? 'Drafting…' : 'Draft reply (agent)'}</button>
            {draft && <div className="card mt" style={{ background: 'var(--bg-2)' }}>
              <div className="muted" style={{ fontSize: 11 }}>Draft ({draft.tone}) — not sent
                {draft.engine && <span className="tag" style={{ marginLeft: 6,
                  color: draft.engine === 'local-llm' ? 'var(--accent)' : 'var(--muted)' }}>
                  🧠 {draft.engine}</span>}</div>
              <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, fontFamily: 'inherit', margin: '8px 0' }}>{draft.body}</pre>
              <div className="row-actions">
                <button className="btn green sm" onClick={() => send()} disabled={busy}>Send</button>
                <button className="btn ghost sm" onClick={() => setDraft(null)} disabled={busy}>Discard</button>
              </div>
            </div>}
          </>}
        </div>
      </div>
    </>
  )
}
