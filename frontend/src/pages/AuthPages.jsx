import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import api, { errMsg, setToken } from '../api'
import { useAuth } from '../auth'
import { theme } from '../theme'
import { Alert, Field } from '../components/ui'

export function AuthCard({ title, subtitle, children }) {
  return (
    <div className="flex min-h-screen bg-white">
      <div className="relative hidden w-[46%] flex-col justify-between overflow-hidden bg-[#0D47A1] p-14 text-white lg:flex">
        <div className="pointer-events-none absolute -right-40 -bottom-40 h-[520px] w-[520px] round border border-white/10" />
        <div className="pointer-events-none absolute -right-20 -bottom-20 h-[360px] w-[360px] round border border-white/10" />
        <div className="inline-flex w-fit bg-white px-4 py-3"><img src={theme.logoFull} alt="VAICS" className="h-9" /></div>
        <div className="relative max-w-md space-y-5">
          <div className="h-[3px] w-12 bg-[#00B6F0]" />
          <h1 className="text-[34px] leading-tight font-semibold !text-white">Sign with confidence.</h1>
          <p className="text-[16px] leading-relaxed text-white/80">VAICS Sign sends documents to the VAICS representative and the countersigner in order, stamps every signature with its reason, time and SHA-256 fingerprint, and keeps a tamper-evident audit trail.</p>
        </div>
        <div className="relative text-[12px] text-white/60">© {new Date().getFullYear()} {theme.company} · Internal use only</div>
      </div>
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-[380px] space-y-7">
          <img src={theme.logoFull} alt="VAICS" className="h-9 lg:hidden" />
          <div><h1>{title}</h1>{subtitle && <p className="muted mt-1.5">{subtitle}</p>}</div>
          {children}
        </div>
        <div className="mt-12 flex gap-5 text-[12px] text-slate-400"><Link to="/privacy" className="hover:text-[#0D47A1]">Privacy notice</Link><Link to="/verify" className="hover:text-[#0D47A1]">Verify a document</Link></div>
      </div>
    </div>
  )
}

export function Login() {
  const { login } = useAuth(); const nav = useNavigate(); const [q] = useSearchParams()
  const [f, setF] = useState({ email: '', password: '', totp: '' }); const [mfa, setMfa] = useState(false); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setErr(''); setBusy(true)
    try {
      const d = await login(f.email, f.password, mfa ? f.totp : '')
      if (d.mfa_required) { setMfa(true); return }
      if (d.mfa_enrolment_required) { setToken(d.access_token); nav('/mfa-enrol'); return }
      nav(d.password_expired ? '/account?expired=1' : (q.get('next') || '/'))
    } catch (ex) { setErr(errMsg(ex)) } finally { setBusy(false) }
  }
  return (
    <AuthCard title={mfa ? 'Two-step verification' : 'Welcome back'} subtitle={mfa ? 'Enter the 6-digit code from your authenticator app.' : 'Sign in to VAICS Sign with your work account.'}>
      {q.get('expired') && <Alert kind="warn">Your session ended. Please sign in again.</Alert>}
      <Alert>{err}</Alert>
      <form onSubmit={submit} className="space-y-4">
        {!mfa ? <>
          <Field label="Work email"><input className="input" type="email" autoComplete="username" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required autoFocus /></Field>
          <Field label="Password"><input className="input" type="password" autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required /></Field>
        </> : <Field label="Authentication code (or a recovery code)"><input className="input text-center tracking-[0.3em]" autoComplete="one-time-code" value={f.totp} onChange={(e) => setF({ ...f, totp: e.target.value })} autoFocus /></Field>}
        <button className="btn-primary h-11 w-full" disabled={busy}>{busy ? 'Please wait…' : mfa ? 'Verify' : 'Sign in'}</button>
      </form>
      <div className="flex items-center justify-between text-[13px]"><Link className="text-[#0D47A1] hover:underline" to="/forgot-password">Forgot password?</Link><span className="text-slate-400">Access is by invitation</span></div>
      <p className="border-t border-gray-100 pt-5 text-[12px] text-slate-400">VAICS Portal single sign-on will be connected in a later step.</p>
    </AuthCard>
  )
}

const COUNTRIES = [['IN', 'India'], ['US', 'United States'], ['GB', 'United Kingdom'], ['DE', 'Germany'], ['FR', 'France'], ['NL', 'Netherlands'], ['IE', 'Ireland'], ['AE', 'United Arab Emirates'], ['SG', 'Singapore'], ['AU', 'Australia'], ['CA', 'Canada']]

