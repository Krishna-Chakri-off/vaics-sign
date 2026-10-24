import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { errMsg, fmt, download } from '../api'
import { useAuth } from '../auth'
import { PageShell, Table, Alert, Modal, Field, SBadge, useAsync , ask } from '../components/ui'

export default function Templates() {
  const nav = useNavigate(); const { can, feature } = useAuth()
  const [q, setQ] = useState(''); const [fav, setFav] = useState(false)
  const { data, err, reload } = useAsync(() => api.get('/templates', { params: { q, favourites: fav } }).then((r) => r.data), [q, fav])
  const [use, setUse] = useState(null); const [msg, setMsg] = useState(''); const [e2, setE2] = useState('')
  const share = async (t, sharing) => { try { await api.put(`/templates/${t.id}`, { sharing }); reload() } catch (e) { setE2(errMsg(e)) } }
  return (
    <PageShell title="Templates" subtitle="Reusable documents, roles, fields and messages. Save any envelope as a template from its page.">
      {!feature('templates') && <Alert kind="warn">Templates are not included in your plan. Upgrade in Plan & billing.</Alert>}
      <div className="flex gap-2"><input className="input max-w-sm" placeholder="Search templates" onKeyDown={(e) => e.key === 'Enter' && setQ(e.target.value)} /><label className="flex items-center gap-1"><input type="checkbox" checked={fav} onChange={(e) => setFav(e.target.checked)} /> Favourites</label></div>
      <Alert>{err || e2}</Alert><Alert kind="ok">{msg}</Alert>
      <Table rows={data || []} empty="No templates yet." cols={[
        { label: '★', render: (t) => <button onClick={async () => { await api.post(`/templates/${t.id}/favourite`); reload() }} className={t.favourite ? 'text-[#E6007E]' : 'text-slate-300'} aria-label="Favourite">★</button> },
        { label: 'Name', render: (t) => <div><b>{t.name}</b><div className="text-slate-400">{t.description}</div></div> },
        { label: 'Roles', render: (t) => t.roles.map((r) => r.role).join(' → ') },
        { label: 'Docs', render: (t) => t.documents.length }, { label: 'Version', k: 'version' },
        { label: 'Sharing', render: (t) => can('templates.share') ? <select className="input !w-auto" value={t.sharing} onChange={(e) => share(t, e.target.value)}><option value="private">Private</option><option value="group">Group</option><option value="org">Organization</option></select> : t.sharing },
        { label: 'Updated', render: (t) => fmt(t.updated_at) },
        { label: '', render: (t) => <div className="flex gap-1"><button className="btn-accent" onClick={() => setUse(t)}>Use</button>
          {can('bulk.send') && <button className="btn-secondary" onClick={() => nav(`/bulk?template=${t.id}`)}>Bulk</button>}
          {can('templates.share') && <button className="btn-secondary" onClick={async () => { const name = prompt('PowerForm name', t.name); if (!name) return; try { const r = await api.post('/powerforms', { template_id: t.id, name }); setMsg(`PowerForm created: ${r.data.url}`) } catch (e) { setE2(errMsg(e)) } }}>PowerForm</button>}
          {can('templates.share') && <button className="btn-secondary" onClick={async () => { if (await ask('Archive this template?')) { await api.put(`/templates/${t.id}`, { archived: true }); reload() } }}>Archive</button>}</div> },
      ]} />
      {use && <UseModal t={use} onClose={() => setUse(null)} onDone={(env) => nav(`/envelopes/${env.id}`)} />}
    </PageShell>)
}

