import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || '/api/v1'
const TOKEN = 'vs_token'
export const getToken = () => localStorage.getItem(TOKEN)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN, t) : localStorage.removeItem(TOKEN))
const api = axios.create({ baseURL: API_URL })
api.interceptors.request.use((cfg) => { const t = getToken(); if (t) cfg.headers.Authorization = `Bearer ${t}`; return cfg })
api.interceptors.response.use((r) => r, (err) => {
  const url = err.config?.url || ''
  if (err.response?.status === 401 && !url.includes('/auth/login') && getToken()) { setToken(null); if (!location.pathname.startsWith('/login')) location.href = '/login?expired=1' }
  return Promise.reject(err)
})
// public (signer / powerform / verify) calls never carry the user token
export const pub = axios.create({ baseURL: API_URL })

export const errMsg = (e) => {
  const d = e?.response?.data?.detail
  if (Array.isArray(d)) return d.map((x) => `${x.loc?.slice(-1)[0]}: ${x.msg}`).join('; ')
  if (d && typeof d === 'object') return d.message || d.code || JSON.stringify(d)
  return d || e?.message || 'Something went wrong'
}
export const errCode = (e) => e?.response?.data?.detail?.code
export const parseDate = (s) => (s ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + 'Z') : null) // API returns naive UTC
export const fmt = (s) => (s ? parseDate(s).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—')
export const fmtDate = (s) => (s ? parseDate(s).toLocaleDateString([], { dateStyle: 'medium' }) : '—')
export const fmtIST = (s) => (s ? `${parseDate(s).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' })} IST` : '—')
export async function download(url, name) {
  const r = await api.get(url, { responseType: 'blob' })
  const a = document.createElement('a'); a.href = URL.createObjectURL(r.data); a.download = name || ''; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 5000)
}
export async function openBlob(url) { const r = await api.get(url, { responseType: 'blob' }); window.open(URL.createObjectURL(r.data), '_blank') }
export async function fetchBuf(url, client = api, headers = {}) { const r = await client.get(url, { responseType: 'arraybuffer', headers }); return r.data }
export default api
