import { useState } from 'react'
import api, { errMsg, fmt, download } from '../api'
import { useAuth, ROLE_LABEL } from '../auth'
import { PageShell, Table, Alert, Modal, Field, SBadge, Section, Tabs, useAsync } from '../components/ui'

const ROLES = ['org_admin', 'billing_admin', 'sender', 'template_manager', 'auditor', 'viewer']
const SCOPES = ['envelopes:read', 'envelopes:write', 'templates:read', 'templates:write', 'bulk:write', 'powerforms:write', 'users:read', 'reports:read', 'audit:read', 'webhooks:write']
const useMsg = () => { const [m, setM] = useState({ ok: '', err: '' }); const run = async (fn, ok) => { setM({ ok: '', err: '' }); try { const r = await fn(); setM({ ok: typeof ok === 'function' ? ok(r.data) : ok || 'Saved', err: '' }); return r } catch (e) { setM({ ok: '', err: errMsg(e) }) } }; return [m, run] }

export function UsersGroups() {
  const { user, feature } = useAuth()
  const users = useAsync(() => api.get('/org/users').then((r) => r.data))
  const invites = useAsync(() => api.get('/org/invitations').then((r) => r.data))
  const groups = useAsync(() => api.get('/org/groups').then((r) => r.data))
  const [m, run] = useMsg(); const [inv, setInv] = useState({ email: '', role: 'sender' }); const [grp, setGrp] = useState(null)
  const reload = () => { users.reload(); invites.reload(); groups.reload() }
  return (
    <PageShell title="Users & groups" subtitle="Invite people, assign roles and organize them into groups for shared envelopes and templates.">
      <Alert>{m.err}</Alert><Alert kind="ok">{m.ok}</Alert>
      <form className="card flex flex-wrap items-end gap-2" onSubmit={async (e) => { e.preventDefault(); if (await run(() => api.post('/org/invitations', inv), 'Invitation sent (see Email outbox in development).')) { setInv({ ...inv, email: '' }); reload() } }}>
        <Field label="Invite by email" className="min-w-64 flex-1"><input className="input" type="email" value={inv.email} onChange={(e) => setInv({ ...inv, email: e.target.value })} required /></Field>
        <Field label="Role"><select className="input" value={inv.role} onChange={(e) => setInv({ ...inv, role: e.target.value })}>{ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select></Field>
        <button className="btn-accent">Send invitation</button>
      </form>
      <Table rows={users.data || []} cols={[{ label: 'Name', render: (u) => <div><b>{u.full_name}</b><div className="text-slate-400">{u.email}</div></div> },
        { label: 'Role', render: (u) => <select className="input !w-auto" value={u.role} disabled={u.id === user.id} onChange={(e) => run(() => api.patch(`/org/users/${u.id}`, { role: e.target.value }), 'Role updated').then(reload)}>{ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}</select> },
        { label: 'Status', render: (u) => <SBadge s={u.is_active ? 'active' : 'closed'} label={u.is_active ? 'Active' : 'Deactivated'} /> }, { label: 'MFA', render: (u) => (u.mfa_enabled ? 'On' : 'Off') },
        { label: 'Last sign-in', render: (u) => fmt(u.last_login_at) },
        { label: '', render: (u) => u.id !== user.id && <div className="flex gap-1">
          <button className="btn-secondary" onClick={() => run(() => api.patch(`/org/users/${u.id}`, { is_active: !u.is_active }), u.is_active ? 'Deactivated; sessions ended' : 'Reactivated').then(reload)}>{u.is_active ? 'Deactivate' : 'Reactivate'}</button>
          <button className="btn-secondary" onClick={() => { const to = prompt(`Transfer ${u.full_name}'s envelopes and templates to (email):`); const dst = (users.data || []).find((x) => x.email === to); if (dst) run(() => api.post(`/org/users/${u.id}/transfer`, { to_user_id: dst.id }), (d) => `Transferred ${d.envelopes} envelope(s), ${d.templates} template(s)`) }}>Transfer</button>
          <button className="btn-danger" onClick={() => confirm(`Delete ${u.full_name}?`) && run(() => api.delete(`/org/users/${u.id}`), 'User deleted').then(reload)}>Delete</button></div> }]} />
      <h2>Pending invitations</h2>
      <Table rows={(invites.data || []).filter((i) => i.status === 'pending')} empty="No pending invitations." cols={[{ label: 'Email', k: 'email' }, { label: 'Role', render: (i) => ROLE_LABEL[i.role] }, { label: 'Expires', render: (i) => fmt(i.expires_at) },
        { label: '', render: (i) => <div className="flex gap-1"><button className="btn-secondary" onClick={() => run(() => api.post(`/org/invitations/${i.id}/resend`), 'Invitation resent')}>Resend</button><button className="btn-danger" onClick={() => run(() => api.delete(`/org/invitations/${i.id}`), 'Revoked').then(reload)}>Revoke</button></div> }]} />
      <div className="flex items-center justify-between"><h2>Groups</h2>{feature('groups') ? <button className="btn-secondary" onClick={() => setGrp({ name: '', member_ids: [] })}>+ New group</button> : <span className="text-slate-500">Groups need the Standard plan or higher.</span>}</div>
      <Table rows={groups.data || []} onRow={setGrp} empty="No groups." cols={[{ label: 'Group', k: 'name' }, { label: 'Members', render: (g) => g.member_ids.map((id) => (users.data || []).find((u) => u.id === id)?.full_name).filter(Boolean).join(', ') }]} />
      {grp && <Modal title={grp.id ? 'Edit group' : 'New group'} onClose={() => setGrp(null)} footer={<>{grp.id && <button className="btn-danger mr-auto" onClick={() => run(() => api.delete(`/org/groups/${grp.id}`), 'Group deleted').then(() => { setGrp(null); reload() })}>Delete</button>}
        <button className="btn-primary" onClick={() => run(() => (grp.id ? api.put(`/org/groups/${grp.id}`, grp) : api.post('/org/groups', grp)), 'Group saved').then(() => { setGrp(null); reload() })}>Save</button></>}>
        <Field label="Name"><input className="input" value={grp.name} onChange={(e) => setGrp({ ...grp, name: e.target.value })} /></Field>
        {(users.data || []).map((u) => <label key={u.id} className="flex gap-2"><input type="checkbox" checked={grp.member_ids.includes(u.id)} onChange={(e) => setGrp({ ...grp, member_ids: e.target.checked ? [...grp.member_ids, u.id] : grp.member_ids.filter((x) => x !== u.id) })} />{u.full_name}</label>)}
      </Modal>}
    </PageShell>)
}

export function SettingsBranding() {
  const { feature, refresh } = useAuth()
  const { data, reload } = useAsync(() => api.get('/org/settings').then((r) => r.data))
  const [m, run] = useMsg(); const [s, setS] = useState(null); const [b, setB] = useState(null); const [o, setO] = useState(null)
  if (!data) return 'Loading…'
  const S = s || data.settings; const B = b || data.branding; const O = o || data.organization
  const setK = (k, v) => setS({ ...S, [k]: v })
  const toggle = (k, v) => setK(k, S[k].includes(v) ? S[k].filter((x) => x !== v) : [...S[k], v])
  return (
    <PageShell title="Settings & branding" subtitle={`Organization ${O.name} · data region ${O.region.toUpperCase()} (fixed at sign-up)`}>
      <Alert>{m.err}</Alert><Alert kind="ok">{m.ok}</Alert>
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Organization & billing details">
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="Organization name"><input className="input" value={O.name} onChange={(e) => setO({ ...O, name: e.target.value })} /></Field>
            <Field label="GSTIN / VAT ID"><input className="input" value={O.tax_id || ''} onChange={(e) => setO({ ...O, tax_id: e.target.value })} /></Field>
            <Field label="State code (India GST)"><input className="input" value={O.billing_state_code || ''} onChange={(e) => setO({ ...O, billing_state_code: e.target.value })} /></Field>
            <Field label="PO reference"><input className="input" value={O.po_reference || ''} onChange={(e) => setO({ ...O, po_reference: e.target.value })} /></Field>
            <Field label="Billing address" className="sm:col-span-2"><textarea className="input" rows={2} value={O.billing_address || ''} onChange={(e) => setO({ ...O, billing_address: e.target.value })} /></Field>
          </div>
        </Section>
        <Section title="Signing defaults">
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="Envelope expiry (days)"><input className="input" type="number" value={S.envelope_expiry_days} onChange={(e) => setK('envelope_expiry_days', +e.target.value)} /></Field>
            <Field label="Default authentication"><select className="input" value={S.default_auth} onChange={(e) => setK('default_auth', e.target.value)}>{['access_code', 'email_otp', 'sms_otp', 'none'].map((x) => <option key={x}>{x}</option>)}</select></Field>
            <Field label="First reminder (days)"><input className="input" type="number" value={S.reminder_first_days} onChange={(e) => setK('reminder_first_days', +e.target.value)} /></Field>
            <Field label="Repeat reminders (days)"><input className="input" type="number" value={S.reminder_every_days} onChange={(e) => setK('reminder_every_days', +e.target.value)} /></Field>
            <Field label="Time zone on stamps"><input className="input" value={S.timezone} onChange={(e) => setK('timezone', e.target.value)} /></Field>
            <Field label="Signer session idle timeout (min)"><input className="input" type="number" value={S.session_idle_minutes} onChange={(e) => setK('session_idle_minutes', +e.target.value)} /></Field>
          </div>
          <div className="mt-2">Allowed authentication: {['none', 'access_code', 'email_otp', 'sms_otp'].map((x) => <label key={x} className="mr-3 inline-flex gap-1"><input type="checkbox" checked={S.allowed_auth.includes(x)} onChange={() => toggle('allowed_auth', x)} />{x}</label>)}</div>
          <div>Allowed signature styles: {['typed', 'drawn', 'uploaded'].map((x) => <label key={x} className="mr-3 inline-flex gap-1"><input type="checkbox" checked={S.allowed_signature_kinds.includes(x)} onChange={() => toggle('allowed_signature_kinds', x)} />{x}</label>)}</div>
          <label className="flex gap-2"><input type="checkbox" checked={!!S.require_reason} onChange={(e) => setK('require_reason', e.target.checked)} /> Require a reason under every signature</label>
          <label className="flex gap-2"><input type="checkbox" checked={!!S.mfa_required} onChange={(e) => setK('mfa_required', e.target.checked)} /> Require MFA for all users</label>
          <label className="flex gap-2"><input type="checkbox" checked={S.access_code_channel === 'sms'} onChange={(e) => setK('access_code_channel', e.target.checked ? 'sms' : 'email')} /> Send access codes by SMS when a mobile number is given</label>
        </Section>
        <Section title="Password policy">
          <div className="grid grid-cols-3 gap-2">
            <Field label="Min length"><input className="input" type="number" value={S.password_policy?.min_length || 12} onChange={(e) => setK('password_policy', { ...S.password_policy, min_length: +e.target.value })} /></Field>
            <Field label="Expiry (days, 0 = never)"><input className="input" type="number" value={S.password_policy?.expiry_days || 0} onChange={(e) => setK('password_policy', { ...S.password_policy, expiry_days: +e.target.value })} /></Field>
            <Field label="History"><input className="input" type="number" value={S.password_policy?.history ?? 3} onChange={(e) => setK('password_policy', { ...S.password_policy, history: +e.target.value })} /></Field>
          </div>
        </Section>
        <Section title="Consent & privacy text shown to signers">
          <Field label="Electronic record & signature disclosure (blank = default)"><textarea className="input" rows={3} value={S.consent_text} onChange={(e) => setK('consent_text', e.target.value)} /></Field>
          <Field label="Privacy notice (blank = default)"><textarea className="input" rows={3} value={S.privacy_text} onChange={(e) => setK('privacy_text', e.target.value)} /></Field>
        </Section>
      </div>
      <button className="btn-primary" onClick={() => run(() => api.put('/org/settings', { settings: S, organization: O }), 'Settings saved').then(() => { setS(null); setO(null); reload(); refresh() })}>Save settings</button>
      <Section title="Branding (emails, signing page, certificate)" right={!feature('branding') && <span className="text-slate-500">Custom branding needs the Standard plan or higher.</span>}>
        <div className="grid gap-2 sm:grid-cols-3">
          <Field label="Product name"><input className="input" value={B.product_name || ''} onChange={(e) => setB({ ...B, product_name: e.target.value })} /></Field>
          <Field label="Primary colour"><input className="input" type="color" value={B.primary || '#0D47A1'} onChange={(e) => setB({ ...B, primary: e.target.value.toUpperCase() })} /></Field>
          <Field label="Accent colour"><input className="input" type="color" value={B.accent || '#E6007E'} onChange={(e) => setB({ ...B, accent: e.target.value.toUpperCase() })} /></Field>
          <Field label="Reply-to email"><input className="input" value={B.reply_to || ''} onChange={(e) => setB({ ...B, reply_to: e.target.value })} /></Field>
          <Field label="Email footer" className="sm:col-span-2"><input className="input" value={B.email_footer || ''} onChange={(e) => setB({ ...B, email_footer: e.target.value })} /></Field>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <img src={B.logo_url || '/vaics-logo-full.png'} alt="logo" className="h-10 border bg-white p-1" />
          <label className="btn-secondary cursor-pointer">Upload logo (PNG/JPEG, ≤512 KB)<input hidden type="file" accept="image/png,image/jpeg" onChange={async (e) => { const fd = new FormData(); fd.append('file', e.target.files[0]); await run(() => api.post('/org/branding/logo', fd), 'Logo updated'); reload() }} /></label>
          <button className="btn-primary" disabled={!feature('branding')} onClick={() => run(() => api.put('/org/branding', { product_name: B.product_name, primary: B.primary, accent: B.accent, email_footer: B.email_footer, reply_to: B.reply_to || null }), 'Branding saved').then(() => { setB(null); reload() })}>Save branding</button>
          <div className="flex items-center gap-2 border px-3 py-2" style={{ background: B.primary }}><span className="font-semibold text-white">{B.product_name}</span><span className="px-2 py-1 text-white" style={{ background: B.accent }}>Button</span></div>
        </div>
      </Section>
      <Section title="VAICS support access">
        <p className="text-slate-500">VAICS operations staff cannot see your envelopes unless you grant time-limited access. Every grant and every access is logged.</p>
        <div className="flex gap-2"><button className="btn-secondary" onClick={() => run(() => api.post('/org/support-access?hours=24'), (d) => `Support access granted until ${fmt(d.support_access_until)}`)}>Grant 24 hours</button><button className="btn-secondary" onClick={() => run(() => api.post('/org/support-access?hours=0'), 'Support access revoked')}>Revoke</button></div>
      </Section>
    </PageShell>)
}

export function Integrations() {
  const { feature } = useAuth()
  const keys = useAsync(() => api.get('/org/api-keys').then((r) => r.data)); const hooks = useAsync(() => api.get('/org/webhooks').then((r) => r.data)); const dels = useAsync(() => api.get('/org/webhooks/deliveries').then((r) => r.data))
  const [m, run] = useMsg(); const [k, setK] = useState({ name: '', scopes: ['envelopes:read'] }); const [secret, setSecret] = useState(null); const [h, setH] = useState({ url: '', events: '*' })
  return (
    <PageShell title="API & webhooks" subtitle={<>REST API at <code>/api/v1</code> · OpenAPI docs at <a className="text-[#0D47A1]" href="/api/docs" target="_blank" rel="noreferrer">/api/docs</a></>}>
      {!feature('api') && <Alert kind="warn">API access and webhooks need the Business plan (or the developer sandbox).</Alert>}
      <Alert>{m.err}</Alert><Alert kind="ok">{m.ok}</Alert>
      {secret && <Alert kind="warn">Copy now — shown only once: <code className="break-all">{secret}</code></Alert>}
      <Section title="API keys">
        <div className="flex flex-wrap items-end gap-2"><Field label="Key name"><input className="input" value={k.name} onChange={(e) => setK({ ...k, name: e.target.value })} /></Field>
          <div className="flex flex-wrap gap-2">{SCOPES.map((s) => <label key={s} className="inline-flex gap-1"><input type="checkbox" checked={k.scopes.includes(s)} onChange={(e) => setK({ ...k, scopes: e.target.checked ? [...k.scopes, s] : k.scopes.filter((x) => x !== s) })} />{s}</label>)}</div>
          <button className="btn-accent" onClick={async () => { const r = await run(() => api.post('/org/api-keys', k), 'API key created'); if (r) { setSecret(r.data.key); keys.reload() } }}>Create key</button></div>
        <Table rows={keys.data || []} cols={[{ label: 'Name', k: 'name' }, { label: 'Prefix', render: (x) => <code>{x.prefix}…</code> }, { label: 'Scopes', render: (x) => x.scopes.join(', ') }, { label: 'Last used', render: (x) => fmt(x.last_used_at) },
          { label: '', render: (x) => x.revoked ? 'Revoked' : <button className="btn-danger" onClick={() => run(() => api.delete(`/org/api-keys/${x.id}`), 'Revoked').then(keys.reload)}>Revoke</button> }]} />
      </Section>
      <Section title="Webhooks">
        <p className="text-slate-500">Each delivery is signed: <code>X-VAICS-Signature: t=&lt;unix&gt;,v1=HMAC_SHA256(secret, "&lt;t&gt;.&lt;body&gt;")</code>. Failed deliveries retry after 1, 5, 30, 120 and 720 minutes.</p>
        <div className="flex flex-wrap items-end gap-2"><Field label="HTTPS URL" className="min-w-72 flex-1"><input className="input" value={h.url} onChange={(e) => setH({ ...h, url: e.target.value })} /></Field>
          <Field label="Events (comma separated, * = all)"><input className="input" value={h.events} onChange={(e) => setH({ ...h, events: e.target.value })} /></Field>
          <button className="btn-accent" onClick={async () => { const r = await run(() => api.post('/org/webhooks', { url: h.url, events: h.events.split(',').map((s) => s.trim()).filter(Boolean) }), 'Webhook added'); if (r) { setSecret(r.data.secret); hooks.reload() } }}>Add webhook</button></div>
        <Table rows={hooks.data || []} cols={[{ label: 'URL', k: 'url' }, { label: 'Events', render: (w) => w.events.join(', ') }, { label: 'Active', render: (w) => (w.active ? 'Yes' : 'No') }, { label: '', render: (w) => w.active && <button className="btn-danger" onClick={() => run(() => api.delete(`/org/webhooks/${w.id}`), 'Disabled').then(hooks.reload)}>Disable</button> }]} />
        <h3 className="mt-3">Recent deliveries</h3>
        <Table rows={dels.data || []} cols={[{ label: 'Time', render: (d) => fmt(d.created_at) }, { label: 'Event', k: 'event' }, { label: 'Status', render: (d) => <SBadge s={d.status === 'delivered' ? 'delivered_wh' : d.status} /> }, { label: 'Attempts', k: 'attempts' }, { label: 'HTTP', k: 'response_code' }, { label: 'Error', k: 'error' }]} />
      </Section>
    </PageShell>)
}

export function AdminAudit() {
  const [q, setQ] = useState('')
  const { data, err } = useAsync(() => api.get('/org/audit-log', { params: { q } }).then((r) => r.data), [q])
  return (
    <PageShell title="Admin audit log" subtitle="Every administrative change with before/after values." right={<button className="btn-secondary" onClick={() => download('/org/audit-log?format=csv', 'admin-audit-log.csv')}>Export CSV</button>}>
      <input className="input max-w-sm" placeholder="Filter by action, actor or target" onKeyDown={(e) => e.key === 'Enter' && setQ(e.target.value)} />
      <Alert>{err}</Alert>
      <Table rows={data || []} cols={[{ label: 'Time', render: (r) => fmt(r.created_at) }, { label: 'Actor', k: 'actor_email' }, { label: 'Action', k: 'action' }, { label: 'Target', k: 'target' }, { label: 'IP', k: 'ip' },
        { label: 'Change', render: (r) => <code className="block max-w-md truncate" title={JSON.stringify(r.after)}>{JSON.stringify(r.after)}</code> }]} />
    </PageShell>)
}

export function Privacy() {
  const { data: s, reload } = useAsync(() => api.get('/org/settings').then((r) => r.data.settings))
  const dsr = useAsync(() => api.get('/privacy/dsr').then((r) => r.data)); const del = useAsync(() => api.get('/privacy/deletions').then((r) => r.data))
  const [m, run] = useMsg(); const [ret, setRet] = useState(null); const [f, setF] = useState({ email: '', kind: 'access' }); const [result, setResult] = useState(null)
  if (!s) return 'Loading…'
  const R = ret || s.retention
  return (
    <PageShell title="Privacy & retention" subtitle="Retention schedules, data-subject requests (DPDP / GDPR) and full organization export." right={<button className="btn-secondary" onClick={() => download('/privacy/export', 'organization-export.zip')}>Export all data (ZIP)</button>}>
      <Alert>{m.err}</Alert><Alert kind="ok">{m.ok}</Alert>
      <Section title="Retention (days; documents are purged automatically, audit evidence is kept)">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">{Object.entries(R).map(([k, v]) => <Field key={k} label={k.replace('_days', '').replace('_', ' ')}><input className="input" type="number" value={v} onChange={(e) => setRet({ ...R, [k]: +e.target.value })} /></Field>)}</div>
        <button className="btn-primary mt-2" onClick={() => run(() => api.put('/org/settings', { settings: { retention: R } }), 'Retention saved').then(() => { setRet(null); reload() })}>Save retention</button>
        <p className="mt-1 text-slate-500">Envelopes on legal hold are never purged. Apply a hold from the envelope page.</p>
      </Section>
      <Section title="Data-subject request">
        <div className="flex flex-wrap items-end gap-2"><Field label="Person's email" className="min-w-64 flex-1"><input className="input" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field label="Request"><select className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="access">Access (what we hold)</option><option value="correct">Correct name/email</option><option value="erase">Erase</option></select></Field>
          {f.kind === 'correct' && <><Field label="New name"><input className="input" value={f.new_name || ''} onChange={(e) => setF({ ...f, new_name: e.target.value })} /></Field><Field label="New email"><input className="input" value={f.new_email || ''} onChange={(e) => setF({ ...f, new_email: e.target.value || undefined })} /></Field></>}
          <button className="btn-accent" onClick={async () => { if (f.kind === 'erase' && !confirm('Erase this person from open records? Completed signed records are retained.')) return; const r = await run(() => api.post('/privacy/dsr', f), 'Request processed'); if (r) { setResult(r.data); dsr.reload(); del.reload() } }}>Run</button></div>
        {result && <pre className="mt-2 max-h-64 overflow-auto border bg-white p-2">{JSON.stringify(result, null, 2)}</pre>}
        <Table rows={dsr.data || []} cols={[{ label: 'Time', render: (d) => fmt(d.created_at) }, { label: 'Email', k: 'email' }, { label: 'Kind', k: 'kind' }, { label: 'Status', k: 'status' }]} />
      </Section>
      <Section title="Deletion records">
        <Table rows={del.data || []} empty="Nothing purged yet." cols={[{ label: 'Time', render: (d) => fmt(d.created_at) }, { label: 'Envelope', k: 'envelope_public_id' }, { label: 'Reason', k: 'reason' }, { label: 'Detail', k: 'detail' }]} />
      </Section>
    </PageShell>)
}

export function Billing() {
  const { refresh } = useAuth()
  const sub = useAsync(() => api.get('/billing/subscription').then((r) => r.data)); const plans = useAsync(() => api.get('/billing/plans').then((r) => r.data)); const inv = useAsync(() => api.get('/billing/invoices').then((r) => r.data))
  const [m, run] = useMsg(); const [cycle, setCycle] = useState('monthly'); const [seats, setSeats] = useState(null); const [coupon, setCoupon] = useState(''); const [tab, setTab] = useState('plan')
  const S = sub.data; if (!S || !plans.data) return 'Loading…'
  const cur = S.currency; const seatN = seats ?? S.seats
  const checkout = async (code) => {
    const r = await run(() => api.post('/billing/checkout', { plan: code, cycle, seats: seatN, coupon: coupon || null }), (d) => d.paid ? 'Plan changed.' : 'Checkout created.')
    if (r?.data?.checkout?.checkout_url) location.href = r.data.checkout.checkout_url
    else if (r?.data?.checkout?.order_id) run(async () => ({ data: null }), `Razorpay order ${r.data.checkout.order_id} created. Complete payment with Razorpay Checkout (key ${r.data.checkout.key_id}).`)
    sub.reload(); inv.reload(); refresh()
  }
  return (
    <PageShell title="Plan & billing" subtitle={`Current: ${S.plan?.name || '—'} · ${S.status}${S.trial_ends_at ? ` · trial ends ${fmt(S.trial_ends_at)}` : ''} · ${S.seats} seat(s)`}>
      {!S.provider_configured && <Alert kind="warn">Online payments are not live: the {S.provider} payment provider is not configured in this deployment. Checkout returns an error and nothing is charged. VAICS can assign plans on invoice terms.</Alert>}
      <Alert>{m.err}</Alert><Alert kind="ok">{m.ok}</Alert>
      <Tabs value={tab} onChange={setTab} tabs={[['plan', 'Plans'], ['usage', 'Usage'], ['invoices', 'Invoices']]} />
      {tab === 'plan' && <>
        <div className="flex flex-wrap items-end gap-2"><Field label="Billing cycle"><select className="input" value={cycle} onChange={(e) => setCycle(e.target.value)}><option value="monthly">Monthly</option><option value="annual">Annual (2 months free)</option></select></Field>
          <Field label="Seats"><input className="input !w-24" type="number" min={1} value={seatN} onChange={(e) => setSeats(+e.target.value)} /></Field>
          <Field label="Coupon"><input className="input" value={coupon} onChange={(e) => setCoupon(e.target.value)} /></Field>
          {seats != null && seats !== S.seats && S.status === 'active' && <button className="btn-secondary" onClick={() => run(() => api.post('/billing/seats', { seats }), (d) => d.note || 'Seats updated').then(() => { setSeats(null); sub.reload() })}>Change seats only</button>}</div>
        <div className="grid gap-3 md:grid-cols-3">{plans.data.map((p) => <div key={p.code} className={`card space-y-2 ${S.plan?.code === p.code ? 'border-[#E6007E]' : ''}`}>
          <h2>{p.name}</h2><p className="text-slate-500">{p.description}</p>
          <div className="text-[22px] font-semibold text-[#0D47A1]">{cur} {p.prices?.[cur]?.[cycle] ?? '—'}<span className="text-[12px] font-normal text-slate-500"> / seat / {cycle === 'annual' ? 'year' : 'month'} + tax</span></div>
          <ul className="text-slate-600">{[['envelopes_per_month', 'envelopes / month'], ['templates', 'templates'], ['sms_per_month', 'SMS / month'], ['api_calls_per_month', 'API calls / month']].map(([k, l]) => <li key={k}>• {p.limits[k] === -1 ? 'Unlimited' : p.limits[k] ?? 0} {l}</li>)}
            {Object.entries(p.features).filter(([, v]) => v).map(([f]) => <li key={f}>✓ {f.replaceAll('_', ' ')}</li>)}</ul>
          {S.plan?.code === p.code && S.status === 'active' ? <SBadge s="active" label="Current plan" /> : <button className="btn-accent w-full" onClick={() => checkout(p.code)}>{p.code === 'free' ? 'Switch to Free' : 'Choose'}</button>}
        </div>)}</div>
        <div className="flex gap-2"><button className="btn-secondary" onClick={() => confirm('Downgrade to Free at once? Paid features stop working.') && run(() => api.post('/billing/cancel'), (d) => d.note).then(() => { sub.reload(); refresh() })}>Cancel subscription</button>
          <button className="btn-secondary" onClick={async () => { const metric = prompt('Buy credits for (envelopes / sms / aadhaar / dsc / idv):', 'envelopes'); const qty = +prompt('Quantity', '100'); if (metric && qty) run(() => api.post('/billing/credits', { metric, quantity: qty }), 'Credit checkout created') }}>Buy credits</button></div>
        <p className="text-slate-500">Enterprise plans with custom limits, invoice billing and PO numbers are arranged with VAICS sales.</p>
      </>}
      {tab === 'usage' && <Table rows={Object.entries(S.usage).map(([k, v]) => ({ id: k, k, ...v }))} cols={[{ label: 'Metric', k: 'k' }, { label: 'Used', k: 'used' }, { label: 'Limit', render: (r) => r.limit ?? 'Unlimited' }, { label: 'Credits', render: (r) => r.credits ?? '—' }, { label: '%', render: (r) => (r.pct != null ? `${r.pct}%` : '—') }]} />}
      {tab === 'invoices' && <Table rows={inv.data || []} empty="No invoices." cols={[{ label: 'Number', k: 'number' }, { label: 'Date', render: (i) => fmt(i.created_at) }, { label: 'Status', render: (i) => <SBadge s={i.status} /> },
        { label: 'Total', render: (i) => `${i.currency} ${(i.total / 100).toFixed(2)}` }, { label: 'Tax', render: (i) => `${i.tax?.type || ''} ${((i.tax?.amount || 0) / 100).toFixed(2)}` },
        { label: '', render: (i) => <button className="btn-secondary" onClick={() => download(`/billing/invoices/${i.id}/pdf`, `${i.number}.pdf`)}>PDF</button> }]} />}
    </PageShell>)
}
