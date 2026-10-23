import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import { Login, Signup, VerifyEmail, ForgotPassword, ResetPassword, AcceptInvite, MfaEnrol } from './pages/AuthPages'
import Dashboard from './pages/Dashboard'
import Envelopes from './pages/Envelopes'
import EnvelopeDetail, { EnvelopeNew } from './pages/EnvelopeDetail'
import SignPortal from './pages/SignPortal'
import { CompletedAccess, PowerFormPublic, VerifyPage } from './pages/PublicPages'
import Templates, { Bulk, PowerForms, Outbox, Reports } from './pages/Templates'
import { UsersGroups, SettingsBranding, Integrations, AdminAudit, Privacy, Billing } from './pages/Admin'
import Account from './pages/Account'
import Platform from './pages/Platform'

function Private({ children, platform }) {
  const { user, loading } = useAuth(); const loc = useLocation()
  if (loading) return <div className="p-8 text-slate-500">Loading…</div>
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />
  if (platform && user.role !== 'platform_admin') return <Navigate to="/" replace />
  if (!platform && user.role === 'platform_admin' && !['/account'].includes(loc.pathname)) return <Navigate to="/platform" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/verify-email/:token" element={<VerifyEmail />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password/:token" element={<ResetPassword />} />
      <Route path="/invite/:token" element={<AcceptInvite />} />
      <Route path="/mfa-enrol" element={<MfaEnrol />} />
      <Route path="/s/:token" element={<SignPortal />} />
      <Route path="/completed/:token" element={<CompletedAccess />} />
      <Route path="/pf/:slug" element={<PowerFormPublic />} />
      <Route path="/verify" element={<VerifyPage />} />
      <Route element={<Private><Layout /></Private>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/envelopes" element={<Envelopes />} />
        <Route path="/envelopes/new" element={<EnvelopeNew />} />
        <Route path="/envelopes/:id" element={<EnvelopeDetail />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/bulk" element={<Bulk />} />
        <Route path="/powerforms" element={<PowerForms />} />
        <Route path="/outbox" element={<Outbox />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/admin/users" element={<UsersGroups />} />
        <Route path="/admin/settings" element={<SettingsBranding />} />
        <Route path="/admin/integrations" element={<Integrations />} />
        <Route path="/admin/audit" element={<AdminAudit />} />
        <Route path="/admin/privacy" element={<Privacy />} />
        <Route path="/admin/billing" element={<Billing />} />
        <Route path="/account" element={<Account />} />
      </Route>
      <Route element={<Private platform><Layout /></Private>}><Route path="/platform" element={<Platform />} /></Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
