import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Empty, Loading, Modal, PageHead, Pill } from '../components/ui'

export default function Webhooks() {
  const [hooks, setHooks] = useState(null)
  const [events, setEvents] = useState([])
  const [add, setAdd] = useState(false)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)
  const hRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([api.get('/webhooks'), api.get('/webhooks/events')])
    .then(([h, e]) => { setHooks(h); hRef.current = h; setEvents(e.events) })
    .catch(() => flash('err', 'Could not load webhooks.'))
  useEffect(() => { load() }, [])

  const test = async (h) => {
    try { const r = await api.post(`/webhooks/${h.id}/test`); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not fire the test.') }
  }
  const toggle = async (h) => {
    const status = h.status === 'active' ? 'paused' : 'active'
    try { const r = await api.patch(`/webhooks/${h.id}`, { status }); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not update the webhook.') }
  }
  const del = async (h) => {
    if (!window.confirm(`Remove the webhook for ${hostOf(h.url)}?`)) return
    try { const r = await api.del(`/webhooks/${h.id}`); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not remove the webhook.') }
  }
  const fire = async (event) => {
    try { const r = await api.post('/webhooks/fire', { event }); flash(r.delivered ? 'ok' : 'err', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not fire the event.') }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/webhooks/resolve', { transcript: phrase })
      const find = (id) => (hRef.current || []).find((x) => x.id === id)
      switch (r.action) {
        case 'add': { try { const x = await api.post('/webhooks', { url: r.url, events: r.events, include_content: false }); flash('ok', x.message); speak(x.message); load() } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not add the webhook.') } } break
        case 'add_open': setAdd(true); flash('ok', r.message); break
        case 'test': { const h = find(r.id); if (h) await test(h) } break
        case 'pause': case 'resume': { const h = find(r.id); if (h) await toggle(h) } break
        case 'delete': { const h = find(r.id); if (h) await del(h) } break
        case 'fire': await fire(r.event); break
        case 'events': document.getElementById('event-catalog')?.scrollIntoView({ behavior: 'smooth' }); flash('ok', r.message); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__webhooksVoice = (t) => { runCommand(t); return true }; return () => { if (window.__webhooksVoice) delete window.__webhooksVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!hooks) return <Loading />
  return (
    <>
      <PageHead title="Webhooks & Integrations"
        sub="Fire signed events to Zapier / Make / anything. IDs & metadata by default — business content needs explicit consent.">
        <button className="btn" onClick={() => setAdd(true)}><Icon name="plus" size={16} /> Add webhook</button>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "test the zapier webhook", "pause it", "fire the approval decided event", "remove the webhook"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      <div className="grid" style={{ gridTemplateColumns: '1fr 320px', alignItems: 'start' }}>
        <div>
          {hooks.length === 0 && <Empty>No webhooks yet. Add one to connect HERMUS to your other tools.</Empty>}
          {hooks.map((h) => (
            <div className="card mb" key={h.id}>
              <div className="between mb">
                <div style={{ fontFamily: 'monospace', fontSize: 13, wordBreak: 'break-all' }}>{h.url}</div>
                <Pill status={h.status === 'active' ? 'active' : 'paused'} />
              </div>
              <div className="flex wrap mb">{h.events.length ? h.events.map((e) => <span key={e} className="tag">{e}</span>)
                : <span className="muted" style={{ fontSize: 12 }}>no events subscribed</span>}</div>
              <div className="between">
                <span className="muted" style={{ fontSize: 12 }}>{h.deliveries} delivered
                  {h.include_content ? ' · content ON' : ' · IDs only'}
                  {h.last_fired_at ? ` · last ${new Date(h.last_fired_at).toLocaleString()}` : ''}</span>
                <div className="row-actions">
                  <button className="btn secondary sm" onClick={() => test(h)} disabled={h.status !== 'active'}>Test fire</button>
                  <button className="btn ghost sm" onClick={() => toggle(h)}>{h.status === 'active' ? 'Pause' : 'Resume'}</button>
                  <button className="icon-btn" style={{ width: 30, height: 30 }} title="Remove" onClick={() => del(h)}><Icon name="x" size={13} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
        <div className="card" id="event-catalog">
          <h3><Icon name="zap" size={17} /> Event catalog</h3>
          <p className="muted" style={{ fontSize: 12.5 }}>Every platform event can trigger an integration. Click to broadcast a signed test.</p>
          {events.map((e) => <button key={e} className="tag" style={{ display: 'block', marginBottom: 4, fontFamily: 'monospace', cursor: 'pointer', textAlign: 'left', width: '100%' }}
            title="Fire a signed test event" onClick={() => fire(e)}>{e}</button>)}
          <div className="card mt" style={{ background: 'var(--grad-soft)', boxShadow: 'none' }}>
            <div style={{ fontSize: 12.5 }}>Official <strong>Zapier / Make</strong> connectors wrap these webhooks + a minimal action API (create PARTY, start recipe, send approved template).</div>
          </div>
        </div>
      </div>
      {add && <AddWebhook events={events} onClose={() => setAdd(false)} onDone={load} onFlash={flash} onSpeak={speak} />}
    </>
  )
}

function hostOf(url) { try { return new URL(url).host } catch { return url } }

function AddWebhook({ events, onClose, onDone, onFlash, onSpeak }) {
  const [url, setUrl] = useState('')
  const [sel, setSel] = useState([])
  const [content, setContent] = useState(false)
  const [created, setCreated] = useState(null)
  const submit = async () => {
    try { const r = await api.post('/webhooks', { url, events: sel, include_content: content }); setCreated(r); onFlash('ok', r.message); onSpeak(r.message); onDone() }
    catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Could not create the webhook.') }
  }
  if (created) return (
    <Modal title="Webhook created" onClose={onClose}>
      <p className="muted" style={{ fontSize: 13 }}>Save this signing secret — it's shown once. Verify deliveries with HMAC-SHA256.</p>
      <div className="card" style={{ background: 'var(--grad-soft)', boxShadow: 'none' }}>
        <div className="muted" style={{ fontSize: 11 }}>Signing secret</div>
        <div style={{ fontFamily: 'monospace', fontSize: 14, wordBreak: 'break-all', userSelect: 'all' }}>{created.secret}</div>
      </div>
      <button className="btn mt" style={{ width: '100%' }} onClick={onClose}>Done</button>
    </Modal>
  )
  return (
    <Modal title="Add webhook" onClose={onClose}>
      <div className="field"><label>Endpoint URL</label>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://hooks.zapier.com/…" autoFocus /></div>
      <div className="field"><label>Events</label>
        <div className="flex wrap">{events.map((e) => (
          <label key={e} className="flex" style={{ width: 'auto', fontSize: 12.5, cursor: 'pointer' }}>
            <input type="checkbox" checked={sel.includes(e)} style={{ width: 15 }}
              onChange={() => setSel(sel.includes(e) ? sel.filter(x => x !== e) : [...sel, e])} /> {e}
          </label>))}</div></div>
      <label className="flex mb" style={{ width: 'auto', fontSize: 13, cursor: 'pointer' }}>
        <input type="checkbox" checked={content} style={{ width: 16 }} onChange={(e) => setContent(e.target.checked)} />
        Include business content (off by default — privacy invariant)
      </label>
      <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={!url || sel.length === 0}>Create signed webhook</button>
    </Modal>
  )
}
