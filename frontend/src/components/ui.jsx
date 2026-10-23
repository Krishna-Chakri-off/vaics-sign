import { FiInbox } from 'react-icons/fi'
import { LABEL, STATE_STYLE, RISK_LABEL, RISK_STYLE } from '../constants'

export const StateBadge = ({ state }) => <span className={`inline-block border px-2 py-0.5 font-medium whitespace-nowrap ${STATE_STYLE[state] || ''}`}>{LABEL[state] || state}</span>
export const RiskBadge = ({ risk }) => <span className={`inline-block border px-2 py-0.5 font-medium whitespace-nowrap ${RISK_STYLE[risk] || 'border-slate-300'}`}>{RISK_LABEL[risk] || risk || '—'}</span>
export const TypeTag = ({ type }) => <span className={`font-medium capitalize ${type === 'emergency' ? 'text-red-600' : type === 'standard' ? 'text-green-700' : 'text-slate-700'}`}>{type}</span>

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
      <div className="w-full max-w-lg border border-gray-200 bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-gray-200 bg-deep px-4 py-2.5 font-semibold text-white">{title}</div>
        <div className="space-y-3 p-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-gray-200 px-4 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export const Field = ({ label, children, className = '' }) => <div className={className}><label className="label">{label}</label>{children}</div>
export const ReadField = ({ label, children }) => <div><div className="text-slate-500">{label}</div><div className="font-medium">{children || '—'}</div></div>
