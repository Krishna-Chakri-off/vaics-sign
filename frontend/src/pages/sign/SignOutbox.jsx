import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { errMsg, fmt } from '../../api'
import { PageShell, Alert, Table } from '../../components/ui'

const DLV = { dev_outbox: ['NOT DELIVERED (dev outbox)', 'border-amber-300 bg-amber-50 text-amber-800'], smtp_accepted: ['Accepted by SMTP server', 'border-green-200 bg-green-50 text-green-800'], smtp_failed: ['SMTP failed', 'border-red-200 bg-red-50 text-red-700'] }
export default function SignOutbox() {
  const [o, setO] = useState(null); const [err, setErr] = useState('')
  const load = () => api.get('/sign/outbox').then((r) => setO(r.data)).catch((e) => setErr(errMsg(e)))
  useEffect(() => { load() }, [])
  return (
    <PageShell title={o && !o.smtp_configured ? 'DEV EMAIL OUTBOX' : 'Email log'} subtitle="Every email VAICS Sign generated for your documents" right={<button className="btn-secondary" onClick={load}>Refresh</button>}>
      <Alert>{err}</Alert>
      {o && !o.smtp_configured && <Alert kind="warn">SMTP is not configured (SMTP_HOST empty). These emails were NOT sent to anyone. For the demo, open the signing link and use the access code shown here. Configure SMTP (e.g. Amazon SES) to deliver real emails — access codes are then never stored or shown.</Alert>}
      <Table rows={o?.emails || []} empty="No emails yet." cols={[
        { k: 'created_at', label: 'Time', render: (m) => fmt(m.created_at) }, { k: 'to', label: 'To' },
        { k: 'subject', label: 'Subject', render: (m) => <span>{m.subject}<div className="text-slate-500"><Link className="underline" to={`/vaics-sign/${m.document_id}`}>VS-{String(m.document_id).padStart(6, '0')}</Link>{m.attachment && ` · 📎 ${m.attachment}`}</div></span> },
        { k: 'link', label: 'Link', render: (m) => m.link ? <a className="break-all text-deep underline" href={m.link} target="_blank" rel="noreferrer">{m.link.length > 60 ? m.link.slice(0, 60) + '…' : m.link}</a> : '—' },
        { k: 'code', label: 'Access code', render: (m) => m.code ? <code className="text-base font-semibold tracking-widest text-magenta">{m.code}</code> : m.kind === 'access_code' ? <span className="text-slate-500">hidden</span> : '—' },
        { k: 'delivery', label: 'Delivery', render: (m) => <span className={`inline-block rounded-full border px-2 py-0.5 font-medium ${DLV[m.delivery]?.[1]}`} title={m.error || ''}>{DLV[m.delivery]?.[0] || m.delivery}</span> }]} />
    </PageShell>)
}