export function Signup() {
  const [f, setF] = useState({ full_name: '', email: '', password: '', organization: '', country: 'IN', accept_terms: false, sandbox: false })
  const [err, setErr] = useState(''); const [done, setDone] = useState(null); const [busy, setBusy] = useState(false)
  const submit = async (e) => { e.preventDefault(); setErr(''); setBusy(true); try { const r = await api.post('/auth/signup', f); setDone(r.data) } catch (ex) { setErr(errMsg(ex)) } finally { setBusy(false) } }
  if (done) return (
    <AuthCard title="Check your email">
      <Alert kind="ok">Your organization was created (data region: {done.region.toUpperCase()}). Verify your email address to start sending.</Alert>
      {done.email_mode === 'dev_outbox' && <Alert kind="warn">SMTP is not configured: no email was delivered. Sign in and open the Email outbox to find the verification link.</Alert>}
      <Link className="btn-primary w-full" to="/login">Go to sign in</Link>
    </AuthCard>)
  return (
    <AuthCard title="Create your organization" subtitle="14-day free trial of the Business plan. No card required.">
      <Alert>{err}</Alert>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Your full name"><input className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></Field>
        <Field label="Work email"><input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required /></Field>
        <Field label="Password (12+ characters, mixed case, a number and a symbol)"><input className="input" type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required /></Field>
        <Field label="Organization name"><input className="input" value={f.organization} onChange={(e) => setF({ ...f, organization: e.target.value })} required /></Field>
        <Field label="Country (sets your data region and currency)"><select className="input" value={f.country} onChange={(e) => setF({ ...f, country: e.target.value })}>{COUNTRIES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></Field>
        <label className="flex gap-2"><input type="checkbox" checked={f.sandbox} onChange={(e) => setF({ ...f, sandbox: e.target.checked })} /> Developer sandbox (watermarked test documents, not legally binding)</label>
        <label className="flex gap-2"><input type="checkbox" checked={f.accept_terms} onChange={(e) => setF({ ...f, accept_terms: e.target.checked })} required /> I accept the Terms of Service, Privacy Policy and Data Processing Agreement.</label>
        <button className="btn-accent w-full" disabled={busy}>Create organization</button>
      </form>
      <Link className="text-[#0D47A1]" to="/login">Already have an account? Sign in</Link>
    </AuthCard>
  )
}

export function VerifyEmail() {
  const { token } = useParams(); const [s, setS] = useState({ ok: '', err: '' })
  useEffect(() => { api.post(`/auth/verify-email/${token}`).then(() => setS({ ok: 'Your email address is verified. You can now send documents.' })).catch((e) => setS({ err: errMsg(e) })) }, [token])
  return <AuthCard title="Email verification"><Alert kind="ok">{s.ok}</Alert><Alert>{s.err}</Alert><Link className="btn-primary w-full" to="/">Continue</Link></AuthCard>
}

export function ForgotPassword() {
  const [email, setEmail] = useState(''); const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  return (
    <AuthCard title="Reset your password">
      <Alert kind="ok">{msg}</Alert><Alert>{err}</Alert>
      <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { setMsg((await api.post('/auth/password/forgot', { email })).data.message) } catch (ex) { setErr(errMsg(ex)) } }}>
        <Field label="Email"><input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></Field>
        <button className="btn-primary w-full">Send reset link</button>
      </form>
      <Link className="text-[#0D47A1]" to="/login">Back to sign in</Link>
    </AuthCard>
  )
}

export function ResetPassword() {
  const { token } = useParams(); const [pw, setPw] = useState(''); const [msg, setMsg] = useState(''); const [err, setErr] = useState('')
  return (
    <AuthCard title="Choose a new password">
      <Alert kind="ok">{msg}</Alert><Alert>{err}</Alert>
      {!msg && <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); setErr(''); try { setMsg((await api.post('/auth/password/reset', { token, password: pw })).data.message) } catch (ex) { setErr(errMsg(ex)) } }}>
        <Field label="New password"><input className="input" type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} required /></Field>
        <button className="btn-primary w-full">Update password</button>
      </form>}
      <Link className="text-[#0D47A1]" to="/login">Sign in</Link>
    </AuthCard>
  )
}

export function AcceptInvite() {
  const { token } = useParams(); const [info, setInfo] = useState(null); const [f, setF] = useState({ full_name: '', password: '', accept_terms: false }); const [err, setErr] = useState(''); const [ok, setOk] = useState('')
  useEffect(() => { api.get(`/auth/invitations/${token}`).then((r) => setInfo(r.data)).catch((e) => setErr(errMsg(e))) }, [token])
  return (
    <AuthCard title="Join your team" subtitle={info && `${info.organization} invited ${info.email} as ${info.role?.replace('_', ' ')}`}>
      <Alert>{err}</Alert><Alert kind="ok">{ok}</Alert>
      {info && !ok && <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); setErr(''); try { setOk((await api.post('/auth/invitations/accept', { token, ...f })).data.message) } catch (ex) { setErr(errMsg(ex)) } }}>
        <Field label="Full name"><input className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></Field>
        <Field label="Password"><input className="input" type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required /></Field>
        <label className="flex gap-2"><input type="checkbox" checked={f.accept_terms} onChange={(e) => setF({ ...f, accept_terms: e.target.checked })} required /> I accept the Terms of Service and Privacy Policy.</label>
        <button className="btn-primary w-full">Create my account</button>
      </form>}
      {ok && <Link className="btn-primary w-full" to="/login">Sign in</Link>}
    </AuthCard>
  )
}

export function MfaEnrol() {
  const nav = useNavigate(); const { refresh } = useAuth()
  const [s, setS] = useState(null); const [code, setCode] = useState(''); const [codes, setCodes] = useState(null); const [err, setErr] = useState('')
  useEffect(() => { api.post('/auth/mfa/enrol-setup').then((r) => setS(r.data)).catch((e) => setErr(errMsg(e))) }, [])
  return (
    <AuthCard title="Set up two-factor authentication" subtitle="Your organization requires an authenticator app.">
      <Alert>{err}</Alert>
      {codes ? <><Alert kind="ok">MFA is on. Store these single-use recovery codes safely:</Alert><pre className="border bg-white p-2">{codes.join('\n')}</pre>
        <button className="btn-primary w-full" onClick={async () => { await refresh(); nav('/') }}>Continue</button></>
        : s && <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); try { setCodes((await api.post('/auth/mfa/enrol-enable', { code })).data.recovery_codes) } catch (ex) { setErr(errMsg(ex)) } }}>
          <p>Add this key to Google Authenticator, Microsoft Authenticator or similar:</p>
          <code className="block border bg-white p-2 break-all">{s.secret}</code>
          <p className="break-all text-slate-400">{s.otpauth_uri}</p>
          <Field label="6-digit code"><input className="input" value={code} onChange={(e) => setCode(e.target.value)} /></Field>
          <button className="btn-primary w-full">Enable</button>
        </form>}
    </AuthCard>
  )
}
