import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api, { errMsg, fmt } from '../../api'
import { PageShell, Table, Alert } from '../../components/ui'
import { SBadge, STATUS } from './common'

export default function SignDashboard() {
  const [dash, setDash] = useState(null); const [docs, setDocs] = useState([]); const [err, setErr] = useState('')
  const [q, setQ] = useState(''); const [st, setSt] = useState(''); const nav = useNavigate()
  useEffect(() => { api.get('/sign/dashboard').then((r) => setDash(r.data)).catch((e) => setErr(errMsg(e))) }, [])
  useEffect(() => { api.get('/sign/documents', { params: { q: q || undefined, status: st || undefined } }).then((r) => setDocs(r.data)).catch((e) => setErr(errMsg(e))) }, [q, st])
  const c = dash?.counts || {}
  const tiles = [['Total', dash?.total], ['Draft', c.draft], ['Awaiting signature', dash?.awaiting], ['Partially signed', c.partially_signed], ['Completed', c.completed], ['Declined', c.declined], ['Cancelled', c.cancelled], ['Expired', c.expired]]
  return (
    <PageShell title="VAICS Sign" subtitle="Upload, send, sign and track organizational documents" right={<><Link to="/vaics-sign/outbox" className="btn-secondary">Email outbox</Link><Link to="/vaics-sign/new" className="btn-accent">+ New document</Link></>}>
      <Alert>{err}</Alert>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        {tiles.map(([l, v]) => <div key={l} className="card"><div className="text-slate-500">{l}</div><div className="mt-1 text-2xl font-semibold text-deep">{v ?? '—'}</div></div>)}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-3 lg:col-span-2">
          <div className="flex flex-wrap gap-2">
            <input className="input max-w-xs" placeholder="Search title…" value={q} onChange={(e) => setQ(e.target.value)} />
            <select className="input max-w-[200px]" value={st} onChange={(e) => setSt(e.target.value)}><option value="">All statuses</option>{['draft', 'sent', 'viewed', 'partially_signed', 'completed', 'declined', 'cancelled', 'expired'].map((s) => <option key={s} value={s}>{STATUS[s][0]}</option>)}</select>
          </div>
          <Table onRow={(r) => nav(`/vaics-sign/${r.id}`)} empty="No documents yet. Upload a PDF to begin." rows={docs} cols={[
            { k: 'title', label: 'Document', render: (r) => <span className="font-medium text-deep">{r.title}</span> }, { k: 'status', label: 'Status', render: (r) => <SBadge s={r.status} /> },
            { k: 'owner', label: 'Owner' }, { k: 'r', label: 'Signatories', render: (r) => r.recipients.map((x) => x.name).join(', ') || '—' }, { k: 'updated_at', label: 'Updated', render: (r) => fmt(r.updated_at) }]} />
        </div>
        <div className="card"><h2 className="mb-2">Recent activity</h2>
          {(dash?.recent || []).map((e, i) => <Link key={i} to={`/vaics-sign/${e.document_id}`} className="block border-b border-gray-100 py-1.5 hover:bg-[#F2F8FF]"><span className="font-medium capitalize">{e.event.replace(/_/g, ' ')}</span> · {e.title}<div className="text-slate-500">{e.actor} · {fmt(e.created_at)}</div></Link>)}
          {!dash?.recent?.length && <div className="text-slate-500">No activity yet.</div>}
        </div>
      </div>
    </PageShell>)
}
