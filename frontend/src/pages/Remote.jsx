import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Empty, Loading, Modal, PageHead, Pill } from '../components/ui'

const TYPES = [['whatsapp', 'WhatsApp'], ['telegram', 'Telegram'], ['signal', 'Signal'], ['email', 'Email']]
const ALL_SCOPES = ['query', 'approve', 'briefing']

export default function Remote() {
  const [channels, setChannels] = useState(null)
  const [history, setHistory] = useState([])
  const [pair, setPair] = useState(null)        // {type} seed or true
  const [tryFor, setTryFor] = useState(null)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const chRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([api.get('/remote/channels'), api.get('/remote/commands')])
    .then(([c, h]) => { setChannels(c); chRef.current = c; setHistory(h) })
    .catch(() => flash('err', 'Could not load remote channels.'))
  useEffect(() => { load() }, [])

  const revoke = async (c) => {
    if (!window.confirm(`Revoke remote access for ${c.label}?`)) return
    try { const r = await api.del(`/remote/channels/${c.id}`); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not revoke.') }
  }
  const toggleScope = async (c, scope) => {
    const next = (c.scopes || []).includes(scope) ? c.scopes.filter((s) => s !== scope) : [...(c.scopes || []), scope]
    try { const r = await api.patch(`/remote/channels/${c.id}`, { scopes: next }); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not update scopes.') }
  }
  const setScopes = async (c, scopes) => {
    try { const r = await api.patch(`/remote/channels/${c.id}`, { scopes }); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not update scopes.') }
  }
  const runRemote = async (c, message) => {
    try { const r = await api.post('/remote/command', { channel_id: c.id, sender: (c.sender_allowlist || ['me'])[0], message })
      flash(r.allowed ? 'ok' : 'err', `${c.type}: ${r.response}`); speak(r.response); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Command failed.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/remote/resolve', { transcript: phrase })
      const find = (id) => (chRef.current || []).find((x) => x.id === id)
      switch (r.action) {
        case 'pair': setPair({ type: r.type }); flash('ok', r.message); break
        case 'pair_open': setPair(true); break
        case 'revoke': { const c = find(r.id); if (c) await revoke(c) } break
        case 'scope': { const c = find(r.id); if (c) await setScopes(c, r.scopes) } break
        case 'command': { const c = find(r.id); if (c) await runRemote(c, r.message_text) } break
        case 'history': document.getElementById('cmd-history')?.scrollIntoView({ behavior: 'smooth' }); flash('ok', r.message); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__remoteVoice = (t) => { runCommand(t); return true }; return () => { if (window.__remoteVoice) delete window.__remoteVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!channels) return <Loading />
  return (
    <>
      <PageHead title="Remote Access"
        sub="Command your workforce from WhatsApp / Telegram anywhere — scoped & audited (SC-11).">
        <button className="btn" onClick={() => setPair(true)}><Icon name="link" size={16} /> Pair a channel</button>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "pair a telegram channel", "ask whatsapp what\'s pending", "remove approve from telegram", "revoke whatsapp"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', alignItems: 'start' }}>
        <div>
          <div className="flex mb"><Icon name="chat" size={16} /><strong>Paired channels</strong></div>
          {channels.length === 0 && <Empty>No channels paired. Pair WhatsApp or Telegram to command remotely.</Empty>}
          {channels.map((c) => (
            <div className="card mb" key={c.id}>
              <div className="between">
                <div className="flex">
                  <div className="ix" style={{ width: 38, height: 38, borderRadius: 11, background: 'var(--grad)',
                    color: '#fff', display: 'grid', placeItems: 'center' }}><Icon name="chat" size={19} /></div>
                  <div><div style={{ fontWeight: 600 }}>{c.label}</div>
                    <div className="muted" style={{ fontSize: 12 }}>{c.type} · {(c.sender_allowlist || []).join(', ') || 'no sender yet'}</div></div>
                </div>
                <Pill status={c.status === 'paired' ? 'active' : 'pending'} />
              </div>
              {c.status === 'paired' && (
                <div className="flex wrap mt" style={{ fontSize: 12, gap: 6 }}>
                  <span className="muted" style={{ fontSize: 11 }}>Scopes:</span>
                  {ALL_SCOPES.map((s) => {
                    const on = (c.scopes || []).includes(s)
                    return <button key={s} className="tag" title={on ? 'Click to remove' : 'Click to grant'}
                      style={{ cursor: 'pointer', opacity: on ? 1 : 0.4, borderColor: on ? 'var(--green)' : 'var(--border)' }}
                      onClick={() => toggleScope(c, s)}>{on ? '✓ ' : '+ '}{s}</button>
                  })}
                </div>
              )}
              {c.status === 'pending' && c.pairing_code &&
                <div className="card mt" style={{ background: 'var(--grad-soft)', boxShadow: 'none' }}>
                  Pairing code: <strong style={{ fontSize: 18, letterSpacing: 2 }}>{c.pairing_code}</strong>
                  <div className="muted" style={{ fontSize: 12 }}>Send this from your phone to finish pairing.</div>
                </div>}
              <div className="row-actions mt">
                {c.status === 'paired' && <button className="btn secondary sm" onClick={() => setTryFor(c)}>
                  <Icon name="send" size={13} /> Try a command</button>}
                <button className="btn ghost sm" onClick={() => revoke(c)}>Revoke</button>
              </div>
            </div>
          ))}

          <div className="card" style={{ background: 'var(--panel-2)', boxShadow: 'none' }}>
            <div className="flex" style={{ fontSize: 13 }}><Icon name="shield" size={15} style={{ color: 'var(--green)' }} />
              <strong>Scoped & safe (SC-11)</strong></div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>
              Remote channels can query status, get briefings, and approve/reject — but never touch the vault,
              change permissions, or run destructive ops. The desktop stays the brain; channels are just I/O.</div>
          </div>
        </div>

        <div id="cmd-history">
          <div className="flex mb"><Icon name="scroll" size={16} /><strong>Command history</strong></div>
          {history.length === 0 && <Empty>No remote commands yet.</Empty>}
          {history.map((h) => (
            <div className="card mb" key={h.id} style={{ padding: 14 }}>
              <div className="between">
                <span className="tag">{h.channel} · {h.sender}</span>
                <span className="tag" style={{ color: h.allowed ? 'var(--green)' : 'var(--red)' }}>
                  {h.intent}{h.allowed ? '' : ' · blocked'}</span>
              </div>
              <div style={{ fontSize: 13, margin: '6px 0' }}>“{h.message}”</div>
              <div className="muted" style={{ fontSize: 12.5 }}>↳ {h.response}</div>
            </div>
          ))}
        </div>
      </div>

      {pair && <PairModal seedType={pair?.type} onClose={() => setPair(null)} onDone={load} onFlash={flash} onSpeak={speak} />}
      {tryFor && <TryModal channel={tryFor} onClose={() => setTryFor(null)} onDone={load} />}
    </>
  )
}

function PairModal({ seedType, onClose, onDone, onFlash, onSpeak }) {
  const [type, setType] = useState(seedType || 'whatsapp')
  const [created, setCreated] = useState(null)
  const [sender, setSender] = useState('')
  const creating = useRef(false)
  const create = async () => {
    if (creating.current) return
    creating.current = true
    try { const r = await api.post('/remote/channels', { type, label: `My ${type}` }); setCreated(r); onFlash('ok', r.message); onSpeak(r.message); onDone() }
    catch (e) { creating.current = false; onFlash('err', e?.detail?.message || e?.message || 'Could not generate a code.') }
  }
  useEffect(() => { if (seedType) create() }, []) // eslint-disable-line
  const complete = async () => {
    try { const r = await api.post('/remote/channels/complete', { pairing_code: created.pairing_code, sender }); onFlash('ok', r.message); onSpeak(r.message); onDone(); onClose() }
    catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Pairing failed.') }
  }
  return (
    <Modal title="Pair a remote channel" onClose={onClose}>
      {!created ? <>
        <p className="muted">Pair your personal messenger to command the workforce on the go.</p>
        <div className="field"><label>Channel</label>
          <select value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
        <button className="btn" style={{ width: '100%' }} onClick={create}>Generate pairing code</button>
      </> : <>
        <div className="card" style={{ background: 'var(--grad-soft)', boxShadow: 'none', textAlign: 'center' }}>
          <div className="muted" style={{ fontSize: 12 }}>Pairing code</div>
          <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: 4 }}>{created.pairing_code}</div>
        </div>
        <p className="muted mt">Simulate the message you'd send from your phone to finish pairing:</p>
        <div className="field"><label>Your number / handle</label>
          <input value={sender} onChange={(e) => setSender(e.target.value)} placeholder="+91-98765-43210" /></div>
        <button className="btn green" style={{ width: '100%' }} onClick={complete} disabled={!sender}>Confirm pairing</button>
      </>}
    </Modal>
  )
}

function TryModal({ channel, onClose, onDone }) {
  const [log, setLog] = useState([])
  const [text, setText] = useState('')
  const send = async (msg) => {
    const m = msg ?? text; if (!m.trim()) return
    setText('')
    try {
      const r = await api.post('/remote/command', { channel_id: channel.id,
        sender: (channel.sender_allowlist || ['me'])[0], message: m })
      setLog((l) => [...l, { me: m, reply: r.response, allowed: r.allowed, intent: r.intent }])
      onDone()
    } catch (e) { setLog((l) => [...l, { me: m, reply: e?.detail?.message || 'Command failed.', allowed: false }]) }
  }
  const suggestions = ["What's pending?", 'Give me my briefing', 'Approve', 'Delete all agents']
  return (
    <Modal title={`Command via ${channel.type}`} onClose={onClose}>
      <div className="flex wrap mb">{suggestions.map((s) => (
        <button key={s} className="tag" style={{ cursor: 'pointer' }} onClick={() => send(s)}>{s}</button>))}</div>
      <div className="card" style={{ background: 'var(--panel-2)', boxShadow: 'none', maxHeight: 260, overflowY: 'auto' }}>
        {log.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Send a command to try it.</div>}
        {log.map((l, i) => (
          <div key={i} style={{ marginBottom: 10 }}>
            <div style={{ textAlign: 'right' }}><span style={{ background: 'var(--grad)', color: '#fff',
              padding: '6px 11px', borderRadius: 12, fontSize: 13, display: 'inline-block' }}>{l.me}</span></div>
            <div style={{ marginTop: 4 }}><span style={{ background: 'var(--panel)', border: '1px solid var(--border)',
              padding: '6px 11px', borderRadius: 12, fontSize: 13, display: 'inline-block',
              color: l.allowed ? 'var(--text)' : 'var(--red)' }}>{l.reply}</span></div>
          </div>
        ))}
      </div>
      <div className="flex mt">
        <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Type a command…" />
        <button className="btn" onClick={() => send()}><Icon name="send" size={16} /></button>
      </div>
    </Modal>
  )
}
