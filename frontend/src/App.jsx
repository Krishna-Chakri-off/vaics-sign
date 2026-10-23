import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import SignDashboard from './pages/sign/SignDashboard'
import SignNew from './pages/sign/SignNew'
import SignDetail from './pages/sign/SignDetail'
import SignPublic from './pages/sign/SignPublic'
import SignOutbox from './pages/sign/SignOutbox'
import { API_URL } from './api'
import { useParams } from 'react-router-dom'
function SignDownload() { const { t } = useParams(); window.location.replace(`${API_URL}/sign/public/download/${t}`); return <p className="p-6">Downloading signed document…</p> }

function Protected({ children, roles }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-10 text-center text-slate-400">Authenticating…</div>
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/sign/:token" element={<SignPublic />} />
      <Route path="/sign-download/:t" element={<SignDownload />} />
      <Route element={<Protected><Layout /></Protected>}>












        <Route index element={<Navigate to="/vaics-sign" replace />} />
        <Route path="vaics-sign" element={<SignDashboard />} />
        <Route path="vaics-sign/new" element={<SignNew />} />
        <Route path="vaics-sign/outbox" element={<SignOutbox />} />
        <Route path="vaics-sign/:id" element={<SignDetail />} />
      </Route>
      <Route path="*" element={<Navigate to="/vaics-sign" replace />} />
    </Routes>
  )
}
