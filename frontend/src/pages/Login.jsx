import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { IS_DESKTOP } from '../api'

export default function Login() {
  const { login, adminLogin } = useAuth()
  const nav = useNavigate()
  const [tab, setTab] = useState('user')
  const [email, setEmail] = useState('user@gmail.com')
  const [password, setPassword] = useState('user')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  const switchTab = (t) => {
    setTab(t); setErr('')
    if (t === 'admin') { setEmail('admin@gmail.com'); setPassword('admin') }
    else { setEmail('user@gmail.com'); setPassword('user') }
  }

  const goUser = async () => {
    // First sign-in on this device → run the install/overview (which installs the
    // local runtime + required models), then the dashboard. Desktop-only: the
    // install screen drives the local Ollama runtime, independent of the backend.
    let firstRun = true
    try { firstRun = localStorage.getItem('hermus_firstrun_done') !== '1' } catch {}
    nav(firstRun && IS_DESKTOP ? '/welcome' : '/')
  }

  const submit = async (e) => {
    e.preventDefault()
    setErr(''); setBusy(true)
    try {
      if (tab === 'admin') { await adminLogin(email, password); nav('/admin') }
      else { await login(email, password); await goUser() }
    } catch (e) {
      setErr(e.message || 'Login failed')
    } finally { setBusy(false) }
  }

  // Testing: enter the app as the demo account without typing credentials.
  // Uses the real backend if it's up, or offline demo mode if it isn't.
  const skipLogin = async () => {
    setErr(''); setBusy(true)
    try { await login('user@gmail.com', 'user'); await goUser() }
    catch (e) { setErr(e.message || 'Could not start the demo') }
    finally { setBusy(false) }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="brand">
          <div className="logo" />
          <h1>HERMUS</h1>
        </div>
        <p className="tagline">A company, not a chatbot. Autonomy you can govern — by voice, verifiably private.</p>

        <div className="tabs">
          <button className={tab === 'user' ? 'active' : ''} onClick={() => switchTab('user')}>
            Account Owner
          </button>
          <button className={tab === 'admin' ? 'active' : ''} onClick={() => switchTab('admin')}>
            Product Admin
          </button>
        </div>

        {err && <div className="error-box">{err}</div>}
        <form onSubmit={submit}>
          <div className="field">
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoFocus />
          </div>
          <div className="field">
            <label>Password</label>
            <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" />
          </div>
          <button className="btn" style={{ width: '100%' }} disabled={busy}>
            {busy ? 'Signing in…' : tab === 'admin' ? 'Sign in to Admin Console' : 'Sign in'}
          </button>
        </form>

        {tab === 'user' && (
          <>
            <div className="or-sep" style={{ textAlign: 'center', margin: '14px 0 10px', color: 'var(--muted)', fontSize: 12 }}>
              <span>or</span>
            </div>
            <button className="btn secondary" style={{ width: '100%' }} disabled={busy} onClick={skipLogin}>
              Continue without signing in →
            </button>
            <p className="muted" style={{ fontSize: 11.5, textAlign: 'center', marginTop: 6 }}>
              For testing — explore the full app as a demo account.
            </p>
          </>
        )}

        <div className="demo-creds">
          <div><strong>Demo logins</strong></div>
          <div className="mt">Account Owner — <code>user@gmail.com</code> / <code>user</code></div>
          <div>Product Admin — <code>admin@gmail.com</code> / <code>admin</code></div>
        </div>
      </div>
    </div>
  )
}
