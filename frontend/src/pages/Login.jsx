import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { errMsg } from '../api'
import { theme } from '../theme'
import { Alert } from '../components/ui'

const DEMO = [['requester', 'Requester'], ['manager', 'Sender (Manager)'], ['approver', 'Tech Approver'], ['cab', 'CAB Member'], ['implementer', 'Implementer'], ['admin', 'Admin']]

export default function Login() {
  const { user, login } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/vaics-sign" replace />
  const submit = async (e) => { e.preventDefault(); setBusy(true); setErr(''); try { await login(email, password); nav('/vaics-sign') } catch (ex) { setErr(errMsg(ex)) } finally { setBusy(false) } }
  return (
    <div className="relative flex min-h-screen items-center justify-center p-6">
      <img src={theme.hero} alt="" className="absolute inset-0 h-full w-full object-cover" />
      <form onSubmit={submit} className="relative w-full max-w-sm border border-[#B8D0E8] bg-white p-6 shadow-lg">
        <img src={theme.logoFull} alt="VAICS" className="mb-1 h-12" />
        <p className="mb-5 font-medium tracking-wide">{theme.appName}</p>
        <Alert>{err}</Alert>
        <label className="label mt-3">Email</label>
        <input className="input mb-3" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
        <label className="label">Password</label>
        <input className="input mb-4" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <button className="btn-primary w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <div className="mt-5 border-t pt-3">
          <p className="mb-2 text-slate-500">Demo accounts (password Demo@123)</p>
          <div className="flex flex-wrap gap-1.5">{DEMO.map(([u, l]) => <button type="button" key={u} className="btn-secondary !min-h-0 !py-1" onClick={() => { setEmail(`${u}@vaics.com`); setPassword('Demo@123') }}>{l}</button>)}</div>
        </div>
      </form>
    </div>
  )
}
