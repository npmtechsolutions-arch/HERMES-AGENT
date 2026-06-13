import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead, Pill } from '../components/ui'

const COLORS = { violet: 'var(--grad)', blue: 'var(--grad-2)',
  green: 'linear-gradient(135deg,#10b981,#34d399)', amber: 'linear-gradient(135deg,#f59e0b,#fbbf24)' }
const CHANNEL_LABEL = { website: 'Website', desktop: 'Desktop', voice: 'Voice',
  telegram: 'Telegram', whatsapp: 'WhatsApp', slack: 'Slack', teams: 'Teams',
  discord: 'Discord', email: 'Email' }
const SCOPES = ['business', 'knowledge', 'personal', 'operational']

export default function Chatbots() {
  const { user } = useAuth()
  const [bots, setBots] = useState(null)
  const [sel, setSel] = useState(null)
  const [create, setCreate] = useState(false)
  const [editBot, setEditBot] = useState(null)
  const [channelsFor, setChannelsFor] = useState(null)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const [pending, setPending] = useState(null)   // active clarification {action, need, slots}
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), kind === 'ask' ? 12000 : 7000) }
  const speak = (t, after) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) { after && after(); return }
    const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'
    u.onend = () => after && after(); u.onerror = () => after && after()
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(u)
  }
  const load = () => api.get('/chatbots').then((b) => {
    setBots(b); if (!sel && b[0]) setSel(b[0].id); else if (sel && !b.find((x) => x.id === sel)) setSel(b[0]?.id || null)
  }).catch(() => flash('err', 'Could not load chatbots.'))
  useEffect(() => { load() }, [])

  // execute a concrete (non-clarify) action; returns a short spoken confirmation
  const exec = async (r) => {
    switch (r.action) {
      case 'create_bot': { const b = await api.post('/chatbots', { name: r.name, purpose: r.purpose || undefined }); await load(); setSel(b.id); return `Created ${b.name}.` }
      case 'delete_bot': { const x = await api.del(`/chatbots/${r.bot_id}`); await load(); return x.message || `Deleted ${r.bot_name}.` }
      case 'open_bot': setSel(r.bot_id); return `Opened ${r.bot_name}.`
      case 'connect_channel': { const id = r.bot_id || sel; if (!id) throw { message: 'Pick a chatbot first.' }
        const x = await api.post(`/chatbots/${id}/channels`, { type: r.channel, token: 'demo-token', account: 'connected' }); await load(); return x.message || `Connected ${r.channel}.` }
      case 'disconnect_channel': { const id = r.bot_id || sel; if (!id) throw { message: 'Pick a chatbot first.' }
        const x = await api.del(`/chatbots/${id}/channels/${r.channel}`); await load(); return x.message || `Disconnected ${r.channel}.` }
      default: return null
    }
  }

  const runCommand = async (text, carry) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      // only ever send a clean clarify-context object (never a DOM event / fiber)
      const src = carry !== undefined ? carry : pending
      const safePending = src && src.action ? { action: src.action, need: src.need, slots: src.slots } : null
      const r = await api.post('/chatbots/resolve', { transcript: phrase, pending: safePending })
      if (r.action === 'clarify') {            // ask the user, speak it, then listen again
        setPending(r.pending); flash('ask', r.question)
        speak(r.question, () => startListening(r.pending))
        return
      }
      setPending(null)
      if (r.action === 'cancelled') { flash('ok', r.message); speak('Okay, cancelled.'); return }
      if (r.action === 'none') { flash('err', r.message); speak(r.message); return }
      const confirm = await exec(r)
      if (confirm) { flash('ok', confirm); speak(confirm) }
    } catch (e) {
      setPending(null)
      const m = e?.detail?.message || e?.message || 'Could not run that command.'
      flash('err', m); speak('Sorry, ' + m)
    }
  }
  useEffect(() => { window.__chatbotsVoice = (t) => { runCommand(t); return true }; return () => { if (window.__chatbotsVoice) delete window.__chatbotsVoice } })

  const startListening = (carry) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return  // no mic: the question stays on screen; the user can type the answer + Run
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t, carry !== undefined ? carry : pending) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!bots) return <Loading />
  const current = bots.find((b) => b.id === sel)

  return (
    <>
      <PageHead title="Chatbots"
        sub={`Profile: ${user?.tenant?.company_name} — purpose-built assistants across channels, by click or voice.`}>
        <button className="btn" onClick={() => setCreate(true)}><Icon name="plus" size={16} /> Create chatbot</button>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : pending ? '…your answer (e.g. the chatbot or channel name)'
              : 'Say or type: "create a sales bot", "open the support bot", "connect telegram", "spin up an HR assistant"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}>
            <Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : msg.kind === 'ask' ? 'var(--primary)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : msg.kind === 'ask' ? '🎤 ' : '⚠ '}{msg.text}</div>}

      <div className="grid" style={{ gridTemplateColumns: '300px 1fr', alignItems: 'start' }}>
        <div className="card" style={{ padding: 10 }}>
          {bots.map((b) => (
            <div key={b.id} className={'thread-item' + (sel === b.id ? ' sel' : '')}
              onClick={() => setSel(b.id)} style={{ marginBottom: 4 }}>
              <div className="flex">
                <div className="ix" style={{ width: 38, height: 38, borderRadius: 11,
                  background: COLORS[b.color] || COLORS.violet, color: '#fff', display: 'grid',
                  placeItems: 'center' }}><Icon name="bot" size={20} /></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{b.name}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{b.department}</div>
                </div>
              </div>
              <div className="flex wrap" style={{ marginTop: 6, gap: 4 }}>
                {b.channels.filter((c) => c.status === 'connected').map((c) => (
                  <span key={c.type} className="tag" style={{ fontSize: 10, padding: '1px 6px' }}>{CHANNEL_LABEL[c.type]}</span>
                ))}
              </div>
            </div>
          ))}
          {bots.length === 0 && <div className="empty" style={{ padding: 24 }}>No chatbots yet. Click <strong>Create chatbot</strong> or say "create a sales bot".</div>}
        </div>

        {current
          ? <ChatPanel bot={current} onChannels={() => setChannelsFor(current)} onEdit={() => setEditBot(current)} onChanged={load} onFlash={flash} />
          : <div className="card"><div className="empty">Create a chatbot to get started.</div></div>}
      </div>

      {create && <BotForm onClose={() => setCreate(false)} onSaved={(b) => { load(); if (b?.id) setSel(b.id) }} onFlash={flash} />}
      {editBot && <BotForm bot={editBot} onClose={() => setEditBot(null)} onSaved={() => load()} onFlash={flash} />}
      {channelsFor && <ChannelsModal bot={channelsFor} onClose={() => setChannelsFor(null)} onChanged={load} onFlash={flash} />}
    </>
  )
}

