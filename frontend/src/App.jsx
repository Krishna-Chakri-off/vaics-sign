import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import { Login, VerifyEmail, ForgotPassword, ResetPassword, AcceptInvite, MfaEnrol } from './pages/AuthPages'
import Dashboard from './pages/Dashboard'
import Envelopes from './pages/Envelopes'
import EnvelopeDetail, { EnvelopeNew } from './pages/EnvelopeDetail'
import SignPortal from './pages/SignPortal'
import { CompletedAccess, VerifyPage, PrivacyNotice } from './pages/PublicPages'
import Templates, { Outbox } from './pages/Templates'
import { UsersGroups, SettingsBranding, AdminAudit, Privacy } from './pages/Admin'
import Account from './pages/Account'

// Phase 1: internal VAICS tool. SaaS surfaces (sign-up, billing, platform console, API/webhooks, PowerForms, bulk) are not routed.
function Private({ children }) {
  const { user, loading } = useAuth(); const loc = useLocation()
  if (loading) return <div className="p-10 text-slate-400">Loading…</div>
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/verify-email/:token" element={<VerifyEmail />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password/:token" element={<ResetPassword />} />
      <Route path="/invite/:token" element={<AcceptInvite />} />
      <Route path="/mfa-enrol" element={<MfaEnrol />} />
      <Route path="/s/:token" element={<SignPortal />} />
      <Route path="/completed/:token" element={<CompletedAccess />} />
      <Route path="/verify" element={<VerifyPage />} />
      <Route path="/privacy" element={<PrivacyNotice />} />
      <Route element={<Private><Layout /></Private>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/envelopes" element={<Envelopes />} />
        <Route path="/envelopes/new" element={<EnvelopeNew />} />
        <Route path="/envelopes/:id" element={<EnvelopeDetail />} />
        <Route path="/templates" element={<Templates />} />
        <Route path="/outbox" element={<Outbox />} />
        <Route path="/admin/users" element={<UsersGroups />} />
        <Route path="/admin/settings" element={<SettingsBranding />} />
        <Route path="/admin/audit" element={<AdminAudit />} />
        <Route path="/admin/privacy" element={<Privacy />} />
        <Route path="/account" element={<Account />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