function UseModal({ t, onClose, onDone }) {
  const [roles, setRoles] = useState(t.roles.map((r) => ({ name: r.locked ? r.name : '', email: r.locked ? r.email : '', phone: '' })))
  const prefillable = t.fields.filter((f) => f.label && ['text', 'number', 'date', 'company', 'title'].includes(f.type))
  const [prefill, setPrefill] = useState({}); const [err, setErr] = useState('')
  const go = async (send) => { setErr(''); try { const r = await api.post('/templates/use', { template_ids: [t.id], roles, prefill, send }); onDone(r.data) } catch (e) { setErr(errMsg(e)) } }
  return <Modal title={`Use template: ${t.name}`} onClose={onClose} footer={<><button className="btn-secondary" onClick={() => go(false)}>Create draft</button><button className="btn-accent" onClick={() => go(true)}>Send now</button></>}>
    <Alert>{err}</Alert>
    {t.roles.map((r, i) => <div key={i} className="space-y-1 border border-gray-200 p-2"><b>Step {r.order} · {r.role}</b>{r.locked ? <div className="text-slate-500">{r.name} &lt;{r.email}&gt; (locked)</div> : <>
      <input className="input" placeholder="Name" value={roles[i].name} onChange={(e) => setRoles(roles.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
      <input className="input" placeholder="Email" value={roles[i].email} onChange={(e) => setRoles(roles.map((x, j) => j === i ? { ...x, email: e.target.value } : x))} /></>}</div>)}
    {prefillable.map((f) => <Field key={f.label} label={`Prefill: ${f.label}`}><input className="input" value={prefill[f.label] || ''} onChange={(e) => setPrefill({ ...prefill, [f.label]: e.target.value })} /></Field>)}
  </Modal>
}

export function Bulk() {
  const sp = new URLSearchParams(location.search)
  const { data: tpls } = useAsync(() => api.get('/templates').then((r) => r.data))
  const { data: jobs, reload } = useAsync(() => api.get('/bulk').then((r) => r.data))
  const [tid, setTid] = useState(sp.get('template') || ''); const [name, setName] = useState('Bulk send'); const [job, setJob] = useState(null); const [err, setErr] = useState('')
  const t = (tpls || []).find((x) => String(x.id) === String(tid))
  const sample = t ? [t.roles.flatMap((r, i) => r.locked ? [] : [`role${i + 1}_name`, `role${i + 1}_email`]).concat(t.fields.filter((f) => f.label).map((f) => f.label)).join(',')].join('\n') : ''
  const validate = async (file) => { setErr(''); const fd = new FormData(); fd.append('template_id', tid); fd.append('name', name); fd.append('file', file); try { setJob((await api.post('/bulk', fd)).data); reload() } catch (e) { setErr(errMsg(e)) } }
  const send = async () => { try { setJob((await api.post(`/bulk/${job.id}/send`)).data); reload() } catch (e) { setErr(errMsg(e)) } }
  return (
    <PageShell title="Bulk send" subtitle="Send one template to many recipients from a CSV or Excel list. Each row becomes its own envelope.">
      <div className="card grid gap-3 md:grid-cols-3">
        <Field label="Template"><select className="input" value={tid} onChange={(e) => setTid(e.target.value)}><option value="">Choose…</option>{(tpls || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></Field>
        <Field label="Job name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Recipient list (.csv / .xlsx)"><input type="file" accept=".csv,.xlsx" disabled={!tid} onChange={(e) => e.target.files[0] && validate(e.target.files[0])} /></Field>
        {t && <div className="md:col-span-3 text-slate-500">Expected columns: <code>{sample}</code> <button className="text-[#0D47A1]" onClick={() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([sample + '\n'], { type: 'text/csv' })); a.download = 'bulk-template.csv'; a.click() }}>Download sample</button></div>}
      </div>
      <Alert>{err}</Alert>
      {job && <div className="card space-y-2"><div className="flex items-center gap-2"><h2 className="mr-auto">{job.name}: {job.valid}/{job.total} valid · {job.sent} sent</h2><SBadge s={job.status} />
        {job.status === 'validated' && <button className="btn-accent" disabled={!job.valid} onClick={send}>Send {job.valid} envelope(s)</button>}
        <button className="btn-secondary" onClick={() => download(`/bulk/${job.id}/report.csv`, `bulk-${job.id}.csv`)}>Results CSV</button></div>
        <Table rows={job.rows.map((r) => ({ ...r, id: r.row }))} cols={[{ label: 'Row', k: 'row' }, { label: 'Data', render: (r) => Object.values(r.data).join(' · ') }, { label: 'Result', render: (r) => r.errors.length ? <span className="text-red-700">{r.errors.join('; ')}</span> : r.envelope_id ? 'Sent' : 'Valid' }]} /></div>}
      <h2>Previous jobs</h2>
      <Table rows={jobs || []} onRow={async (j) => setJob((await api.get(`/bulk/${j.id}`)).data)} cols={[{ label: 'Job', k: 'name' }, { label: 'Status', render: (j) => <SBadge s={j.status} /> }, { label: 'Rows', k: 'total' }, { label: 'Sent', k: 'sent' }, { label: 'Created', render: (j) => fmt(j.created_at) }]} />
    </PageShell>)
}

export function PowerForms() {
  const { can } = useAuth()
  const { data, err, reload } = useAsync(() => api.get('/powerforms').then((r) => r.data))
  return (
    <PageShell title="PowerForms" subtitle="Self-service signing links built from a template. The signer verifies their email before signing. Create one from Templates.">
      <Alert>{err}</Alert>
      <Table rows={data || []} empty="No PowerForms yet." cols={[{ label: 'Name', k: 'name' }, { label: 'Link', render: (f) => <a className="break-all text-[#0D47A1]" href={f.url} target="_blank" rel="noreferrer">{f.url}</a> },
        { label: 'Uses', render: (f) => `${f.uses}${f.max_uses ? ` / ${f.max_uses}` : ''}` }, { label: 'Status', render: (f) => <SBadge s={f.enabled ? 'active' : 'closed'} label={f.enabled ? 'Enabled' : 'Disabled'} /> },
        { label: 'Embed', render: (f) => <button className="btn-secondary" onClick={() => navigator.clipboard?.writeText(f.embed_html)}>Copy iframe</button> },
        { label: '', render: (f) => can('templates.share') && <button className="btn-secondary" onClick={async () => { await api.patch(`/powerforms/${f.id}`, { enabled: !f.enabled }); reload() }}>{f.enabled ? 'Disable' : 'Enable'}</button> }]} />
    </PageShell>)
}

export function Outbox() {
  const { data, err } = useAsync(() => api.get('/org/outbox').then((r) => r.data))
  const [open, setOpen] = useState(null)
  return (
    <PageShell title="Email outbox" subtitle="Every email and SMS the platform generated for your organization.">
      {data && !data.smtp_configured && <Alert kind="warn"><b>DEV EMAIL OUTBOX — NOT DELIVERED.</b> Email (SMTP / Amazon SES) is not configured, so no message below reached anyone. Links and codes are shown here for testing only.</Alert>}
      {data?.smtp_configured && <Alert kind="ok">SMTP is configured. "Accepted by SMTP" means the relay accepted the message; it does not prove inbox delivery.</Alert>}
      <Alert>{err}</Alert>
      <Table rows={data?.messages || []} onRow={setOpen} cols={[{ label: 'Time', render: (m) => fmt(m.created_at) }, { label: 'Channel', k: 'channel' }, { label: 'To', k: 'to' }, { label: 'Kind', k: 'kind' }, { label: 'Subject', k: 'subject' },
        { label: 'Code', render: (m) => m.secret ? <code className="font-bold text-[#E6007E]">{m.secret}</code> : '' }, { label: 'Delivery', render: (m) => <SBadge s={m.delivery} /> }]} />
      {open && <Modal title={open.subject} onClose={() => setOpen(null)} footer={<button className="btn-secondary" onClick={() => setOpen(null)}>Close</button>}>
        <div className="text-slate-500">To {open.to} · {fmt(open.created_at)} · {open.delivery}{open.error ? ` · ${open.error}` : ''}</div>
        <pre className="font-[inherit] whitespace-pre-wrap">{open.body}</pre>
        {open.secret && <div>Code: <code className="text-[18px] font-bold text-[#E6007E]">{open.secret}</code></div>}
        {open.link && <a className="btn-primary" href={open.link} target="_blank" rel="noreferrer">Open link</a>}
        {open.attachment && <div className="text-slate-500">Attachment: {open.attachment}</div>}
      </Modal>}
    </PageShell>)
}

export function Reports() {
  const [days, setDays] = useState(30); const [by, setBy] = useState('period')
  const { data, err } = useAsync(() => api.get('/reports/summary', { params: { days, group_by: by } }).then((r) => r.data), [days, by])
  const T = data?.total
  return (
    <PageShell title="Reports" subtitle="Volume, completion and turnaround. Sandbox envelopes are excluded." right={<button className="btn-secondary" onClick={() => download(`/reports/summary.csv?days=${days}&group_by=${by}`, 'vaics-sign-report.csv')}>Export CSV</button>}>
      <div className="flex gap-2"><select className="input !w-auto" value={days} onChange={(e) => setDays(+e.target.value)}>{[7, 30, 90, 365].map((d) => <option key={d} value={d}>Last {d} days</option>)}</select>
        <select className="input !w-auto" value={by} onChange={(e) => setBy(e.target.value)}><option value="period">By period</option><option value="user">By sender</option><option value="template">By template</option></select></div>
      <Alert>{err}</Alert>
      {T && <div className="grid grid-cols-2 gap-3 md:grid-cols-5">{[['Sent', T.sent], ['Completed', T.completed], ['Completion rate', `${T.completion_rate}%`], ['Decline rate', `${T.decline_rate}%`], ['Avg turnaround', T.avg_turnaround_hours != null ? `${T.avg_turnaround_hours} h` : '—']].map(([l, v]) => <div key={l} className="card"><div className="text-slate-500">{l}</div><div className="text-[22px] font-semibold text-[#0D47A1]">{v}</div></div>)}</div>}
      {data && <div className="card space-y-1">{data.groups.map((g) => <div key={g.key} className="grid grid-cols-[160px_1fr_60px] items-center gap-2"><span className="truncate">{g.key}</span>
        <div className="flex h-4 bg-[#D6E8FF]"><div style={{ width: `${(100 * g.completed) / Math.max(1, ...data.groups.map((x) => x.sent))}%` }} className="bg-[#0D47A1]" /><div style={{ width: `${(100 * (g.sent - g.completed)) / Math.max(1, ...data.groups.map((x) => x.sent))}%` }} className="bg-[#00B6F0]" /></div><span>{g.completed}/{g.sent}</span></div>)}
        {!data.groups.length && <p className="text-slate-500">No envelopes sent in this period.</p>}<p className="text-slate-400">Dark blue = completed, sky = other.</p></div>}
      {data && <Table rows={data.groups.map((g) => ({ ...g, id: g.key }))} cols={['key', 'sent', 'completed', 'declined', 'voided', 'expired', 'in_progress', 'completion_rate', 'avg_turnaround_hours'].map((k) => ({ k, label: k.replaceAll('_', ' ') }))} />}
    </PageShell>)
}