function ChatPanel({ bot, onChannels, onEdit, onChanged, onFlash }) {
  const [msgs, setMsgs] = useState([])
  const [convId, setConvId] = useState(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [speak, setSpeak] = useState(false)
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const endRef = useRef(null)
  const supported = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition)

  useEffect(() => {
    setMsgs([]); setConvId(null)
    api.get(`/chatbots/${bot.id}/conversations`).then((c) => {
      if (c[0]) { setConvId(c[0].id); setMsgs(c[0].messages) }
    }).catch(() => {})
  }, [bot.id])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  useEffect(() => {
    if (!supported) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = true
    r.onresult = (e) => { let t = ''; for (const res of e.results) t += res[0].transcript; setText(t) }
    r.onend = () => setListening(false)
    recogRef.current = r
    return () => { try { r.stop() } catch {} }
  }, [supported])

  const send = async (msg) => {
    const m = (msg ?? text).trim(); if (!m || busy) return
    setText(''); setMsgs((x) => [...x, { role: 'user', body: m }]); setBusy(true)
    try {
      const r = await api.post(`/chatbots/${bot.id}/chat`, { message: m, conversation_id: convId })
      setConvId(r.conversation_id)
      setMsgs((x) => [...x, { role: 'assistant', body: r.response, citations: r.citations, engine: r.engine }])
      if (speak && window.speechSynthesis) {
        const u = new SpeechSynthesisUtterance(r.response); u.lang = 'en-IN'
        window.speechSynthesis.cancel(); window.speechSynthesis.speak(u)
      }
    } catch (e) {
      setMsgs((x) => [...x, { role: 'assistant', body: '⚠ ' + (e?.message || 'The assistant could not reply.'), error: true }])
      onFlash?.('err', e?.message || 'Chat failed.')
    } finally { setBusy(false) }
  }
  const toggleMic = () => {
    if (!supported) return
    if (listening) { recogRef.current.stop(); setListening(false) }
    else { setText(''); setListening(true); try { recogRef.current.start() } catch {} }
  }
  const remove = async () => {
    if (!window.confirm(`Delete “${bot.name}”? This removes the chatbot (recoverable).`)) return
    try { const r = await api.del(`/chatbots/${bot.id}`); onFlash('ok', r.message || `Deleted “${bot.name}”.`); onChanged() }
    catch (e) { onFlash('err', e?.message || 'Could not delete the chatbot.') }
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '70vh', padding: 0 }}>
      <div className="between" style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
        <div className="flex">
          <div className="ix" style={{ width: 40, height: 40, borderRadius: 12,
            background: COLORS[bot.color] || COLORS.violet, color: '#fff', display: 'grid', placeItems: 'center' }}>
            <Icon name="bot" size={21} /></div>
          <div>
            <div style={{ fontWeight: 700 }}>{bot.name}</div>
            <div className="muted" style={{ fontSize: 12 }}>{bot.purpose}</div>
          </div>
        </div>
        <div className="row-actions">
          <button className="btn secondary sm" onClick={onEdit}><Icon name="settings" size={14} /> Edit</button>
          <button className="btn secondary sm" onClick={onChannels}><Icon name="link" size={14} /> Channels</button>
          <button className="icon-btn" title="Delete" style={{ width: 34, height: 34 }} onClick={remove}><Icon name="x" size={15} /></button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 18 }}>
        {msgs.length === 0 && <div className="empty">
          Say hello to <strong>{bot.name}</strong>. It answers from your company memory
          ({(bot.memory_scopes || []).join(', ') || 'all'}).</div>}
        {msgs.map((m, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: m.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
            <div style={{ maxWidth: '78%' }}>
              <div style={{ padding: '10px 14px', borderRadius: 14, fontSize: 14,
                background: m.role === 'user' ? 'var(--grad)' : m.error ? 'var(--red-bg, #fee)' : 'var(--panel-2)',
                color: m.role === 'user' ? '#fff' : 'var(--text)',
                border: m.role === 'user' ? 'none' : '1px solid var(--border)', whiteSpace: 'pre-wrap' }}>
                {m.body}
              </div>
              {m.citations?.length > 0 && <div className="flex wrap" style={{ marginTop: 5, gap: 4 }}>
                {m.citations.map((c, j) => <span key={j} className="cite" style={{ fontSize: 11 }}>📎 {c.title}</span>)}
              </div>}
              {m.engine && <div className="muted" style={{ fontSize: 10, marginTop: 2 }}>via {m.engine}</div>}
            </div>
          </div>
        ))}
        {busy && <div className="muted" style={{ fontSize: 13 }}>🧠 {bot.name} is thinking…</div>}
        <div ref={endRef} />
      </div>

      <div style={{ padding: 14, borderTop: '1px solid var(--border)' }}>
        <div className="flex">
          <button className="icon-btn" onClick={toggleMic}
            title={supported ? 'Voice input' : 'Voice not available'} disabled={!supported}
            style={listening ? { background: 'var(--grad)', color: '#fff', borderColor: 'transparent' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input value={text} onChange={(e) => setText(e.target.value)} disabled={busy}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder={listening ? 'Listening…' : `Message ${bot.name}…`} />
          <button className="icon-btn" onClick={() => setSpeak(!speak)} title="Read replies aloud"
            style={speak ? { background: 'var(--grad)', color: '#fff', borderColor: 'transparent' } : {}}>
            🔊</button>
          <button className="btn" onClick={() => send()} disabled={busy || !text.trim()}>
            <Icon name="send" size={16} /></button>
        </div>
      </div>
    </div>
  )
}

