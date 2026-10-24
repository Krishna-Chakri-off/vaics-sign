import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import api, { errMsg, fmt } from '../api'
import { useAuth } from '../auth'
import { PageShell, Table, SBadge, Alert, Tabs } from '../components/ui'

const STATUSES = [['', 'Any status'], ['draft', 'Draft'], ['waiting_for_others', 'Waiting for others'], ['sent', 'Sent'], ['delivered', 'Opened'], ['partially_signed', 'Partially signed'],
  ['completed', 'Completed'], ['declined', 'Declined'], ['voided', 'Voided'], ['expired', 'Expired'], ['expiring_soon', 'Expiring soon']]

export default function Envelopes() {
  const nav = useNavigate(); const { can } = useAuth(); const [sp, setSp] = useSearchParams()
  const [data, setData] = useState({ items: [], total: 0 }); const [err, setErr] = useState(''); const [sel, setSel] = useState([]); const [msg, setMsg] = useState('')
  const q = Object.fromEntries(sp.entries()); const box = q.box || 'all'; const page = +(q.page || 1)
  const set = (k, v) => { const n = { ...q, [k]: v, page: k === 'page' ? v : 1 }; if (!v) delete n[k]; setSp(n) }
  const load = () => api.get('/envelopes', { params: { ...q, page_size: 25 } }).then((r) => setData(r.data)).catch((e) => setErr(errMsg(e)))
  useEffect(() => { load() }, [sp]) // eslint-disable-line
  const bulk = async (action) => {
    const reason = action === 'void' ? prompt('Reason for voiding the selected envelopes?') : ''
    if (action === 'void' && !reason) return
    try { const r = await api.post('/envelopes-bulk-action', { envelope_ids: sel, action, reason }); setMsg(`${r.data.done} envelope(s) processed${r.data.errors.length ? `, ${r.data.errors.length} skipped` : ''}`); setSel([]); load() } catch (e) { setErr(errMsg(e)) }
  }
  return (
    <PageShell title="Documents" subtitle={`${data.total} document${data.total === 1 ? '' : 's'}`} right={can('envelopes.send') && <Link className="btn-primary" to="/envelopes/new">+ New document</Link>}>
      <Tabs value={box} onChange={(v) => set('box', v === 'all' ? '' : v)} tabs={[['all', 'All I can see'], ['mine', 'Sent by me'], ['waiting_for_me', 'Waiting for me'], ['shared', 'Shared with my groups']]} />
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
        <input id="list-search" className="input lg:col-span-2" placeholder="Search title, ID, recipient, document text…" defaultValue={q.q || ''} onKeyDown={(e) => e.key === 'Enter' && set('q', e.target.value)} />
        <select className="input" value={q.status || ''} onChange={(e) => set('status', e.target.value)}>{STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <input className="input" placeholder="Recipient name/email" defaultValue={q.recipient || ''} onKeyDown={(e) => e.key === 'Enter' && set('recipient', e.target.value)} />
        <input className="input" type="date" value={q.date_from || ''} onChange={(e) => set('date_from', e.target.value)} title="Created from" />
        <select className="input" value={q.sort || '-updated_at'} onChange={(e) => set('sort', e.target.value)}>
          {[['-updated_at', 'Last updated'], ['-created_at', 'Newest'], ['created_at', 'Oldest'], ['title', 'Title A–Z'], ['expires_at', 'Expiry']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
      </div>
      <Alert>{err}</Alert><Alert kind="ok">{msg}</Alert>
      {sel.length > 0 && <div className="flex items-center gap-2"><b>{sel.length} selected</b><button className="btn-secondary" onClick={() => bulk('remind')}>Send reminders</button><button className="btn-danger" onClick={() => bulk('void')}>Void</button></div>}
      <Table rows={data.items} onRow={(e) => nav(`/envelopes/${e.id}`)} empty="No envelopes match these filters."
        cols={[
          { label: '', render: (e) => <input type="checkbox" checked={sel.includes(e.id)} onClick={(ev) => ev.stopPropagation()} onChange={(ev) => setSel(ev.target.checked ? [...sel, e.id] : sel.filter((x) => x !== e.id))} /> },
          { label: 'Title', render: (e) => <div><div className="font-medium">{e.title}</div><div className="text-slate-400">{e.public_id}{e.is_sandbox ? ' · sandbox' : ''}{e.labels?.length ? ` · ${e.labels.join(', ')}` : ''}</div></div> },
          { label: 'Status', render: (e) => <SBadge s={e.status} /> },
          { label: 'Recipients', render: (e) => e.recipients.map((r) => <div key={r.id} className={r.current ? 'font-semibold text-[#0D47A1]' : ''}>{r.order}. {r.name} <span className="text-slate-400">({r.status})</span></div>) },
          { label: 'Sender', render: (e) => e.owner?.name },
          { label: 'Updated', render: (e) => fmt(e.updated_at) },
          { label: 'Expires', render: (e) => fmt(e.expires_at) },
        ]} />
      <div className="flex items-center justify-end gap-2">
        <button className="btn-secondary" disabled={page <= 1} onClick={() => set('page', page - 1)}>Previous</button><span>Page {page} of {Math.max(1, Math.ceil(data.total / 25))}</span>
        <button className="btn-secondary" disabled={page * 25 >= data.total} onClick={() => set('page', page + 1)}>Next</button>
      </div>
    </PageShell>
  )
}
