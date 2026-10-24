import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, Link } from 'react-router-dom'
import { FiHome, FiFileText, FiPlus, FiLayers, FiCheckCircle, FiMail, FiUsers, FiSettings, FiShield, FiLock, FiLogOut, FiBell, FiMenu, FiUser } from 'react-icons/fi'
import { useAuth, ROLE_LABEL } from '../auth'
import api, { fmt } from '../api'
import { theme } from '../theme'

const initials = (n = '') => n.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join('').toUpperCase()

export function Footer({ className = '' }) {
  return (
    <footer className={`flex flex-wrap items-center justify-between gap-2 text-[12px] text-slate-400 ${className}`}>
      <span>© {new Date().getFullYear()} {theme.company} · {theme.appName} · Internal use</span>
      <span className="flex gap-4"><Link className="hover:text-[#0D47A1]" to="/privacy">Privacy notice</Link><Link className="hover:text-[#0D47A1]" to="/verify">Verify a document</Link></span>
    </footer>
  )
}

export default function Layout() {
  const { user, logout, can } = useAuth()
  const nav = useNavigate()
  const [mobile, setMobile] = useState(false)
  const [notes, setNotes] = useState([])
  const [open, setOpen] = useState(false)
  const load = () => api.get('/org/notifications').then((r) => setNotes(r.data)).catch(() => {})
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t) }, [])
  const unread = notes.filter((n) => !n.read).length
  const groups = [
    ['', [['/', 'Home', FiHome], ['/envelopes', 'Documents', FiFileText], ['/templates', 'Templates', FiLayers], ['/verify', 'Verify', FiCheckCircle]]],
    ['Administration', [can('users.manage') && ['/admin/users', 'People & roles', FiUsers], can('settings.manage') && ['/admin/settings', 'Organization', FiSettings],
      (can('audit.view') && ['org_admin', 'auditor'].includes(user.role)) && ['/admin/audit', 'Audit log', FiShield], can('privacy.manage') && ['/admin/privacy', 'Privacy & retention', FiLock],
      ['/outbox', 'Email outbox', FiMail]]],
  ]
  const side = (
    <aside className="flex h-full w-[248px] flex-col border-r border-[#E5E7EB] bg-white">
      <div className="flex items-center gap-3 px-6 pt-6 pb-5">
        <img src={theme.logoFull} alt="VAICS" className="h-9 w-auto object-contain" />
      </div>
      <div className="px-6 pb-4"><div className="text-[15px] font-semibold tracking-tight text-[#0D47A1]">{theme.appName}</div><div className="text-[12px] text-slate-400">E-signature · Internal</div></div>
      {can('envelopes.send') && <div className="px-4 pb-4"><Link to="/envelopes/new" onClick={() => setMobile(false)} className="btn-primary w-full"><FiPlus /> New document</Link></div>}
      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-2">
        {groups.map(([g, links]) => links.some(Boolean) && (
          <div key={g || 'main'} className="space-y-0.5">
            {g && <p className="eyebrow px-3 pb-2">{g}</p>}
            {links.filter(Boolean).map(([to, label, Icon]) => (
              <NavLink key={to} to={to} end={to === '/'} onClick={() => setMobile(false)}
                className={({ isActive }) => `flex items-center gap-3 border-l-2 px-3 py-2 text-[14px] transition-colors ${isActive ? 'border-[#0D47A1] bg-[#D6E8FF]/60 font-semibold text-[#0D47A1]' : 'border-transparent text-slate-600 hover:bg-[#F2F8FF] hover:text-[#0F172A]'}`}>
                <Icon className="h-[17px] w-[17px] shrink-0" />{label}
              </NavLink>))}
          </div>))}
      </nav>
      <div className="border-t border-[#E5E7EB] p-4">
        <Link to="/account" onClick={() => setMobile(false)} className="flex items-center gap-3 p-1 hover:bg-[#F2F8FF]">
          <span className="round flex h-9 w-9 shrink-0 items-center justify-center bg-[#0D47A1] text-[13px] font-semibold text-white">{initials(user.full_name)}</span>
          <span className="min-w-0"><span className="block truncate font-medium">{user.full_name}</span><span className="block truncate text-[12px] text-slate-500">{ROLE_LABEL[user.role] || user.role}</span></span>
        </Link>
        <button onClick={async () => { await logout(); nav('/login') }} className="mt-2 flex w-full items-center gap-2 px-1 py-1.5 text-[13px] text-slate-500 hover:text-[#0D47A1]"><FiLogOut /> Sign out</button>
      </div>
    </aside>
  )
  return (
    <div className="flex h-screen overflow-hidden bg-[#F7FAFF]">
      <div className="hidden h-screen shrink-0 lg:block">{side}</div>
      {mobile && <div className="fixed inset-0 z-40 flex lg:hidden" onClick={() => setMobile(false)}><div onClick={(e) => e.stopPropagation()}>{side}</div><div className="flex-1 bg-slate-900/30" /></div>}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-[#E5E7EB] bg-white/80 px-4 backdrop-blur sm:px-8">
          <button className="btn-ghost px-2 lg:hidden" onClick={() => setMobile(true)} aria-label="Menu"><FiMenu size={18} /></button>
          <img src={theme.logoFull} alt="VAICS" className="h-7 lg:hidden" />
          <div className="ml-auto flex items-center gap-2">
            {!user.email_verified && <span className="round hidden border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[12px] text-amber-800 sm:inline">Email not verified</span>}
            <div className="relative">
              <button className="btn-ghost relative px-2.5" onClick={() => setOpen(!open)} aria-label="Notifications"><FiBell size={18} />{unread > 0 && <span className="round absolute top-1.5 right-1.5 h-2 w-2 bg-[#E6007E]" />}</button>
              {open && (
                <div className="absolute top-11 right-0 z-40 max-h-[420px] w-[340px] overflow-auto border border-gray-200 bg-white shadow-xl">
                  <div className="flex items-center justify-between border-b border-gray-100 px-4 py-3"><b>Notifications</b>{notes.length > 0 && <button className="text-[13px] text-[#0D47A1]" onClick={async () => { await api.post('/org/notifications/read-all'); load() }}>Mark all read</button>}</div>
                  {notes.length === 0 && <p className="px-4 py-8 text-center text-slate-400">You're all caught up.</p>}
                  {notes.map((n) => <button key={n.id} onClick={() => { setOpen(false); if (n.envelope_id) nav(`/envelopes/${n.envelope_id}`) }} className={`block w-full border-b border-gray-50 px-4 py-3 text-left hover:bg-[#F2F8FF] ${n.read ? 'text-slate-400' : ''}`}>{n.text}<div className="mt-0.5 text-[12px] text-slate-400">{fmt(n.created_at)}</div></button>)}
                </div>
              )}
            </div>
            <Link to="/account" className="btn-ghost px-2.5" aria-label="My account"><FiUser size={18} /></Link>
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="px-4 py-8 sm:px-8 lg:px-12"><Outlet /><Footer className="mx-auto mt-16 max-w-6xl border-t border-[#E5E7EB] pt-6" /></div>
        </main>
      </div>
    </div>
  )
}

export function PublicShell({ brand, children, wide }) {
  return (
    <div className="flex min-h-screen flex-col bg-[#F7FAFF]">
      <header className="border-b border-[#E5E7EB] bg-white">
        <div className={`mx-auto flex h-16 items-center gap-4 px-4 ${wide ? 'max-w-6xl' : 'max-w-5xl'}`}>
          <img src={brand?.logo_url || theme.logoFull} alt={brand?.org_name || 'VAICS'} className="h-8" />
          <span className="h-6 w-px bg-[#E5E7EB]" />
          <span className="font-semibold text-[#0D47A1]">{brand?.product_name || theme.appName}</span>
          <span className="ml-auto hidden truncate text-[13px] text-slate-500 sm:block">{brand?.org_name}</span>
        </div>
        <div className="h-[2px] bg-gradient-to-r from-[#0D47A1] via-[#00B6F0] to-[#E6007E]" />
      </header>
      <main className={`mx-auto w-full flex-1 space-y-5 px-4 py-8 ${wide ? 'max-w-6xl' : 'max-w-5xl'}`}>{children}</main>
      <Footer className={`mx-auto w-full px-4 pb-8 ${wide ? 'max-w-6xl' : 'max-w-5xl'}`} />
    </div>
  )
}
