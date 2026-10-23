import api from '../../api'
export const STATUS = { draft: ['Draft', 'border-slate-300 bg-slate-50 text-slate-700'], sent: ['Sent', 'border-blue-200 bg-blue-50 text-[#0D47A1]'], viewed: ['Viewed', 'border-sky-200 bg-sky-50 text-sky-700'],
  partially_signed: ['Partially signed', 'border-amber-200 bg-amber-50 text-amber-800'], completed: ['Completed', 'border-green-200 bg-green-50 text-green-800'],
  declined: ['Declined', 'border-red-200 bg-red-50 text-red-700'], cancelled: ['Cancelled', 'border-slate-300 bg-slate-100 text-slate-600'], expired: ['Expired', 'border-slate-300 bg-slate-100 text-slate-600'],
  pending: ['Waiting', 'border-slate-300 text-slate-600'], signed: ['Signed', 'border-green-200 bg-green-50 text-green-800'] }
export const SBadge = ({ s }) => <span className={`inline-block rounded-full border px-2 py-0.5 font-medium whitespace-nowrap ${STATUS[s]?.[1] || ''}`}>{STATUS[s]?.[0] || s}</span>
export const SIGNER_COLORS = ['#0D47A1', '#E6007E', '#00B6F0', '#7C3AED', '#059669']
export async function openPdf(url) { const r = await api.get(url, { responseType: 'blob' }); window.open(URL.createObjectURL(r.data), '_blank') }
export async function fetchBuf(url) { const r = await api.get(url, { responseType: 'arraybuffer' }); return r.data }
