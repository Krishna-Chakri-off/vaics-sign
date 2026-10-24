import axios from 'axios'

export const API_URL = import.meta.env.VITE_API_URL || '/api/v1'
const TOKEN = 'vs_token'
export const getToken = () => localStorage.getItem(TOKEN)
export const setToken = (t) => (t ? localStorage.setItem(TOKEN, t) : localStorage.removeItem(TOKEN))
const api = axios.create({ baseURL: API_URL })
// interaction feedback: the button that triggered a request shows a spinner and is blocked until it finishes
const busy = (cfg, on) => { const b = on ? (document.activeElement?.closest?.('button') || null) : cfg._btn; if (!b) return; if (on) { cfg._btn = b; b.classList.add('is-loading'); b.setAttribute('aria-busy', 'true') } else { b.classList.remove('is-loading'); b.removeAttribute('aria-busy') } }
const track = (cfg) => { if (typeof document !== 'undefined' && cfg.method && cfg.method !== 'get') busy(cfg, true); return cfg }
const done = (cfg) => cfg && busy(cfg, false)
api.interceptors.request.use((cfg) => { const t = getToken(); if (t) cfg.headers.Authorization = `Bearer ${t}`; return track(cfg) })
api.interceptors.response.use((r) => { done(r.config); return r }, (err) => {
  done(err.config)
  const url = err.config?.url || ''
  if (err.response?.status === 401 && !url.includes('/auth/login') && getToken()) { setToken(null); if (!location.pathname.startsWith('/login')) location.href = '/login?expired=1' }
  return Promise.reject(err)
})
// public (signer / verify) calls never carry the user token
export const pub = axios.create({ baseURL: API_URL })
pub.interceptors.request.use(track)
pub.interceptors.response.use((r) => { done(r.config); return r }, (e) => { done(e.config); return Promise.reject(e) })

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
