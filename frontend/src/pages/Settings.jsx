import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'
import { getBig, setBig, setMode, useMode } from '../mode'

export default function Settings() {
  const { user } = useAuth()
  const [cfg, setCfg] = useState(null)        // saved/effective config
  const [draft, setDraft] = useState(null)    // editable copy
  const [opts, setOpts] = useState(null)
  const [models, setModels] = useState([])
  const [online, setOnline] = useState(false)
  const [voice, setVoice] = useState(null)
  const [test, setTest] = useState(null)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const [busy, setBusy] = useState(false)
  const recogRef = useRef(null)
  const draftRef = useRef(null); draftRef.current = draft

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 7000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([api.get('/agent/config'), api.get('/voice/config').catch(() => null)])
    .then(([g, v]) => { setCfg(g.config); setDraft({ ...g.config }); setOpts(g.options); setModels(g.installed_models || []); setOnline(g.runtime_online); setVoice(v) })
    .catch(() => flash('err', 'Could not load settings.'))
  useEffect(() => { load() }, [])

  const dirty = cfg && draft && JSON.stringify(cfg) !== JSON.stringify(draft)
  const set = (k, v) => setDraft((d) => ({ ...d, [k]: v }))

  const save = async (patch = draft) => {
    setBusy(true)
    try { const r = await api.patch('/agent/config', { config: patch }); setCfg(r.config); setDraft({ ...r.config }); flash('ok', r.message); speak(r.message) }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not save settings.') }
    finally { setBusy(false) }
  }
  const reset = async () => {
    if (!window.confirm('Reset all Hermes agent settings to defaults?')) return
    try { const r = await api.post('/agent/config/reset'); setCfg(r.config); setDraft({ ...r.config }); flash('ok', r.message); speak(r.message) }
    catch (e) { flash('err', e?.message || 'Could not reset.') }
  }
  const runTest = async () => {
    setBusy(true)
    try { const r = await api.post('/agent/config/test', {}); setTest(r); flash(r.online ? 'ok' : 'err', r.message); speak(r.output) }
    catch (e) { flash('err', e?.message || 'Test failed.') }
    finally { setBusy(false) }
  }

  const runCommand = async (text) => {
    const phrase = (text ?? cmd).trim()
    if (!phrase) return
    setCmd('')
    try {
      const r = await api.post('/voice/settings/resolve', { transcript: phrase })
      switch (r.action) {
        case 'set': { const next = { ...draftRef.current, [r.field]: r.value }; setDraft(next); await save({ [r.field]: r.value }) } break
        case 'test': await runTest(); break
        case 'reset': { const x = await api.post('/agent/config/reset'); setCfg(x.config); setDraft({ ...x.config }); flash('ok', x.message); speak(x.message) } break
        case 'display': if (r.mode) setMode(r.mode); if (r.big != null) setBig(r.big); flash('ok', r.message); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__settingsVoice = (t) => { runCommand(t); return true }; return () => { if (window.__settingsVoice) delete window.__settingsVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!draft) return <Loading />
  const modelNames = [...new Set([...models.map((m) => m.name), draft.reasoning_model, draft.fast_model, draft.embed_model].filter(Boolean))]

  return (
    <>
      <PageHead title="Settings" sub="Hermes agent configuration, account, voice & privacy — tune your AI workforce for better output.">
        <div className="flex" style={{ gap: 8 }}>
          <button className="btn ghost sm" onClick={reset}>Reset defaults</button>
          <button className="btn" onClick={() => save()} disabled={!dirty || busy}><Icon name="check" size={15} /> {busy ? 'Saving…' : dirty ? 'Save changes' : 'Saved'}</button>
        </div>
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "set temperature to 0.5", "use a friendly tone", "set autonomy to full auto", "turn on telemetry", "test the agent"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {/* ── Hermes Agent Configuration ─────────────────────────────── */}
      <div className="card mb" style={{ borderTop: '3px solid var(--primary)' }}>
        <div className="between mb">
          <h3 style={{ margin: 0 }}><Icon name="cpu" size={17} /> Hermes Agent Configuration</h3>
          <span className={'pill ' + (online ? 'st-online' : 'st-error')}><span className="dot" />
            {online ? 'local runtime online' : 'runtime offline · rule-based fallback'}</span>
        </div>
        <p className="muted" style={{ fontSize: 12.5, marginTop: 0 }}>These knobs shape every agent's reasoning and output. Saved per company; private to your machine.</p>

        <div className="grid cols-2" style={{ gap: 18 }}>
          {/* Reasoning & models */}
          <div>
            <h4 style={{ margin: '4px 0' }}>Reasoning & models</h4>
            <Field label="Reasoning model (complex tasks)">
              <select value={draft.reasoning_model} onChange={(e) => set('reasoning_model', e.target.value)}>
                {modelNames.map((m) => <option key={m} value={m}>{m}</option>)}</select></Field>
            <Field label="Fast model (simple tasks)">
              <select value={draft.fast_model} onChange={(e) => set('fast_model', e.target.value)}>
                {modelNames.map((m) => <option key={m} value={m}>{m}</option>)}</select></Field>
            <Field label="Embedding model (memory search)">
              <select value={draft.embed_model} onChange={(e) => set('embed_model', e.target.value)}>
                {[...new Set([draft.embed_model, 'nomic-embed-text', ...models.map((m) => m.name)])].map((m) => <option key={m} value={m}>{m}</option>)}</select></Field>
          </div>

          {/* Generation params */}
          <div>
            <h4 style={{ margin: '4px 0' }}>Generation</h4>
            <Field label={`Creativity (temperature) — ${draft.temperature}`}>
              <input type="range" min="0" max="1" step="0.05" value={draft.temperature}
                onChange={(e) => set('temperature', parseFloat(e.target.value))} style={{ width: '100%' }} />
              <div className="between muted" style={{ fontSize: 11 }}><span>precise</span><span>creative</span></div>
            </Field>
            <Field label="Max response length (tokens)">
              <input type="number" min="64" max="4096" value={draft.max_tokens} onChange={(e) => set('max_tokens', parseInt(e.target.value) || 0)} /></Field>
            <Field label="Context window (tokens)">
              <input type="number" min="1024" max="32768" step="1024" value={draft.context_window} onChange={(e) => set('context_window', parseInt(e.target.value) || 0)} /></Field>
          </div>

          {/* Behaviour */}
          <div>
            <h4 style={{ margin: '4px 0' }}>Behaviour & output quality</h4>
            <Field label="Autonomy level">
              <select value={draft.autonomy} onChange={(e) => set('autonomy', e.target.value)}>
                {opts.autonomy.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
              <div className="muted" style={{ fontSize: 11 }}>{opts.autonomy.find((o) => o.value === draft.autonomy)?.desc}</div></Field>
            <Field label="Grounding (anti-hallucination)">
              <select value={draft.grounding} onChange={(e) => set('grounding', e.target.value)}>
                {opts.grounding.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>
              <div className="muted" style={{ fontSize: 11 }}>{opts.grounding.find((o) => o.value === draft.grounding)?.desc}</div></Field>
            <div className="grid cols-2" style={{ gap: 10 }}>
              <Field label="Tone">
                <select value={draft.tone} onChange={(e) => set('tone', e.target.value)}>
                  {opts.tone.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></Field>
              <Field label="Verbosity">
                <select value={draft.verbosity} onChange={(e) => set('verbosity', e.target.value)}>
                  {opts.verbosity.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></Field>
            </div>
          </div>

          {/* Reliability & safety */}
          <div>
            <h4 style={{ margin: '4px 0' }}>Reliability & safety</h4>
            <Field label="Retries on failure">
              <input type="number" min="0" max="5" value={draft.retry_count} onChange={(e) => set('retry_count', parseInt(e.target.value) || 0)} /></Field>
            <Field label="Approval needed above (₹)">
              <input type="number" min="0" step="1000" value={draft.approval_threshold_inr} onChange={(e) => set('approval_threshold_inr', parseInt(e.target.value) || 0)} /></Field>
            <label className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer', padding: '6px 0' }}>
              <input type="checkbox" checked={draft.failover_managed} style={{ width: 16 }} onChange={(e) => set('failover_managed', e.target.checked)} />
              Failover to managed gateway if local fails</label>
            <label className="flex" style={{ width: 'auto', fontSize: 13, cursor: 'pointer', padding: '6px 0' }}>
              <input type="checkbox" checked={draft.telemetry} style={{ width: 16 }} onChange={(e) => set('telemetry', e.target.checked)} />
              Share anonymous telemetry (off by default)</label>
          </div>
        </div>

        {/* Voice I/O */}
        <h4 style={{ margin: '14px 0 4px' }}>Voice I/O</h4>
        <div className="grid cols-4" style={{ gap: 12 }}>
          <Field label="Wake word"><input value={draft.wake_word} onChange={(e) => set('wake_word', e.target.value)} /></Field>
          <Field label="Push-to-talk"><input value={draft.push_to_talk} onChange={(e) => set('push_to_talk', e.target.value)} /></Field>
          <Field label="Language"><select value={draft.language} onChange={(e) => set('language', e.target.value)}>
            {opts.language.map((l) => <option key={l} value={l}>{l}</option>)}</select></Field>
          <Field label="TTS voice"><select value={draft.tts_voice} onChange={(e) => set('tts_voice', e.target.value)}>
            {opts.voices.map((v) => <option key={v} value={v}>{v}</option>)}</select></Field>
        </div>

        {/* Test */}
        <div className="row-actions mt" style={{ alignItems: 'center' }}>
          <button className="btn secondary sm" onClick={runTest} disabled={busy}><Icon name="zap" size={14} /> Test with these settings</button>
          {dirty && <span className="muted" style={{ fontSize: 12 }}>Unsaved changes — Save to apply.</span>}
        </div>
        {test && <div className="card mt" style={{ background: 'var(--bg-2)' }}>
          <div className="muted" style={{ fontSize: 11 }}>Sample · {test.model} · temp {test.temperature} · {test.tone} {test.online ? '· local' : '· templated (offline)'}</div>
          <div style={{ fontSize: 13.5, marginTop: 6 }}>🔊 {test.output}</div>
        </div>}
      </div>

      <DisplayCard />

      <div className="grid cols-2">
        <div className="card">
          <h3><Icon name="settings" size={17} /> Account</h3>
          <Row k="Name" v={user?.full_name} />
          <Row k="Email" v={user?.email} />
          <Row k="Company" v={user?.tenant?.company_name} />
          <Row k="Industry" v={user?.tenant?.industry || 'Universal core'} />
          <Row k="Role" v={user?.role} />
        </div>
        <div className="card">
          <h3><Icon name="shield" size={17} /> Privacy & Security</h3>
          <ul style={{ fontSize: 13, lineHeight: 1.9, paddingLeft: 16 }}>
            <li>AES-256 local encryption at rest · OS keychain</li>
            <li>Vault-managed credentials (injected as references)</li>
            <li>Immutable audit logs (every agent action)</li>
            <li>Business data never leaves the local plane (SRS-INV-1)</li>
            <li>Telemetry: <strong>{draft.telemetry ? 'on' : 'off'}</strong></li>
          </ul>
        </div>
      </div>
    </>
  )
}

function DisplayCard() {
  const mode = useMode()
  const [big, setBigState] = useState(getBig())
  return (
    <div className="card mb">
      <h3><Icon name="settings" size={17} /> Display & accessibility</h3>
      <div className="grid cols-2" style={{ gap: 16 }}>
        <div>
          <div className="muted mb" style={{ fontSize: 12 }}>Detail level (one surface, two doors)</div>
          <div className="tabs" style={{ margin: 0, maxWidth: 280 }}>
            {['simple', 'advanced'].map((m) => (
              <button key={m} className={mode === m ? 'active' : ''} onClick={() => setMode(m)}>
                {m === 'simple' ? 'Simple — plain language' : 'Advanced — logs, IDs, JSON'}</button>
            ))}
          </div>
        </div>
        <div>
          <div className="muted mb" style={{ fontSize: 12 }}>Accessibility</div>
          <label className="flex" style={{ width: 'auto', fontSize: 14, cursor: 'pointer' }}>
            <input type="checkbox" checked={big} style={{ width: 18 }}
              onChange={(e) => { setBig(e.target.checked); setBigState(e.target.checked) }} />
            Large type (voice-first, words + icons, never colour alone)
          </label>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return <div className="field" style={{ marginBottom: 10 }}>
    <label style={{ fontSize: 12 }}>{label}</label>{children}</div>
}

function Row({ k, v }) {
  return <div className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
    <span className="muted">{k}</span><span>{v || '—'}</span></div>
}
