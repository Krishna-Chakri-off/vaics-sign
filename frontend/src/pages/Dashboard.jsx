import { Link, useNavigate } from 'react-router-dom'
import { FiPlus, FiArrowRight, FiEdit3, FiClock, FiCheckCircle, FiFileText } from 'react-icons/fi'
import api, { fmt } from '../api'
import { useAuth } from '../auth'
import { PageShell, Stat, Section, Alert, Empty, useAsync } from '../components/ui'

const greet = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening' }

export default function Dashboard() {
  const nav = useNavigate(); const { can, user } = useAuth()
  const { data: d, err } = useAsync(() => api.get('/envelopes/dashboard').then((r) => r.data))
  if (!d) return err ? <Alert>{err}</Alert> : <div className="text-slate-400">Loading…</div>
  const c = d.counts
  return (
    <PageShell eyebrow={new Date().toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' })} title={`${greet()}, ${user.full_name.split(' ')[0]}`}
      subtitle="Here is where your documents stand." right={can('envelopes.send') && <Link className="btn-primary" to="/envelopes/new"><FiPlus /> New document</Link>}>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Needs my action" value={d.waiting_for_me.length} onClick={() => nav('/envelopes?box=waiting_for_me')} />
        <Stat label="Waiting for others" value={d.waiting_for_others} onClick={() => nav('/envelopes?status=waiting_for_others')} />
        <Stat label="Completed" value={c.completed || 0} onClick={() => nav('/envelopes?status=completed')} />
        <Stat label="Drafts" value={c.draft || 0} onClick={() => nav('/envelopes?status=draft')} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <Section title="Recent activity" right={<Link to="/envelopes" className="inline-flex items-center gap-1 text-[13px] text-[#0D47A1] hover:underline">All documents <FiArrowRight /></Link>}>
          {d.recent.length === 0 ? <Empty icon={FiFileText} title="No activity yet" action={can('envelopes.send') && <Link className="btn-primary" to="/envelopes/new"><FiPlus /> Send your first document</Link>}>Upload a PDF, add the VAICS representative and the countersigner, and send it for signature.</Empty>
            : <ul className="-my-2 divide-y divide-gray-100">{d.recent.slice(0, 8).map((r, i) => (
              <li key={i}><button onClick={() => nav(`/envelopes/${r.envelope_id}`)} className="flex w-full items-center gap-4 py-3 text-left hover:bg-[#F7FAFF]">
                <span className="round flex h-9 w-9 shrink-0 items-center justify-center bg-[#F2F8FF] text-[#0D47A1]">{/sign|complet/.test(r.event) ? <FiCheckCircle /> : <FiEdit3 />}</span>
                <span className="min-w-0 flex-1"><span className="block truncate font-medium">{r.title}</span><span className="block truncate text-[13px] text-slate-500"><span className="capitalize">{r.event.replaceAll('_', ' ')}</span> · {r.actor}</span></span>
                <span className="shrink-0 text-[12px] text-slate-400">{fmt(r.created_at)}</span></button></li>))}</ul>}
        </Section>
        <div className="space-y-6">
          <Section title="Needs my signature">
            {d.waiting_for_me.length === 0 ? <p className="muted">Nothing is waiting for you.</p>
              : d.waiting_for_me.map((e) => <div key={e.id} className="border-l-2 border-[#0D47A1] bg-[#F7FAFF] px-3 py-2"><div className="font-medium">{e.title}</div><div className="text-[13px] text-slate-500">{e.public_id} · open the signing link from your email</div></div>)}
          </Section>
          <Section title="Expiring within 7 days">
            {d.expiring_soon.length === 0 ? <p className="muted">No documents are about to expire.</p>
              : d.expiring_soon.map((e) => <button key={e.id} onClick={() => nav(`/envelopes/${e.id}`)} className="flex w-full items-center gap-2 py-1 text-left hover:text-[#0D47A1]"><FiClock className="text-amber-600" /><span className="truncate">{e.title}</span></button>)}
          </Section>
        </div>
      </div>
    </PageShell>
  )
}
