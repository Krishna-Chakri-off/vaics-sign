import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import api, { errMsg, fmt, fmtIST, download, openBlob, fetchBuf } from '../api'
import { useAuth } from '../auth'
import { PageShell, Alert, Table, SBadge, Section, Modal, Field, COLORS, Tabs , ask } from '../components/ui'
import PdfPages from '../components/PdfPages'
import EnvelopeEditor from './EnvelopeEditor'

export function EnvelopeNew() {
  const nav = useNavigate(); const [title, setTitle] = useState('Consulting Agreement'); const [err, setErr] = useState('')
  const create = async (e) => { e.preventDefault(); try { const r = await api.post('/envelopes', { title }); nav(`/envelopes/${r.data.id}`) } catch (ex) { setErr(errMsg(ex)) } }
  return (
    <PageShell title="New envelope" subtitle="Upload documents, add recipients in order, place fields, then Generate." right={<Link className="btn-secondary" to="/templates">Start from a template</Link>}>
      <Alert>{err}</Alert>
      <form onSubmit={create} className="card max-w-xl space-y-3">
        <Field label="Title"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus /></Field>
        <button className="btn-accent">Create draft</button>
      </form>
    </PageShell>)
}

export default function EnvelopeDetail() {
  const { id } = useParams(); const nav = useNavigate(); const { user, can } = useAuth()
  const [env, setEnv] = useState(null); const [err, setErr] = useState(''); const [ok, setOk] = useState(''); const [tab, setTab] = useState('document')
  const [audit, setAudit] = useState(null); const [buf, setBuf] = useState(null); const [doc, setDoc] = useState(null); const [modal, setModal] = useState(null)
  const load = (msg) => api.get(`/envelopes/${id}`).then((r) => { setEnv(r.data); if (typeof msg === 'string') setOk(msg); if (!doc && r.data.documents[0]) setDoc(r.data.documents[0].id) }).catch((e) => setErr(errMsg(e)))
  useEffect(() => { load() }, [id]) // eslint-disable-line
  useEffect(() => { if (env && env.status !== 'draft' && can('audit.view')) api.get(`/envelopes/${id}/audit`).then((r) => setAudit(r.data)).catch(() => {}) }, [env?.status, env?.updated_at]) // eslint-disable-line
  useEffect(() => { if (env && env.status !== 'draft' && doc && !env.purged_at) fetchBuf(`/envelopes/${id}/documents/${doc}/file`).then(setBuf).catch(() => {}) }, [doc, env?.status]) // eslint-disable-line
  if (!env) return <Alert>{err || 'Loading…'}</Alert>
  const act = async (fn, msg) => { setErr(''); setOk(''); try { const r = await fn(); setModal(null); await load(); setOk(typeof msg === 'function' ? msg(r.data) : msg); return true } catch (e) { setErr(errMsg(e)); return false } }
  const open = ['sent', 'delivered', 'partially_signed'].includes(env.status)
  const mine = env.owner?.id === user.id || user.role === 'org_admin'
  const header = (
    <span>{env.public_id} · sender {env.owner?.name} · <SBadge s={env.status} />{env.legal_hold && <b className="ml-2 text-red-700">LEGAL HOLD</b>}</span>)
  if (env.status === 'draft') return (
    <PageShell title={env.title} subtitle={header} right={<><Link className="btn-secondary" to="/outbox">Email outbox</Link><button className="btn-danger" onClick={async () => await ask('Delete this draft?') && act(() => api.delete(`/envelopes/${id}`), 'Deleted').then((ok2) => ok2 && nav('/envelopes'))}>Delete draft</button></>}>
      <EnvelopeEditor env={env} reload={load} />
    </PageShell>)
  const fieldsOf = (rid) => env.fields.filter((f) => f.recipient_id === rid)
  const ridx = Object.fromEntries(env.recipients.map((r, i) => [r.id, i]))
  const overlay = (page) => env.fields.filter((f) => f.document_id === doc && f.page === page).map((f) => (
    <div key={f.id} className="absolute border-2 bg-white/70 p-0.5 text-[9px]" style={{ left: `${f.x * 100}%`, top: `${f.y * 100}%`, width: `${f.w * 100}%`, height: `${f.h * 100}%`, borderColor: f.signed_at ? '#059669' : COLORS[ridx[f.recipient_id] % COLORS.length] }}>
      <b>{f.type}</b> · {env.recipients[ridx[f.recipient_id]]?.name}{f.signed_at ? ` ✓ ${f.type === 'signature' ? `reason: ${f.reason || '—'}` : f.value || ''}` : ''}
    </div>))
  return (
    <PageShell title={env.title} subtitle={header} right={<>
      {env.status === 'completed' && !env.purged_at && <><button className="btn-accent" onClick={() => download(`/envelopes/${id}/completed`, `${env.public_id}-signed.pdf`)}>Signed PDF + certificate</button>
        <button className="btn-secondary" onClick={() => openBlob(`/envelopes/${id}/certificate`)}>Certificate</button>
        <button className="btn-secondary" onClick={() => download(`/envelopes/${id}/evidence`, `${env.public_id}-evidence.zip`)}>Evidence package</button></>}
      {open && mine && <><button className="btn-secondary" onClick={() => act(() => api.post(`/envelopes/${id}/remind`), (d) => `Reminder sent to ${d.reminded} recipient(s)`)}>Remind</button>
        <button className="btn-secondary" onClick={() => setModal('correct')}>Correct</button><button className="btn-danger" onClick={() => setModal('void')}>Void</button></>}
      {(open || env.status === 'expired') && mine && <button className="btn-secondary" onClick={() => setModal('extend')}>Extend</button>}
      {can('envelopes.send') && <button className="btn-secondary" onClick={() => api.post(`/envelopes/${id}/duplicate`).then((r) => nav(`/envelopes/${r.data.id}`)).catch((e) => setErr(errMsg(e)))}>Duplicate</button>}
      {can('templates.create') && <button className="btn-secondary" onClick={() => setModal('template')}>Save as template</button>}
      {can('privacy.manage') && <button className="btn-secondary" onClick={() => act(() => api.post(`/envelopes/${id}/legal-hold`, { hold: !env.legal_hold }), env.legal_hold ? 'Legal hold removed' : 'Legal hold applied')}>{env.legal_hold ? 'Release hold' : 'Legal hold'}</button>}
      {!open && mine && !env.legal_hold && <button className="btn-danger" onClick={async () => await ask('Delete this envelope? Documents are purged; the audit evidence is kept.') && act(() => api.delete(`/envelopes/${id}`), 'Deleted').then((ok2) => ok2 && nav('/envelopes'))}>Delete</button>}
    </>}>
      <Alert>{err}</Alert><Alert kind="ok">{ok}</Alert>
      {env.status === 'voided' && <Alert kind="warn">Voided: {env.void_reason}</Alert>}
      {env.purged_at && <Alert kind="warn">Document content was purged on {fmt(env.purged_at)} under the retention policy. Hashes and the audit trail are retained.</Alert>}
      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <div className="space-y-4">
          <Section title="Recipients & routing">
            {env.recipients.map((r, i) => (
              <div key={r.id} className={`mb-2 border p-2 ${r.current ? 'border-[#E6007E] bg-[#F2F8FF]' : 'border-gray-200'}`}>
                <div className="flex items-center justify-between gap-2"><b style={{ color: COLORS[i % COLORS.length] }}>Step {r.order} · {r.role_name || r.type}</b><SBadge s={r.status} /></div>
                <div>{r.name} &lt;{r.email}&gt;</div>
                <div className="text-slate-500">{r.type} · auth: {r.auth_method}{r.sender_set_code ? ' (sender-set code)' : ''} · {fieldsOf(r.id).length} field(s){r.reminders_sent ? ` · ${r.reminders_sent} reminder(s)` : ''}</div>
                {r.completed_at && <div className="text-green-800">Completed {fmtIST(r.completed_at)}{r.completed_ip ? ` · IP ${r.completed_ip}` : ''}</div>}
                {r.decline_reason && <div className="text-red-700">Declined: {r.decline_reason}</div>}
                {r.code_locked && <div className="font-semibold text-red-700">Locked after too many wrong codes</div>}
                {r.current && open && mine && r.type !== 'in_person' && <button className="btn-secondary mt-1 w-full" onClick={() => setModal({ reissue: r })}>Revoke & reissue link + code</button>}
                {r.current && open && r.type === 'in_person' && r.host_user_id === user.id && <button className="btn-accent mt-1 w-full" onClick={() => setModal({ inperson: r })}>Start in-person signing</button>}
              </div>))}
            <div className="text-slate-500">CC: {env.owner?.email} receives the completed PDF and certificate.</div>
          </Section>
          <Section title="Details">
            <div className="space-y-1">
              <div>Sent: {fmtIST(env.sent_at)}</div><div>Expires: {fmtIST(env.expires_at)}</div>{env.completed_at && <div>Completed: {fmtIST(env.completed_at)}</div>}
              <div>Reminders: first after {env.reminder_first_days} day(s), then every {env.reminder_every_days}</div>
              {env.status === 'completed' && <div>Seal: <b>{{ no: 'not sealed', pades_dev_selfsigned: 'PAdES (development self-signed, not trusted)', pades: 'PAdES', pades_timestamped: 'PAdES + trusted timestamp' }[env.sealed] || env.sealed}</b></div>}
              {env.completed_sha256 && <div className="break-all">Signed PDF SHA-256: <code>{env.completed_sha256}</code></div>}
              {env.documents.map((d) => <div key={d.id} className="break-all text-slate-500">{d.name}: <code>{d.sha256.slice(0, 24)}…</code></div>)}
            </div>
          </Section>
        </div>
        <div className="space-y-3">
          <Tabs value={tab} onChange={setTab} tabs={[['document', 'Document'], can('audit.view') && ['audit', 'Audit trail'], ['emails', 'Emails']].filter(Boolean)} />
          {tab === 'document' && <div className="card overflow-x-auto bg-[#F2F8FF]">
            {env.documents.length > 1 && <div className="mb-3 flex flex-wrap gap-1">{env.documents.map((d) => <button key={d.id} className={`border px-2 py-1 ${doc === d.id ? 'border-[#0D47A1] bg-[#0D47A1] text-white' : 'border-gray-300 bg-white'}`} onClick={() => { setBuf(null); setDoc(d.id) }}>{d.name}</button>)}</div>}
            {env.purged_at ? 'Purged.' : buf ? <PdfPages data={buf} overlay={overlay} /> : 'Loading document…'}</div>}
          {tab === 'audit' && audit && <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">{audit.chain_valid ? <SBadge s="completed" label="Hash chain verified" /> : <SBadge s="declined" label={`Chain broken at event ${audit.broken_at}`} />}
              <button className="btn-secondary" onClick={() => download(`/envelopes/${id}/audit?format=csv`, `${env.public_id}-audit.csv`)}>Export CSV</button>
              <button className="btn-secondary" onClick={() => download(`/envelopes/${id}/audit?format=pdf`, `${env.public_id}-audit.pdf`)}>Export PDF</button></div>
            <Table rows={audit.events} cols={[{ label: 'Time (IST)', render: (e) => fmtIST(e.created_at) }, { label: 'Event', render: (e) => e.event.replaceAll('_', ' ') }, { label: 'Actor', k: 'actor' }, { label: 'IP', k: 'ip' },
              { label: 'Detail', render: (e) => <span className="break-all">{e.detail}</span> }, { label: 'Entry hash', render: (e) => <code title={e.entry_hash}>{e.entry_hash.slice(0, 10)}…</code> }]} />
          </div>}
          {tab === 'emails' && <EmailsFor id={id} />}
        </div>
      </div>
      {modal === 'void' && <ReasonModal title="Void envelope" label="Reason (sent to recipients)" onClose={() => setModal(null)} onOk={(reason) => act(() => api.post(`/envelopes/${id}/void`, { reason }), 'Voided. All links and codes are revoked.')} />}
      {modal === 'extend' && <ReasonModal title="Extend expiry" label="Extend by (days)" initial="30" onClose={() => setModal(null)} onOk={(d) => act(() => api.post(`/envelopes/${id}/extend`, { days: +d }), 'Expiry extended')} />}
      {modal === 'template' && <ReasonModal title="Save as template" label="Template name" initial={env.title} onClose={() => setModal(null)} onOk={(name) => act(() => api.post('/templates', { envelope_id: env.id, name, sharing: 'private' }), 'Template saved (private). Share it from Templates.')} />}
      {modal === 'correct' && <CorrectModal env={env} onClose={() => setModal(null)} onOk={(body) => act(() => api.post(`/envelopes/${id}/correct`, body), 'Corrected. Changed recipients whose turn it is were re-notified.')} />}
      {modal?.reissue && <ReasonModal title={`Reissue access for ${modal.reissue.name}`} label="Optional: your own 6–8 digit code (leave empty to email a new random code)" initial="" allowEmpty onClose={() => setModal(null)}
        onOk={(code) => act(() => api.post(`/envelopes/${id}/recipients/${modal.reissue.id}/reissue`, { access_code: code || null }), 'New link and access code issued; the previous ones are revoked.')} />}
      {modal?.inperson && <InPersonModal r={modal.inperson} onClose={() => setModal(null)} onStart={async (body) => { try { const r = await api.post(`/envelopes/${id}/recipients/${modal.inperson.id}/in-person`, body); sessionStorage.setItem(`vs_${r.data.token}`, r.data.session); nav(r.data.kiosk_url) } catch (e) { setErr(errMsg(e)); setModal(null) } }} />}
    </PageShell>)
}