function BotForm({ bot, onClose, onSaved, onFlash }) {
  const editing = !!bot
  const [depts, setDepts] = useState([])
  const [f, setF] = useState({
    name: bot?.name || '', purpose: bot?.purpose || '', department: bot?.department || '',
    model_id: bot?.model_id || 'mdl_gemma9b', persona: bot?.persona || '',
    memory_scopes: bot?.memory_scopes || ['business', 'knowledge'], color: bot?.color || 'violet',
  })
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.get('/departments').then(setDepts).catch(() => {}) }, [])
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const toggleScope = (s) => setF({ ...f, memory_scopes: f.memory_scopes.includes(s)
    ? f.memory_scopes.filter((x) => x !== s) : [...f.memory_scopes, s] })
  const submit = async () => {
    setBusy(true)
    try {
      const b = editing ? await api.patch(`/chatbots/${bot.id}`, f) : await api.post('/chatbots', f)
      onFlash('ok', editing ? `Updated “${b.name}”.` : `Created “${b.name}”.`); onSaved(b); onClose()
    } catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not save the chatbot.') }
    finally { setBusy(false) }
  }

  return (
    <Modal title={editing ? `Edit ${bot.name}` : 'Create a chatbot'} onClose={onClose}>
      {!editing && <p className="muted">A purpose-built assistant — e.g. Sales Bot, HR Bot, Support Bot.</p>}
      <div className="field"><label>Name</label>
        <input value={f.name} onChange={set('name')} placeholder="e.g. Sales Assistant" autoFocus /></div>
      <div className="field"><label>Purpose</label>
        <input value={f.purpose} onChange={set('purpose')} placeholder="What is this bot for?" /></div>
      <div className="grid cols-2" style={{ gap: 12 }}>
        <div className="field"><label>Department</label>
          <select value={f.department} onChange={set('department')}>
            <option value="">—</option>
            {depts.map((d) => <option key={d.id} value={d.name}>{d.name}</option>)}
          </select></div>
        <div className="field"><label>Model</label>
          <select value={f.model_id} onChange={set('model_id')}>
            <option value="mdl_gemma9b">Gemma 9B</option>
            <option value="mdl_qwen14b_q4">Qwen 14B</option>
            <option value="mdl_phi3">Phi 3.8B</option>
          </select></div>
      </div>
      <div className="field"><label>Persona / instructions</label>
        <textarea rows={3} value={f.persona} onChange={set('persona')}
          placeholder="You are a friendly sales assistant who…" /></div>
      <div className="field"><label>Memory scope</label>
        <div className="flex wrap">{SCOPES.map((s) => (
          <label key={s} className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={f.memory_scopes.includes(s)} style={{ width: 16 }}
              onChange={() => toggleScope(s)} /> {s}
          </label>))}</div></div>
      <div className="field"><label>Color</label>
        <div className="flex">{Object.keys(COLORS).map((c) => (
          <button key={c} onClick={() => setF({ ...f, color: c })} style={{ width: 30, height: 30,
            borderRadius: 9, background: COLORS[c], border: f.color === c ? '2px solid var(--text)' : 'none', cursor: 'pointer' }} />
        ))}</div></div>
      <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={!f.name || busy}>
        {busy ? 'Saving…' : editing ? 'Save changes' : 'Create chatbot'}</button>
    </Modal>
  )
}

