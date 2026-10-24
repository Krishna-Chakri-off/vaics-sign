import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate, Link } from 'react-router-dom'
import { FiGrid, FiInbox, FiEdit3, FiLayers, FiMail, FiUsers, FiSettings, FiShield, FiLogOut, FiBell, FiChevronLeft, FiChevronRight, FiUser, FiServer, FiCheckCircle, FiMenu } from 'react-icons/fi'
import { useAuth, ROLE_LABEL } from '../auth'
import api, { fmt } from '../api'
import { theme } from '../theme'

function Hero({ user, right }) {
  const org = user.org
  return (
    <div className="relative w-full shrink-0 overflow-hidden" style={{ minHeight: 120 }}>
      <img src={theme.hero} alt="" className="absolute inset-0 h-full w-full object-cover object-right" />
      <div className="relative z-10 flex min-h-[120px] flex-wrap items-start justify-between gap-4 px-6 py-4 sm:px-8">
        <div>
          <div className="text-[18px] font-semibold text-slate-900">{user.full_name}</div>
          <div className="mt-1.5 space-y-0.5 text-slate-500">
            <p>{org ? org.name : 'VAICS platform operations'}</p>
            <p>Role: {ROLE_LABEL[user.role] || user.role}</p>
          </div>
        </div>
        {right}
      </div>
    </div>
  )
}

