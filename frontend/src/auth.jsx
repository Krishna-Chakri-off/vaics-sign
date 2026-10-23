import { createContext, useContext, useEffect, useState } from 'react'
import api from './api'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!localStorage.getItem('cms_token'))
  useEffect(() => {
    if (!localStorage.getItem('cms_token')) return
    api.get('/auth/me').then((r) => setUser(r.data)).catch(() => localStorage.removeItem('cms_token')).finally(() => setLoading(false))
  }, [])
  const login = async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('cms_token', data.access_token); setUser(data.user)
  }
  const logout = () => { localStorage.removeItem('cms_token'); setUser(null) }
  const isMgr = user && ['change_manager', 'admin'].includes(user.role)
  return <Ctx.Provider value={{ user, loading, login, logout, isMgr }}>{children}</Ctx.Provider>
}
