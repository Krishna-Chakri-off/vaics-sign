import { useEffect, useState } from 'react'
import { FiInbox } from 'react-icons/fi'


export function PageShell({ title, subtitle, right, children }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><h1>{title}</h1>{subtitle && <p className="mt-1 text-slate-500">{subtitle}</p>}</div>
        <div className="flex flex-wrap gap-2">{right}</div>
      </div>
      <div className="shell space-y-4">{children}</div>
    </div>
  )
}

export function Table({ cols, rows, empty = 'No records found.', onRow }) {
  return (
    <div className="overflow-x-auto border border-gray-200 bg-white shadow-sm">
      <table className="w-full border-collapse">
        <thead><tr className="thead-navy">{cols.map((c) => <th key={c.k || c.label} className="th">{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? i} className={`trow ${onRow ? 'cursor-pointer' : ''}`} onClick={onRow ? () => onRow(r) : undefined}>
              {cols.map((c) => <td key={c.k || c.label} className="td">{c.render ? c.render(r) : (r[c.k] ?? '—')}</td>)}
            </tr>
          ))}
          {rows.length === 0 && <tr><td colSpan={cols.length} className="bg-white py-12 text-center text-slate-500"><span className="mx-auto mb-2 flex h-10 w-10 items-center justify-center bg-[#E6007E]/10 text-magenta"><FiInbox size={20} /></span>{empty}</td></tr>}
        </tbody>
      </table>
    </div>
  )
}

export const Alert = ({ kind = 'error', children }) => children ? (
  <div className={`border px-4 py-2.5 font-medium ${kind === 'error' ? 'border-red-200 bg-red-50 text-red-800' : kind === 'warn' ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-green-200 bg-green-50 text-green-800'}`}>{children}</div>
) : null

export const Section = ({ title, right, children }) => (
  <div className="card"><div className="mb-3 flex items-center justify-between gap-2"><h2>{title}</h2>{right}</div>{children}</div>
)

export function Modal({ title, onClose, children, footer }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto border border-gray-200 bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-gray-200 bg-deep px-4 py-2.5 font-semibold text-white">{title}</div>
        <div className="space-y-3 p-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-gray-200 px-4 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export const Field = ({ label, children, className = '' }) => <div className={className}><label className="label">{label}</label>{children}</div>
export const ReadField = ({ label, children }) => <div><div className="text-slate-500">{label}</div><div className="font-medium">{children || '—'}</div></div>

export const STATUS = {
  draft: ['Draft', 'border-slate-300 bg-slate-50 text-slate-700'], sent: ['Sent', 'border-blue-200 bg-blue-50 text-[#0D47A1]'], delivered: ['Opened', 'border-sky-200 bg-sky-50 text-sky-700'],
  partially_signed: ['Partially signed', 'border-amber-200 bg-amber-50 text-amber-800'], completed: ['Completed', 'border-green-200 bg-green-50 text-green-800'],
  declined: ['Declined', 'border-red-200 bg-red-50 text-red-700'], voided: ['Voided', 'border-slate-300 bg-slate-100 text-slate-600'], expired: ['Expired', 'border-slate-300 bg-slate-100 text-slate-600'],
  created: ['Waiting', 'border-slate-300 text-slate-600'], authenticated: ['Authenticated', 'border-sky-200 bg-sky-50 text-sky-700'],
  pending: ['Pending', 'border-slate-300 text-slate-600'], validated: ['Validated', 'border-sky-200 bg-sky-50 text-sky-700'], done: ['Done', 'border-green-200 bg-green-50 text-green-800'],
  delivered_wh: ['Delivered', 'border-green-200 bg-green-50 text-green-800'], retrying: ['Retrying', 'border-amber-200 bg-amber-50 text-amber-800'], failed: ['Failed', 'border-red-200 bg-red-50 text-red-700'],
  open: ['Open', 'border-amber-200 bg-amber-50 text-amber-800'], paid: ['Paid', 'border-green-200 bg-green-50 text-green-800'], trial: ['Trial', 'border-sky-200 bg-sky-50 text-sky-700'],
  active: ['Active', 'border-green-200 bg-green-50 text-green-800'], past_due: ['Past due', 'border-red-200 bg-red-50 text-red-700'], restricted: ['Restricted', 'border-red-200 bg-red-50 text-red-700'],
  suspended: ['Suspended', 'border-red-200 bg-red-50 text-red-700'], closed: ['Closed', 'border-slate-300 bg-slate-100 text-slate-600'], dev_outbox: ['Dev outbox (not sent)', 'border-amber-200 bg-amber-50 text-amber-800'],
  accepted: ['Accepted by SMTP', 'border-green-200 bg-green-50 text-green-800'],
}
export const SBadge = ({ s, label }) => <span className={`round inline-block border px-2 py-0.5 font-medium whitespace-nowrap ${STATUS[s]?.[1] || 'border-slate-300'}`}>{label || STATUS[s]?.[0] || s}</span>
export const COLORS = ['#0D47A1', '#E6007E', '#00B6F0', '#7C3AED', '#059669', '#B45309']
export const Tabs = ({ tabs, value, onChange }) => (
  <div className="flex flex-wrap gap-0 border-b border-[#B8D0E8]">{tabs.map(([k, l]) => (
    <button key={k} onClick={() => onChange(k)} className={`-mb-px border-b-2 px-3 py-2 font-medium ${value === k ? 'border-[#E6007E] text-[#0D47A1]' : 'border-transparent text-slate-600 hover:text-[#0D47A1]'}`}>{l}</button>))}</div>
)
export const Stat = ({ label, value, hint, onClick }) => (
  <button onClick={onClick} className="card text-left hover:border-[#0D47A1]"><div className="text-slate-500">{label}</div><div className="mt-1 text-[22px] font-semibold text-[#0D47A1]">{value}</div>{hint && <div className="text-slate-400">{hint}</div>}</button>
)
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, err: '', loading: true })
  const run = () => { setState((s) => ({ ...s, loading: true })); return fn().then((data) => setState({ data, err: '', loading: false })).catch((e) => setState({ data: null, err: e?.response?.data?.detail?.message || e?.response?.data?.detail || e.message, loading: false })) }
  useEffect(() => { run() }, deps) // eslint-disable-line
  return { ...state, reload: run }
}