export default function Layout() {
  const { user, logout, can, isPlatform } = useAuth()
  const nav = useNavigate()
  const [collapsed, setCollapsed] = useState(localStorage.getItem('vs_sidebar') === '1')
  const [mobile, setMobile] = useState(false)
  const [notes, setNotes] = useState([])
  const [open, setOpen] = useState(false)
  const load = () => { if (!isPlatform) api.get('/org/notifications').then((r) => setNotes(r.data)).catch(() => {}) }
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t) }, []) // eslint-disable-line
  const toggle = () => { setCollapsed(!collapsed); localStorage.setItem('vs_sidebar', collapsed ? '0' : '1') }
  const unread = notes.filter((n) => !n.read).length
  const groups = isPlatform ? [['VAICS platform', [['/platform', 'Tenants & health', FiServer]]], ['Account', [['/account', 'My account', FiUser]]]] : [
    ['VAICS Sign', [['/', 'Dashboard', FiGrid], ['/envelopes', 'Envelopes', FiInbox], can('envelopes.send') && ['/envelopes/new', 'New envelope', FiEdit3],
      ['/templates', 'Templates', FiLayers], ['/outbox', 'Email outbox', FiMail]]],
    ['Insights', [['/verify', 'Verify a document', FiCheckCircle]]],
    ['Administration', [can('users.manage') && ['/admin/users', 'Users & groups', FiUsers], can('settings.manage') && ['/admin/settings', 'Settings & branding', FiSettings],
      (can('audit.view') && user.role !== 'sender') && ['/admin/audit', 'Admin audit log', FiShield],
      can('privacy.manage') && ['/admin/privacy', 'Privacy & retention', FiShield], ['/account', 'My account', FiUser]]],
  ]
  const org = user.org
  const banner = org && (org.status === 'suspended' ? 'Your organization is suspended. Contact the VAICS administrator.' : !user.email_verified ? 'Verify your email address to send documents.' : '')
  const bell = (
    <div className="relative flex items-center gap-2">
      <button className="btn-secondary relative" onClick={() => setOpen(!open)} aria-label="Notifications"><FiBell />{unread > 0 && <span className="round absolute -top-1.5 -right-1.5 bg-[#E6007E] px-1.5 text-[10px] text-white">{unread}</span>}</button>
      {open && (
        <div className="absolute top-10 right-0 z-40 max-h-96 w-80 overflow-auto border border-gray-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2"><b>Notifications</b><button className="text-[#0D47A1]" onClick={async () => { await api.post('/org/notifications/read-all'); load() }}>Mark all read</button></div>
          {notes.length === 0 && <p className="p-3 text-slate-400">No notifications</p>}
          {notes.map((n) => <button key={n.id} onClick={() => { setOpen(false); if (n.envelope_id) nav(`/envelopes/${n.envelope_id}`) }} className={`block w-full px-3 py-2 text-left hover:bg-[#F2F8FF] ${n.read ? 'text-slate-400' : 'font-medium'}`}>{n.text}<div className="text-[11px] text-slate-400">{fmt(n.created_at)}</div></button>)}
        </div>
      )}
    </div>
  )
  const side = (
    <aside className="flex h-full flex-col overflow-hidden border-r border-blue-200 bg-white">
      <div className={`px-2 pt-2 ${collapsed ? 'pb-14' : 'pb-2 pr-10'}`}>
        {collapsed ? <img src={theme.logoIcon} alt="VAICS" className="round mx-auto h-10 w-10" />
          : <><img src={theme.logoFull} alt="VAICS" className="h-12 w-[168px] object-contain object-left" /><p className="mt-0.5 ml-0.5 truncate font-medium tracking-wide">{theme.appName}</p></>}
      </div>
      <nav className="flex-1 space-y-3 overflow-y-auto px-2 py-2">
        {groups.map(([g, links]) => (
          <div key={g}>
            {!collapsed && <div className="mb-1"><p className="px-2 font-semibold tracking-wider text-gray-400 uppercase">{g}</p><div className="mx-2 mt-1.5 border-t border-gray-200" /></div>}
            {links.filter(Boolean).map(([to, label, Icon]) => (
              <NavLink key={to} to={to} end onClick={() => setMobile(false)} title={collapsed ? label : undefined}
                className={({ isActive }) => `flex items-center font-medium ${collapsed ? 'justify-center px-2 py-2.5' : 'gap-2 px-2 py-2'} ${isActive ? 'bg-[#D6E8FF] text-[#0D47A1]' : 'text-[#0F172A] hover:bg-gray-50'}`}>
                <span className="shrink-0 text-[#E6007E]"><Icon className="h-5 w-5" strokeWidth={2.25} /></span>{!collapsed && <span className="truncate">{label}</span>}
              </NavLink>))}
          </div>))}
      </nav>
      <div className="border-t border-gray-200 p-3">
        {!collapsed && <><div className="font-semibold">{user.full_name}</div><div className="truncate text-slate-500">{user.email}</div></>}
        <button onClick={async () => { await logout(); nav('/login') }} className={`mt-2 flex items-center gap-2 font-medium text-slate-700 hover:text-[#0D47A1] ${collapsed ? 'mx-auto' : ''}`} title="Sign out"><FiLogOut className="text-[#E6007E]" />{!collapsed && 'Sign out'}</button>
      </div>
    </aside>
  )
  return (
    <div className="flex h-screen overflow-hidden bg-white">
      <div className="relative z-20 hidden h-screen shrink-0 md:block" style={{ width: collapsed ? 64 : 240, transition: 'width 200ms' }}>
        {side}
        <button onClick={toggle} aria-label="Toggle sidebar" className={`round absolute z-30 flex h-9 w-9 items-center justify-center border border-gray-300 bg-white shadow-sm hover:bg-gray-50 ${collapsed ? 'top-16 left-1/2 -translate-x-1/2' : 'top-8 right-0 translate-x-1/2 -translate-y-1/2'}`}>{collapsed ? <FiChevronRight /> : <FiChevronLeft />}</button>
      </div>
      {mobile && <div className="fixed inset-0 z-40 flex md:hidden" onClick={() => setMobile(false)}><div className="h-full w-64" onClick={(e) => e.stopPropagation()}>{side}</div><div className="flex-1 bg-slate-900/40" /></div>}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex items-center gap-2 border-b border-blue-200 px-3 py-2 md:hidden"><button className="btn-secondary" onClick={() => setMobile(true)} aria-label="Menu"><FiMenu /></button><img src={theme.logoFull} alt="VAICS" className="h-8" /></div>
        <Hero user={user} right={bell} />
        {banner && <div className="border-y border-amber-200 bg-amber-50 px-6 py-2 font-medium text-amber-800">{banner}</div>}
        <main className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6"><Outlet /><p className="mt-8 text-center text-slate-400">VAICS Sign · <Link className="underline hover:text-[#0D47A1]" to="/privacy">Privacy notice</Link></p></main>
      </div>
    </div>
  )
}

export function PublicShell({ brand, children, wide }) {
  return (
    <div className="min-h-screen bg-[#F2F8FF]">
      <header className="flex items-center gap-3 px-4 py-2" style={{ background: brand?.primary || '#0D47A1' }}>
        <img src={brand?.logo_url || '/vaics-logo-full.png'} alt={brand?.org_name || 'VAICS'} className="h-9 bg-white p-1" />
        <span className="font-semibold text-white">{brand?.product_name || 'VAICS Sign'}</span>
        <span className="ml-auto truncate text-white/80">{brand?.org_name}</span>
      </header>
      <main className={`mx-auto space-y-4 p-4 ${wide ? 'max-w-6xl' : 'max-w-5xl'}`}>{children}</main>
      <footer className="pb-6 text-center text-slate-400">Powered by VAICS Sign · <a className="underline" href="/verify">Verify a document</a> · <a className="underline" href="/privacy">Privacy notice</a></footer>
    </div>
  )
}
