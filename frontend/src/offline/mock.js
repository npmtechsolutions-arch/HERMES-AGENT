// Offline demo mode — lets the desktop app run WITHOUT the local backend.
// When the bundled FastAPI/Postgres can't be reached (e.g. a tester's fresh
// machine), the app falls back to canned fixtures captured from a real seeded
// backend so a tester can log in and click through every page.
//
// This is TESTING-ONLY: nothing is persisted and writes are no-ops that return
// optimistic success. A banner is shown so the tester knows.
import fixtures from './fixtures.json'

export const DEMO_USER_CREDS = { email: 'user@gmail.com', password: 'user' }
export const DEMO_ADMIN_CREDS = { email: 'admin@gmail.com', password: 'admin' }

// Pattern fixtures (parameterized paths) -> regex.
const STAR = Object.keys(fixtures).filter((k) => k.includes('*'))
function starMatch(path) {
  for (const pat of STAR) {
    const re = new RegExp('^' + pat.replace(/[.*+?^${}()|[\]\\]/g, (m) => (m === '*' ? '[^/]+' : '\\' + m)).replace('\\*', '[^/]+') + '$')
    if (re.test(path)) return fixtures[pat]
  }
  return undefined
}

// Heuristic fallbacks for endpoints we didn't capture (mostly because the
// seeded DB had no rows). Keeps pages from crashing on unknown shapes.
function fallback(path) {
  const p = path.split('?')[0]
  if (/\/(activity|performance|runs|conversations|channels|history|commands|destinations|escalations|anchors|events|members)$/.test(p)) return []
  if (p === '/health/plain') return { status: 'ok', online: true }
  if (p === '/suggestions') return []
  if (p.startsWith('/universal/reskin')) return fixtures['/universal/skin'] || {}
  if (p.startsWith('/why/interaction')) return { factors: [], summary: 'Explanation needs the live backend.' }
  // detail lookups (/tasks/x, /leads/x, /comms/threads/x) — no row in demo data
  if (/^\/(tasks|leads|comms\/threads)\/[^/]+$/.test(p)) return {}
  return [] // safest default for unmatched list-style GETs
}

export function offlineGet(path) {
  if (path in fixtures) return fixtures[path]
  const noq = path.split('?')[0]
  if (noq in fixtures) return fixtures[noq]
  const star = starMatch(noq)
  if (star !== undefined) return star
  return fallback(path)
}

// Auth: accept the demo credentials offline; anything else is rejected.
export function offlineAuth(path, body) {
  const email = (body?.email || '').trim().toLowerCase()
  const pw = body?.password || ''
  if (path === '/auth/login' || path === '/auth/signup') {
    if (path === '/auth/signup' || (email === DEMO_USER_CREDS.email && pw === DEMO_USER_CREDS.password)) {
      return { token: 'offline-user', user: fixtures['__user__'] || fixtures['/auth/me'] }
    }
    const e = new Error('Demo build: sign in with user@gmail.com / user (offline mode).'); e.status = 401; throw e
  }
  if (path === '/auth/admin/login') {
    if (email === DEMO_ADMIN_CREDS.email && pw === DEMO_ADMIN_CREDS.password) {
      return { token: 'offline-admin', admin: fixtures['__admin__'] || fixtures['/admin/me'] }
    }
    const e = new Error('Demo build: sign in with admin@gmail.com / admin (offline mode).'); e.status = 401; throw e
  }
  return null
}

// Writes can't persist offline — return optimistic success so UIs proceed.
export function offlineWrite(method, path, body) {
  if (path.endsWith('/resolve')) {
    return { action: 'none', ok: false, message: 'Voice control needs the live backend (demo mode).' }
  }
  return { ok: true, id: 'offline-' + path.replace(/[^a-z0-9]/gi, '').slice(0, 8), status: 'ok',
    demo: true, message: 'Demo mode — changes are not saved.', ...(body && typeof body === 'object' ? body : {}) }
}

// Resolve any request offline. Returns the data (mirrors api.request's return).
export function offlineRequest(method, path, body) {
  if (path.startsWith('/auth/') && (path.endsWith('login') || path.endsWith('signup'))) {
    const r = offlineAuth(path, body)
    if (r) return r
  }
  if (method === 'GET') return offlineGet(path)
  return offlineWrite(method, path, body)
}
