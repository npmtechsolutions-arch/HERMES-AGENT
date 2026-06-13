// Thin API client for the HERMUS Cloud + Local Core API.
// In the Electron desktop app the UI is served statically, so it calls the
// local core service at an absolute address (exposed by the preload bridge).
import { offlineRequest } from './offline/mock'

// API base resolution order:
//  1. Desktop app  → the local core service address from the preload bridge.
//  2. VITE_API_URL → a hosted backend (set at build time for web deploys, e.g.
//     https://hermes-agent-hw8v.onrender.com/api/v1).
//  3. /api/v1      → same-origin (local dev with the Vite proxy).
const BASE = (typeof window !== 'undefined' && window.hermus?.apiBase)
  || import.meta.env.VITE_API_URL
  || '/api/v1'
export const IS_DESKTOP = typeof window !== 'undefined' && !!window.hermus?.isElectron

// Offline demo mode: once the backend is found unreachable on desktop (or forced
// via localStorage), serve canned fixtures so the app stays usable for testers.
let OFFLINE = typeof window !== 'undefined' && localStorage.getItem('hermus_offline') === '1'
export function isOffline() { return OFFLINE }
function goOffline() {
  if (!OFFLINE) {
    OFFLINE = true
    try { localStorage.setItem('hermus_offline', '1') } catch {}
    try { window.dispatchEvent(new Event('hermus-offline')) } catch {}
  }
}

export function getToken() {
  return localStorage.getItem('hermus_token')
}
export function getKind() {
  return localStorage.getItem('hermus_kind')
}
export function setSession(token, kind) {
  localStorage.setItem('hermus_token', token)
  localStorage.setItem('hermus_kind', kind)
}
export function clearSession() {
  localStorage.removeItem('hermus_token')
  localStorage.removeItem('hermus_kind')
}

async function request(method, path, body) {
  // Already known offline → serve the demo fixtures without hitting the network.
  if (OFFLINE) return offlineRequest(method, path, body)

  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  let res
  try {
    res = await fetch(BASE + path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (netErr) {
    // Connection refused / DNS / offline. In the desktop app this means the
    // bundled backend isn't running — fall back to offline demo mode.
    if (IS_DESKTOP) { goOffline(); return offlineRequest(method, path, body) }
    throw netErr
  }
  const text = await res.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : data
    const err = new Error((detail && detail.message) || `HTTP ${res.status}`)
    err.status = res.status
    err.detail = detail
    throw err
  }
  return data
}

export const api = {
  get: (p) => request('GET', p),
  post: (p, b) => request('POST', p, b),
  patch: (p, b) => request('PATCH', p, b),
  del: (p) => request('DELETE', p),
}

// WebSocket for live events (agent.status, task.status_changed, approval.*)
export function openEvents(onMessage) {
  const token = getToken()
  if (!token || OFFLINE) return null
  // Derive the WS endpoint from a hosted API URL when one is configured, else
  // fall back to same-origin (local dev).
  let wsBase = (typeof window !== 'undefined' && window.hermus?.wsBase) || ''
  if (!wsBase && import.meta.env.VITE_API_URL) {
    wsBase = import.meta.env.VITE_API_URL.replace(/^http/, 'ws').replace(/\/api\/v1\/?$/, '/ws/v1/events')
  }
  if (!wsBase) wsBase = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/v1/events`
  const ws = new WebSocket(`${wsBase}?token=${token}`)
  ws.onmessage = (e) => {
    try { onMessage(JSON.parse(e.data)) } catch {}
  }
  return ws
}
