import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import api, { errMsg, fmt, download } from '../api'
import { useAuth, ROLE_LABEL } from '../auth'
import { LANGS, setLang } from '../i18n'
import { PageShell, Section, Alert, Field, Table, useAsync } from '../components/ui'

export default function Account() {
  const { user, refresh } = useAuth(); const [q] = useSearchParams()
  const [m, setM] = useState({ ok: '', err: '' }); const run = async (fn, ok) => { setM({}); try { const r = await fn(); setM({ ok }); return r } catch (e) { setM({ err: errMsg(e) }) } }
  const [p, setP] = useState({ full_name: user.full_name, title: user.title || '', language: user.language, timezone: user.timezone })
  const [pw, setPw] = useState({ current_password: '', new_password: '' }); const [mfa, setMfa] = useState(null); const [code, setCode] = useState(''); const [codes, setCodes] = useState(null)
  const sessions = useAsync(() => api.get('/auth/sessions').then((r) => r.data))
  const reqs = useAsync(() => api.get('/privacy/my-requests').then((r) => r.data))
  return (
    <PageShell title="My account" subtitle={`${user.email} · ${ROLE_LABEL[user.role]}`}>
      {q.get('expired') && <Alert kind="warn">Your password has expired under your organization's policy. Choose a new one.</Alert>}
      <Alert>{m.err}</Alert><Alert kind="ok">{m.ok}</Alert>
      {!user.email_verified && <Alert kind="warn">Your email is not verified. <button className="underline" onClick={() => run(() => api.post('/auth/resend-verification'), 'Verification email sent (see Email outbox in development).')}>Resend verification</button></Alert>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Profile">
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="Full name"><input className="input" value={p.full_name} onChange={(e) => setP({ ...p, full_name: e.target.value })} /></Field>
            <Field label="Title"><input className="input" value={p.title} onChange={(e) => setP({ ...p, title: e.target.value })} /></Field>
            <Field label="Language"><select className="input" value={p.language} onChange={(e) => setP({ ...p, language: e.target.value })}>{LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
            <Field label="Time zone"><input className="input" value={p.timezone} onChange={(e) => setP({ ...p, timezone: e.target.value })} /></Field>
          </div>
          <button className="btn-primary mt-2" onClick={() => run(() => api.patch('/auth/me', p), 'Profile saved').then(() => { setLang(p.language); refresh() })}>Save profile</button>
        </Section>
        <Section title="Password">
          <Field label="Current password"><input className="input" type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
          <Field label="New password"><input className="input" type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
          <button className="btn-primary mt-2" onClick={() => run(() => api.post('/auth/password/change', pw), 'Password changed').then(() => setPw({ current_password: '', new_password: '' }))}>Change password</button>
        </Section>
        <Section title="Two-factor authentication (authenticator app)">
          {codes ? <><Alert kind="ok">MFA enabled. Save these single-use recovery codes:</Alert><pre className="border bg-white p-2">{codes.join('\n')}</pre></>
            : user.mfa_enabled ? <div className="flex gap-2"><input className="input" placeholder="Current 6-digit code" value={code} onChange={(e) => setCode(e.target.value)} /><button className="btn-danger" onClick={() => run(() => api.post('/auth/mfa/disable', { code }), 'MFA disabled').then(refresh)}>Disable MFA</button></div>
              : mfa ? <div className="space-y-2"><p>Add this key to your authenticator app:</p><code className="block border bg-white p-2 break-all">{mfa.secret}</code><p className="break-all text-slate-400">{mfa.otpauth_uri}</p>
                <div className="flex gap-2"><input className="input" placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value)} /><button className="btn-primary" onClick={async () => { const r = await run(() => api.post('/auth/mfa/enable', { code }), 'MFA enabled'); if (r) { setCodes(r.data.recovery_codes); refresh() } }}>Enable</button></div></div>
                : <button className="btn-accent" onClick={async () => { const r = await run(() => api.post('/auth/mfa/setup'), ''); if (r) setMfa(r.data) }}>Set up MFA</button>}
        </Section>
        <Section title="My data" right={<div className="flex gap-2"><button className="btn-secondary" onClick={() => run(() => api.post('/privacy/my-requests', { kind: 'export' }), 'Export requested. An administrator will review it.').then(reqs.reload)}>Request a copy</button>
          <button className="btn-danger" onClick={() => { if (confirm('Request deletion of your personal data? An administrator reviews it; completed signed records are kept where the law requires, and your account will be deactivated.')) run(() => api.post('/privacy/my-requests', { kind: 'erase' }), 'Deletion requested. An administrator will review it.').then(reqs.reload) }}>Request deletion</button></div>}>
          <p className="muted">Ask for a copy of the personal data VAICS Sign holds about you, or for its deletion. Requests are approved by an administrator and recorded in the admin audit log.</p>
          <Table rows={reqs.data || []} empty="No requests yet." cols={[{ label: 'Requested', render: (r) => fmt(r.created_at) }, { label: 'Type', render: (r) => r.kind === 'self_export' ? 'Copy of my data' : 'Deletion' },
            { label: 'Status', render: (r) => <span className="capitalize">{r.status}</span> }, { label: '', render: (r) => r.kind === 'self_export' && r.status === 'completed' && <button className="btn-ghost" onClick={() => download(`/privacy/my-requests/${r.id}/download`, `my-data-${r.id}.json`)}>Download</button> }]} />
        </Section>
        <Section title="Active sessions">
          <Table rows={(sessions.data || []).map((s) => ({ ...s }))} cols={[{ label: 'Started', render: (s) => fmt(s.created_at) }, { label: 'Last seen', render: (s) => fmt(s.last_seen_at) }, { label: 'IP', k: 'ip' },
            { label: 'Device', render: (s) => <span className="block max-w-56 truncate" title={s.user_agent}>{s.user_agent}</span> }, { label: '', render: (s) => s.current ? 'This device' : <button className="btn-secondary" onClick={() => run(() => api.delete(`/auth/sessions/${s.id}`), 'Session ended').then(sessions.reload)}>End</button> }]} />
        </Section>
      </div>
    </PageShell>)
}
