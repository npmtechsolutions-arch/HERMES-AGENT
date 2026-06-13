import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, Modal, PageHead, Pill } from '../components/ui'

const DEST_TYPES = [['folder', 'Local folder'], ['usb', 'USB drive'], ['gdrive', 'Google Drive'],
  ['onedrive', 'OneDrive'], ['lan', 'Second machine (LAN)']]
const DEST_LABEL = Object.fromEntries(DEST_TYPES)

export default function Backup() {
  const [status, setStatus] = useState(null)
  const [dests, setDests] = useState([])
  const [history, setHistory] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  const [phrase, setPhrase] = useState(null)
  const [verify, setVerify] = useState(null)
  const [restore, setRestore] = useState(false)
  const [addDest, setAddDest] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [cmd, setCmd] = useState('')
  const [listening, setListening] = useState(false)
  const recogRef = useRef(null)

  const flash = (kind, text) => { setMsg({ kind, text }); setTimeout(() => setMsg(null), 8000) }
  const speak = (t) => { try { if (typeof window !== 'undefined' && window.speechSynthesis) { const u = new SpeechSynthesisUtterance(t); u.lang = 'en-IN'; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u) } } catch {} }
  const load = () => Promise.all([
    api.get('/backup/status'), api.get('/backup/destinations'), api.get('/backup/history').catch(() => []),
  ]).then(([s, d, h]) => { setStatus(s); setDests(d); setHistory(h) }).catch(() => flash('err', 'Could not load backup status.'))
  useEffect(() => { load() }, [])

  const makePhrase = async () => {
    try { const r = await api.post('/backup/recovery-phrase'); setPhrase(r); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.message || 'Could not generate a recovery phrase.') }
  }
  const createDest = async (type, path) => {
    try { const r = await api.post('/backup/destinations', { type, path }); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not add the destination.') }
  }
  const removeDest = async (d) => {
    if (!window.confirm(`Remove backup destination ${d.type} (${d.path})?`)) return
    try { const r = await api.del(`/backup/destinations/${d.id}`); flash('ok', r.message); speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not remove the destination.') }
  }
  const runBackup = async () => {
    if (!status.recovery_phrase_set) { flash('err', 'Generate a recovery phrase first.'); return }
    if (dests.length === 0) { flash('err', 'Add a backup destination first.'); return }
    setBusy(true)
    try { const r = await api.post('/backup/run'); r.status === 'completed' ? flash('ok', r.message) : flash('err', `Backup failed: ${r.reason}`); if (r.status === 'completed') speak(r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Backup failed.') }
    finally { setBusy(false) }
  }
  const runVerify = async () => {
    setBusy(true)
    try { const r = await api.post('/backup/verify'); setVerify(r); flash(r.ok ? 'ok' : 'err', r.message); speak(r.message) }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not verify the backup.') }
    finally { setBusy(false) }
  }

  const runCommand = async (text) => {
    const phr = (text ?? cmd).trim()
    if (!phr) return
    setCmd('')
    try {
      const r = await api.post('/backup/resolve', { transcript: phr })
      switch (r.action) {
        case 'phrase': await makePhrase(); break
        case 'add_dest': await createDest(r.type, r.path); break
        case 'delete_dest': { const d = dests.find((x) => x.id === r.id); if (d) await removeDest(d) } break
        case 'run': await runBackup(); break
        case 'verify': await runVerify(); break
        case 'restore': setRestore(true); flash('ok', r.message); break
        case 'history': setShowHistory(true); flash('ok', r.message); break
        default: flash('err', r.message || "I didn't catch that."); speak(r.message || "I didn't catch that.")
      }
    } catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not run that command.') }
  }
  useEffect(() => { window.__backupVoice = (t) => { runCommand(t); return true }; return () => { if (window.__backupVoice) delete window.__backupVoice } })

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { flash('err', 'Voice not available in this browser — type the command instead.'); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false; r.continuous = false
    r.onresult = (e) => { const t = e.results[0][0].transcript; setCmd(t); runCommand(t) }
    r.onend = () => setListening(false); r.onerror = () => setListening(false)
    recogRef.current = r; setListening(true)
    try { r.start() } catch { setListening(false) }
  }

  if (!status) return <Loading />
  return (
    <>
      <PageHead title="Backup & Restore" sub="Your data lives on your machine — so it's yours to protect. Encrypted, tenant-key, tenant-destination.">
        {history.length > 0 && <button className="btn ghost sm" onClick={() => setShowHistory((v) => !v)}>
          <Icon name="refresh" size={14} /> History ({history.length})</button>}
      </PageHead>

      <div className="card mb">
        <div className="flex" style={{ gap: 8 }}>
          <button className={`icon-btn${listening ? ' active' : ''}`} title="Speak a command"
            onClick={() => startListening()} style={listening ? { color: 'var(--primary)' } : {}}>
            <Icon name="mic" size={18} /></button>
          <input style={{ flex: 1 }} value={cmd} onChange={(e) => setCmd(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') runCommand() }}
            placeholder={listening ? 'Listening…' : 'Say or type: "back up now", "generate a recovery phrase", "add a folder destination at ~/Backups", "verify the backup"'} />
          <button className="btn sm" onClick={() => runCommand()} disabled={!cmd.trim()}><Icon name="send" size={13} /> Run</button>
        </div>
      </div>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.text}</div>}

      {showHistory && (
        <div className="card mb">
          <h3 style={{ marginTop: 0 }}>Backup history · {history.length}</h3>
          {history.map((h) => (
            <div key={h.id} className="between" style={{ padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12.5 }}>
              <span className="muted">{h.at ? new Date(h.at).toLocaleString() : '—'} · {h.kind}</span>
              <span><strong>{(h.size_bytes / 1024).toFixed(1)} KB</strong> <Pill status={h.status === 'completed' ? 'active' : 'error'} /></span>
            </div>
          ))}
          {history.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No backups yet.</div>}
        </div>
      )}

      <div className="grid cols-2 mb">
        <div className="card">
          <div className="between mb"><h3 style={{ margin: 0 }}><Icon name="shield" size={17} /> Backup health</h3>
            <Pill status={status.stale_48h ? 'error' : 'active'} /></div>
          <div style={{ fontSize: 14 }}>{status.summary}</div>
          {status.stale_48h && status.recovery_phrase_set &&
            <div className="error-box mt">⚠ No successful backup in 48h — this would be an URGENT voice alert in your briefing.</div>}
          <div className="muted mt" style={{ fontSize: 12 }}>Default: daily full + hourly incremental of local Postgres + artifacts.</div>
          <div className="row-actions mt" style={{ flexWrap: 'wrap' }}>
            <button className="btn" onClick={runBackup} disabled={busy || !status.recovery_phrase_set || dests.length === 0}>
              <Icon name="download" size={15} /> {busy ? 'Working…' : 'Back up now'}</button>
            <button className="btn secondary" onClick={runVerify} disabled={busy || !status.last_backup_at}>Verify latest</button>
            <button className="btn secondary" onClick={() => setRestore(true)}>Restore from phrase</button>
          </div>
          {verify && <div className="card mt" style={{ background: verify.ok ? 'var(--success-bg)' : 'var(--danger-bg)',
            border: `1px solid ${verify.ok ? 'var(--success-border)' : 'var(--danger-border)'}` }}>
            <strong style={{ color: verify.ok ? 'var(--success-fg)' : 'var(--danger-fg)' }}>
              {verify.ok ? '✓ ' : '✕ '}{verify.message}</strong>
            {verify.counts && <div className="muted mt" style={{ fontSize: 12 }}>
              {Object.entries(verify.counts).map(([k, v]) => `${v} ${k}`).join(' · ')}</div>}
          </div>}
        </div>

        <div className="card">
          <h3><Icon name="link" size={17} /> Recovery phrase</h3>
          <p className="muted" style={{ fontSize: 12.5 }}>The only way to restore on a new machine. Shown ONCE — we never store it.</p>
          {status.recovery_phrase_set
            ? <div className="pill st-active"><span className="dot" /> recovery phrase set</div>
            : <button className="btn" onClick={makePhrase}>Generate recovery phrase</button>}
          {phrase && (
            <div className="card mt" style={{ background: 'var(--grad-soft)', boxShadow: 'none' }}>
              <div className="flex wrap" style={{ gap: 6 }}>
                {phrase.words.map((w, i) => <span key={i} className="tag">{i + 1}. {w}</span>)}
              </div>
              <div className="error-box mt" style={{ background: 'var(--danger-bg)' }}>{phrase.warning}</div>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="between mb"><h3 style={{ margin: 0 }}><Icon name="monitor" size={17} /> Backup destinations</h3>
          <button className="btn sm" onClick={() => setAddDest(true)}><Icon name="plus" size={14} /> Add destination</button></div>
        {dests.length === 0 && <div className="muted" style={{ fontSize: 13 }}>No destination yet — add a folder, USB, Drive or LAN machine. Your data goes to YOUR destination, encrypted with YOUR key.</div>}
        {dests.map((d) => (
          <div key={d.id} className="between" style={{ padding: '9px 0', borderBottom: '1px solid var(--border)' }}>
            <div className="flex"><span className="tag">{DEST_LABEL[d.type] || d.type}</span><span style={{ fontSize: 13, fontFamily: 'monospace' }}>{d.path}</span></div>
            <div className="flex" style={{ gap: 8 }}>
              <span className="muted" style={{ fontSize: 12 }}>{d.last_backup_at ? `last: ${new Date(d.last_backup_at).toLocaleString()}` : 'never'}</span>
              <button className="icon-btn" style={{ width: 28, height: 28 }} title="Remove" onClick={() => removeDest(d)}><Icon name="x" size={13} /></button>
            </div>
          </div>
        ))}
      </div>

      {addDest && <AddDestModal onClose={() => setAddDest(false)} onAdd={createDest} />}
      {restore && <RestoreModal onClose={() => setRestore(false)} onFlash={flash} />}
    </>
  )
}

function AddDestModal({ onClose, onAdd }) {
  const [type, setType] = useState('folder')
  const [path, setPath] = useState('~/HermusBackups')
  return (
    <Modal title="Add backup destination" onClose={onClose}>
      <div className="field"><label>Type</label>
        <select value={type} onChange={(e) => setType(e.target.value)}>{DEST_TYPES.map(([t, l]) => <option key={t} value={t}>{l}</option>)}</select></div>
      <div className="field"><label>Path / account</label>
        <input autoFocus value={path} onChange={(e) => setPath(e.target.value)} placeholder="~/HermusBackups or account ref"
          onKeyDown={(e) => { if (e.key === 'Enter' && path.trim()) { onAdd(type, path.trim()); onClose() } }} /></div>
      <button className="btn" style={{ width: '100%' }} disabled={!path.trim()} onClick={() => { onAdd(type, path.trim()); onClose() }}>Add destination</button>
    </Modal>
  )
}

function RestoreModal({ onClose, onFlash }) {
  const [words, setWords] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const go = async () => {
    setBusy(true)
    try { const r = await api.post('/backup/restore', { phrase: words.trim() }); setResult(r); onFlash(r.status === 'restored' ? 'ok' : 'err', r.status === 'restored' ? r.message : r.reason) }
    catch (e) { onFlash('err', e?.detail?.message || e?.message || 'Restore failed.') }
    finally { setBusy(false) }
  }
  return (
    <Modal title="Restore from recovery phrase" onClose={onClose}>
      <p className="muted">Acceptance test: kill the machine, restore on new hardware from the phrase, killer workflow resumes.</p>
      <div className="field"><label>Enter your 12-word recovery phrase</label>
        <textarea rows={2} value={words} onChange={(e) => setWords(e.target.value)} placeholder="river stone maple …" /></div>
      <button className="btn" style={{ width: '100%' }} onClick={go} disabled={!words.trim() || busy}>{busy ? 'Decrypting…' : 'Decrypt & restore'}</button>
      {result && (
        <div className="card mt" style={{ background: result.status === 'restored' ? 'var(--success-bg)' : 'var(--danger-bg)',
          border: `1px solid ${result.status === 'restored' ? 'var(--success-border)' : 'var(--danger-border)'}` }}>
          {result.status === 'restored'
            ? <><strong style={{ color: 'var(--success-fg)' }}>✓ Decrypted & verified</strong>
                <div style={{ fontSize: 13, marginTop: 6 }}>Recovered {result.recovered.leads} leads, {result.recovered.properties} properties,
                  {result.recovered.interactions} conversations, {result.recovered.agents} agents.</div>
                <div className="muted mt" style={{ fontSize: 12 }}>{result.note}</div></>
            : <strong style={{ color: 'var(--danger-fg)' }}>✕ {result.reason}</strong>}
        </div>
      )}
    </Modal>
  )
}
