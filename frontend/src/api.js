import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
const api = axios.create({ baseURL: API_URL })
api.interceptors.request.use((cfg) => { const t = localStorage.getItem('cms_token'); if (t) cfg.headers.Authorization = `Bearer ${t}`; return cfg })
api.interceptors.response.use((r) => r, (err) => {
  if (err.response?.status === 401 && !err.config.url.includes('/auth/login')) { localStorage.removeItem('cms_token'); if (location.pathname !== '/login') location.href = '/login' }
  return Promise.reject(err)
})
export const errMsg = (e) => { const d = e?.response?.data?.detail; return Array.isArray(d) ? d.map((x) => `${x.loc?.slice(-1)[0]}: ${x.msg}`).join('; ') : d || e?.message || 'Something went wrong' }
export const parseDate = (s) => (s ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + 'Z') : null) // API returns naive UTC
export const fmt = (s) => (s ? parseDate(s).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—')
export const fmtDate = (s) => (s ? parseDate(s).toLocaleDateString([], { dateStyle: 'medium' }) : '—')
export const toLocalInput = (s) => { if (!s) return ''; const d = parseDate(s); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16) }
export const fromLocalInput = (v) => (v ? new Date(v).toISOString() : null)
export default api
