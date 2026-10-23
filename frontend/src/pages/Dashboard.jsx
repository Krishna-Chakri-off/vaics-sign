import { Link, useNavigate } from 'react-router-dom'
import api, { fmt } from '../api'
import { useAuth } from '../auth'
import { PageShell, Stat, Section, Table, useAsync, Alert } from '../components/ui'

export default function Dashboard() {
  const nav = useNavigate(); const { can, user } = useAuth()
  const { data: d, err } = useAsync(() => api.get('/envelopes/dashboard').then((r) => r.data))
  if (!d) return <Alert>{err || 'Loading…'}</Alert>
  const c = d.counts; const u = d.usage
  return (
    <PageShell title="Dashboard" subtitle={`Welcome, ${user.full_name}`} right={can('envelopes.send') && <Link className="btn-accent" to="/envelopes/new">+ New envelope</Link>}>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Stat label="Waiting for me" value={d.waiting_for_me.length} onClick={() => nav('/envelopes?box=waiting_for_me')} />
        <Stat label="Waiting for others" value={d.waiting_for_others} onClick={() => nav('/envelopes?status=waiting_for_others')} />
        <Stat label="Completed" value={c.completed || 0} onClick={() => nav('/envelopes?status=completed')} />
        <Stat label="Drafts" value={c.draft || 0} onClick={() => nav('/envelopes?status=draft')} />
        <Stat label="Declined" value={c.declined || 0} onClick={() => nav('/envelopes?status=declined')} />
        <Stat label="Expiring in 7 days" value={d.expiring_soon.length} onClick={() => nav('/envelopes?status=expiring_soon')} />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <Section title="Recent activity">
          <Table rows={d.recent.map((r, i) => ({ ...r, id: i }))} onRow={(r) => nav(`/envelopes/${r.envelope_id}`)} empty="No activity yet. Create your first envelope."
            cols={[{ label: 'When', render: (r) => fmt(r.created_at) }, { label: 'Envelope', k: 'title' }, { label: 'Event', render: (r) => r.event.replaceAll('_', ' ') }, { label: 'By', k: 'actor' }]} />
        </Section>
        <div className="space-y-4">
          {d.waiting_for_me.length > 0 && <Section title="Needs your signature">{d.waiting_for_me.map((e) => <div key={e.id} className="border-b py-1.5 last:border-0">{e.title} <span className="text-slate-400">{e.public_id}</span><div className="text-slate-500">Open the signing link from your email.</div></div>)}</Section>}
          <Section title="Usage this month" right={can('billing.manage') && <Link className="text-[#0D47A1]" to="/admin/billing">Plan & billing</Link>}>
            {[['Envelopes', u.envelopes], ['SMS', u.sms], ['API calls', u.api_calls], ['Seats', u.seats]].map(([l, m]) => (
              <div key={l} className="mb-2"><div className="flex justify-between"><span>{l}</span><span>{m.used} / {m.limit ?? '∞'}{m.credits ? ` (+${m.credits} credits)` : ''}</span></div>
                {m.limit ? <div className="mt-1 h-1.5 bg-[#D6E8FF]"><div className="h-full" style={{ width: `${Math.min(100, (100 * m.used) / m.limit)}%`, background: m.used / m.limit >= 0.8 ? '#E6007E' : '#0D47A1' }} /></div> : null}</div>))}
          </Section>
        </div>
      </div>
    </PageShell>
  )
}
