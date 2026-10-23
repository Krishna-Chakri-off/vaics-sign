import { createContext, useContext, useEffect, useState } from 'react'
import api, { getToken, setToken } from './api'
import { setLang } from './i18n'

const Ctx = createContext(null)
export const useAuth = () => useContext(Ctx)

// role -> permissions mirror of backend app/core/permissions.py (UI only; the API enforces)
const PERMS = {
  'users.manage': ['org_admin'], 'billing.manage': ['org_admin', 'billing_admin'], 'settings.manage': ['org_admin'], 'integrations.manage': ['org_admin'],
  'templates.share': ['org_admin', 'template_manager'], 'templates.create': ['org_admin', 'template_manager', 'sender'],
  'envelopes.send': ['org_admin', 'sender', 'template_manager'], 'bulk.send': ['org_admin', 'sender', 'template_manager'],
  'envelopes.view_all': ['org_admin', 'auditor'], 'audit.view': ['org_admin', 'auditor', 'sender', 'template_manager'],
  'privacy.manage': ['org_admin'], 'reports.view': ['org_admin', 'auditor', 'sender', 'template_manager', 'billing_admin'],
}
export const ROLE_LABEL = { org_admin: 'Organization admin', billing_admin: 'Billing admin', sender: 'Sender', template_manager: 'Template manager', auditor: 'Auditor', viewer: 'Viewer', platform_admin: 'VAICS platform admin' }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!getToken())
  const refresh = () => api.get('/auth/me').then((r) => { setUser(r.data); setLang(r.data.language) })
  useEffect(() => { if (getToken()) refresh().catch(() => setToken(null)).finally(() => setLoading(false)) }, [])
  const login = async (email, password, totp) => {
    const { data } = await api.post('/auth/login', { email, password, totp: totp || undefined })
    if (data.mfa_required) return data
    setToken(data.access_token); setUser(data.user); setLang(data.user.language)
    return data
  }
  const logout = async () => { try { await api.post('/auth/logout') } catch { /* already gone */ } setToken(null); setUser(null) }
  const can = (p) => !!user && (PERMS[p] || []).includes(user.role)
  const feature = (f) => !!user?.org?.features?.[f]
  return <Ctx.Provider value={{ user, loading, login, logout, refresh, can, feature, isPlatform: user?.role === 'platform_admin' }}>{children}</Ctx.Provider>
}