function ChannelsModal({ bot, onClose, onChanged, onFlash }) {
  const [channels, setChannels] = useState(null)
  const [connecting, setConnecting] = useState(null)
  const [token, setToken] = useState('')
  const load = () => api.get(`/chatbots/${bot.id}/channels`).then(setChannels)
  useEffect(() => { load() }, [])

  const connect = async (type) => {
    try { const r = await api.post(`/chatbots/${bot.id}/channels`, { type, token: token || 'demo-token', account: 'connected' })
      onFlash('ok', r.message || `Connected ${type}.`); setConnecting(null); setToken(''); load(); onChanged() }
    catch (e) { onFlash('err', e?.message || `Could not connect ${type}.`) }
  }
  const disconnect = async (type) => {
    try { const r = await api.del(`/chatbots/${bot.id}/channels/${type}`); onFlash('ok', r.message || `Disconnected ${type}.`); load(); onChanged() }
    catch (e) { onFlash('err', e?.message || `Could not disconnect ${type}.`) }
  }

  return (
    <Modal title={`Channels · ${bot.name}`} onClose={onClose}>
      <p className="muted">Connect this chatbot to the platforms your users live on. Every channel
        normalizes to the same engine (the adapter layer).</p>
      {!channels ? <Loading /> : channels.map((c) => (
        <div key={c.type} className="between" style={{ padding: '11px 0', borderBottom: '1px solid var(--border)' }}>
          <div className="flex">
            <Icon name={c.type === 'voice' ? 'mic' : c.type === 'email' ? 'inbox' : 'chat'} size={18} />
            <div><div style={{ fontWeight: 600, fontSize: 14 }}>{CHANNEL_LABEL[c.type]}</div>
              {c.account && <div className="muted" style={{ fontSize: 11 }}>{c.account}</div>}</div>
          </div>
          {c.status === 'connected'
            ? <div className="flex"><Pill status="connected" />
                {c.type !== 'website' && <button className="btn ghost sm" onClick={() => disconnect(c.type)}>Disconnect</button>}</div>
            : connecting === c.type
              ? <div className="flex">
                  <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="API token"
                    style={{ width: 150 }} />
                  <button className="btn sm" onClick={() => connect(c.type)}>Save</button>
                </div>
              : <button className="btn secondary sm" onClick={() => setConnecting(c.type)}>
                  <Icon name="link" size={13} /> Connect</button>}
        </div>
      ))}
    </Modal>
  )
}
