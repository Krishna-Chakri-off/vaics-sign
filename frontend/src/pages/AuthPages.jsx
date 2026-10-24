import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import api, { errMsg, setToken } from '../api'
import { useAuth } from '../auth'
import { theme } from '../theme'
import { Alert, Field } from '../components/ui'

export function AuthCard({ title, subtitle, children }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#F2F8FF] md:flex-row">
      <div className="relative hidden flex-1 overflow-hidden md:block">
        <img src={theme.hero} alt="" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute bottom-10 left-10 max-w-md bg-white/85 p-6">
          <img src={theme.logoFull} alt="VAICS" className="h-12" />
          <p className="mt-3 text-[18px] font-semibold text-[#0D47A1]">VAICS Sign</p>
          <p className="mt-1 text-slate-600">Send, sign and track documents with a tamper-evident audit trail, sequential and parallel routing, and a Certificate of Completion for every envelope.</p>
        </div>
      </div>
      <div className="flex w-full items-center justify-center p-6 md:w-[480px]">
        <div className="card w-full max-w-sm space-y-4">
          <img src={theme.logoFull} alt="VAICS" className="h-10 md:hidden" />
          <div><h1>{title}</h1>{subtitle && <p className="mt-1 text-slate-500">{subtitle}</p>}</div>
          {children}
        </div>
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
    <AuthCard title="Sign in" subtitle="VAICS Sign">
      {q.get('expired') && <Alert kind="warn">Your session ended. Please sign in again.</Alert>}
      <Alert>{err}</Alert>
      <form onSubmit={submit} className="space-y-3">
        {!mfa ? <>
          <Field label="Work email"><input className="input" type="email" autoComplete="username" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required autoFocus /></Field>
          <Field label="Password"><input className="input" type="password" autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required /></Field>
        </> : <Field label="Authentication code (or a recovery code)"><input className="input text-center tracking-[0.3em]" autoComplete="one-time-code" value={f.totp} onChange={(e) => setF({ ...f, totp: e.target.value })} autoFocus /></Field>}
        <button className="btn-primary w-full" disabled={busy}>{mfa ? 'Verify' : 'Sign in'}</button>
      </form>
      <div className="flex justify-between"><Link className="text-[#0D47A1]" to="/forgot-password">Forgot password?</Link><span className="text-slate-500">Access is by invitation from your VAICS administrator.</span></div>
          </AuthCard>
  )
}

const COUNTRIES = [['IN', 'India'], ['US', 'United States'], ['GB', 'United Kingdom'], ['DE', 'Germany'], ['FR', 'France'], ['NL', 'Netherlands'], ['IE', 'Ireland'], ['AE', 'United Arab Emirates'], ['SG', 'Singapore'], ['AU', 'Australia'], ['CA', 'Canada']]

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