function EmailsFor({ id }) {
  const [d, setD] = useState(null)
  useEffect(() => { api.get('/org/outbox', { params: { envelope_id: id } }).then((r) => setD(r.data)).catch(() => setD({ messages: [] })) }, [id])
  if (!d) return 'Loading…'
  return <Table rows={d.messages} empty="No emails for this envelope." cols={[{ label: 'Time (IST)', render: (m) => fmtIST(m.created_at) }, { label: 'To', k: 'to' }, { label: 'Kind', k: 'kind' }, { label: 'Subject', k: 'subject' }, { label: 'Delivery', render: (m) => <SBadge s={m.delivery} /> }]} />
}

export function ReasonModal({ title, label, initial = '', onClose, onOk, allowEmpty }) {
  const [v, setV] = useState(initial)
  return <Modal title={title} onClose={onClose} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!allowEmpty && !String(v).trim()} onClick={() => onOk(v)}>Confirm</button></>}>
    <Field label={label}><input className="input" value={v} onChange={(e) => setV(e.target.value)} autoFocus /></Field></Modal>
}

function CorrectModal({ env, onClose, onOk }) {
  const [rs, setRs] = useState(env.recipients.filter((r) => r.status !== 'completed').map((r) => ({ id: r.id, name: r.name, email: r.email, phone: r.phone || '' })))
  const [message, setMessage] = useState(env.message || '')
  return <Modal title="Correct envelope" onClose={onClose} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-primary" onClick={() => onOk({ message, recipients: rs })}>Save corrections</button></>}>
    <p className="text-slate-500">Only recipients who have not completed can be changed. Completed signatures are never altered.</p>
    {rs.map((r, i) => <div key={r.id} className="grid grid-cols-2 gap-1"><input className="input" value={r.name} onChange={(e) => setRs(rs.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} /><input className="input" value={r.email} onChange={(e) => setRs(rs.map((x, j) => j === i ? { ...x, email: e.target.value } : x))} /></div>)}
    <Field label="Message"><textarea className="input" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} /></Field>
  </Modal>
}

function InPersonModal({ r, onClose, onStart }) {
  const [f, setF] = useState({ id_type: 'PAN card', id_number: '', confirmed: false })
  return <Modal title={`In-person signing: ${r.name}`} onClose={onClose} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-accent" disabled={!f.confirmed} onClick={() => onStart(f)}>Hand over the device</button></>}>
    <p>Check the signer's identity document before handing over this device. Only the last 4 characters of the ID number are stored.</p>
    <Field label="ID document type"><select className="input" value={f.id_type} onChange={(e) => setF({ ...f, id_type: e.target.value })}>{['PAN card', 'Aadhaar (masked)', 'Passport', 'Driving licence', 'Voter ID', 'Employee ID', 'Other'].map((x) => <option key={x}>{x}</option>)}</select></Field>
    <Field label="ID number (optional)"><input className="input" value={f.id_number} onChange={(e) => setF({ ...f, id_number: e.target.value })} /></Field>
    <label className="flex gap-2"><input type="checkbox" checked={f.confirmed} onChange={(e) => setF({ ...f, confirmed: e.target.checked })} /> I verified {r.name}'s identity in person.</label>
  </Modal>
}
