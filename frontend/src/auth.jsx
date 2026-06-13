import { createContext, useContext, useEffect, useState } from 'react'
import { api, clearSession, getKind, getToken, setSession } from './api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [admin, setAdmin] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = getToken()
    const kind = getKind()
    if (!token) { setLoading(false); return }
    const load = async () => {
      try {
        if (kind === 'admin') {
          const a = await api.get('/admin/me')
          setAdmin(a)
        } else {
          const u = await api.get('/auth/me')
          setUser(u)
        }
      } catch {
        clearSession()
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const login = async (email, password) => {
    const r = await api.post('/auth/login', { email, password })
    setSession(r.token, 'user')
    setUser(r.user)
    setAdmin(null)
    return r
  }
  const adminLogin = async (email, password) => {
    const r = await api.post('/auth/admin/login', { email, password })
    setSession(r.token, 'admin')
    setAdmin(r.admin)
    setUser(null)
    return r
  }
  const signup = async (payload) => {
    const r = await api.post('/auth/signup', payload)
    setSession(r.token, 'user')
    setUser(r.user)
    return r
  }
  const logout = () => {
    clearSession()
    setUser(null)
    setAdmin(null)
  }

  return (
    <AuthCtx.Provider value={{ user, admin, loading, login, adminLogin, signup, logout }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)
