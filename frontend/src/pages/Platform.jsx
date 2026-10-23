import { useState } from 'react'
import api, { errMsg, fmt } from '../api'
import { PageShell, Section, Alert, Table, SBadge, Tabs, Modal, Field, useAsync } from '../components/ui'

export default function Platform() {
  const [tab, setTab] = useState('tenants'); const [m, setM] = useState({}); const run = async (fn, ok) => { setM({}); try { const r = await fn(); setM({ ok }); return r } catch (e) { setM({ err: errMsg(e) }) } }
  const [q, setQ] = useState('')
  const ten = useAsync(() => api.get('/platform/tenants', { params: { q } }).then((r) => r.data), [q])
  const health = useAsync(() => api.get('/platform/health').then((r) => r.data))
  const plans = useAsync(() => api.get('/platform/plans').then((r) => r.data))
  const log = useAsync(() => api.get('/platform/audit-log').then((r) => r.data))
  const [assign, setAssign] = useState(null); const [plan, setPlan] = useState(null)
  const H = health.data
  return (
    <PageShell title="VAICS platform console" subtitle="Tenant operations. Customer document content is not visible here.">
      <Alert>{m.err}</Alert><Alert kind="ok">{m.ok}</Alert>
      <Tabs value={tab} onChange={setTab} tabs={[['tenants', 'Tenants'], ['health', 'Health & providers'], ['plans', 'Plans'], ['log', 'Platform audit log']]} />
      {tab === 'tenants' && <>
        <input className="input max-w-sm" placeholder="Search tenants" onKeyDown={(e) => e.key === 'Enter' && setQ(e.target.value)} />
        <Table rows={ten.data || []} cols={[{ label: 'Tenant', render: (t) => <div><b>{t.name}</b><div className="text-slate-400">{t.slug} · {t.country} · region {t.region}</div></div> }, { label: 'Status', render: (t) => <SBadge s={t.status} /> },
          { label: 'Plan', k: 'plan' }, { label: 'Seats', render: (t) => `${t.users}/${t.seats}` }, { label: 'Envelopes', k: 'envelopes' }, { label: 'Created', render: (t) => fmt(t.created_at) },
          { label: 'Support access', render: (t) => (t.support_access_until ? `until ${fmt(t.support_access_until)}` : 'none') },
          { label: '', render: (t) => <div className="flex flex-wrap gap-1">
            {t.status !== 'suspended' ? <button className="btn-danger" onClick={() => { const reason = prompt('Suspension reason'); if (reason) run(() => api.post(`/platform/tenants/${t.id}/status`, { status: 'suspended', reason }), 'Suspended').then(ten.reload) }}>Suspend</button>
              : <button className="btn-secondary" onClick={() => run(() => api.post(`/platform/tenants/${t.id}/status`, { status: 'active' }), 'Reactivated').then(ten.reload)}>Reactivate</button>}
            <button className="btn-secondary" onClick={() => setAssign({ id: t.id, plan: t.plan || 'business', seats: t.seats, trial_days: '' })}>Assign plan</button>
            <button className="btn-secondary" onClick={() => confirm(`Close ${t.name}? Data becomes read-only and is purged after 30 days.`) && run(() => api.post(`/platform/tenants/${t.id}/status`, { status: 'closed', reason: 'closed by platform' }), 'Closed').then(ten.reload)}>Close</button></div> }]} />
      </>}
      {tab === 'health' && H && <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Services">{[['Database', `${H.database} (${H.dialect})`], ['Storage', H.storage], ['Email', H.email === 'smtp' ? 'SMTP configured' : 'DEV OUTBOX (nothing delivered)'], ['SMS', H.sms], ['Document seal', H.seal], ['Malware scan', H.malware_scan]].map(([k, v]) => <div key={k} className="flex justify-between border-b py-1"><span>{k}</span><b>{v}</b></div>)}</Section>
        <Section title="Volume">{[['Tenants', H.tenants], ['Users', H.users], ['Envelopes', H.envelopes], ['Sent this month', H.envelopes_this_month]].map(([k, v]) => <div key={k} className="flex justify-between border-b py-1"><span>{k}</span><b>{v}</b></div>)}</Section>
        <Section title="Signature providers (trust services)">{H.signature_providers.map((p) => <div key={p.code} className="flex justify-between border-b py-1"><span>{p.label}</span><span>{p.implemented ? 'implemented' : 'NOT IMPLEMENTED'} · {p.configured ? 'configured' : 'not configured'}</span></div>)}</Section>
        <Section title="Payment providers">{Object.entries(H.payment_providers).map(([k, v]) => <div key={k} className="flex justify-between border-b py-1"><span>{k}</span><b>{v ? 'configured' : 'not configured (no live billing)'}</b></div>)}</Section>
      </div>}
      {tab === 'plans' && <><button className="btn-accent" onClick={() => setPlan({ code: '', name: '', description: '', features: {}, limits: {}, prices: {}, is_public: false, is_custom: true, active: true, _new: true })}>+ Custom plan</button>
        <Table rows={plans.data || []} onRow={(p) => setPlan(p)} cols={[{ label: 'Code', k: 'code' }, { label: 'Name', k: 'name' }, { label: 'Public', render: (p) => (p.is_public ? 'Yes' : 'No') }, { label: 'Envelopes/mo', render: (p) => p.limits.envelopes_per_month }, { label: 'Prices', render: (p) => JSON.stringify(p.prices) }]} /></>}
      {tab === 'log' && <Table rows={log.data || []} cols={[{ label: 'Time', render: (r) => fmt(r.created_at) }, { label: 'Actor', k: 'actor_email' }, { label: 'Action', k: 'action' }, { label: 'Target', k: 'target' }, { label: 'IP', k: 'ip' }]} />}
      {assign && <Modal title="Assign plan" onClose={() => setAssign(null)} footer={<button className="btn-primary" onClick={() => run(() => api.post(`/platform/tenants/${assign.id}/plan`, { plan: assign.plan, seats: +assign.seats || null, trial_days: +assign.trial_days || null, po_reference: assign.po || null }), 'Plan assigned').then(() => { setAssign(null); ten.reload() })}>Assign</button>}>
        <Field label="Plan"><select className="input" value={assign.plan} onChange={(e) => setAssign({ ...assign, plan: e.target.value })}>{(plans.data || []).map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}</select></Field>
        <Field label="Seats"><input className="input" type="number" value={assign.seats} onChange={(e) => setAssign({ ...assign, seats: e.target.value })} /></Field>
        <Field label="Trial days (blank = activate now on invoice terms)"><input className="input" type="number" value={assign.trial_days} onChange={(e) => setAssign({ ...assign, trial_days: e.target.value })} /></Field>
        <Field label="PO reference"><input className="input" value={assign.po || ''} onChange={(e) => setAssign({ ...assign, po: e.target.value })} /></Field>
      </Modal>}
      {plan && <PlanModal plan={plan} onClose={() => setPlan(null)} onSave={(p) => run(() => (p._new ? api.post('/platform/plans', p) : api.put(`/platform/plans/${p.code}`, p)), 'Plan saved').then(() => { setPlan(null); plans.reload() })} />}
    </PageShell>)
}

function PlanModal({ plan, onClose, onSave }) {
  const [p, setP] = useState(plan); const [j, setJ] = useState({ features: JSON.stringify(plan.features, null, 1), limits: JSON.stringify(plan.limits, null, 1), prices: JSON.stringify(plan.prices, null, 1) }); const [err, setErr] = useState('')
  const save = () => { try { onSave({ ...p, features: JSON.parse(j.features), limits: JSON.parse(j.limits), prices: JSON.parse(j.prices) }) } catch { setErr('Invalid JSON') } }
  return <Modal title={p._new ? 'New plan' : `Edit plan ${p.code}`} onClose={onClose} footer={<button className="btn-primary" onClick={save}>Save</button>}>
    <Alert>{err}</Alert>
    {p._new && <Field label="Code"><input className="input" value={p.code} onChange={(e) => setP({ ...p, code: e.target.value })} /></Field>}
    <Field label="Name"><input className="input" value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} /></Field>
    <Field label="Description"><input className="input" value={p.description} onChange={(e) => setP({ ...p, description: e.target.value })} /></Field>
    {['features', 'limits', 'prices'].map((k) => <Field key={k} label={`${k} (JSON)`}><textarea className="input font-mono" rows={4} value={j[k]} onChange={(e) => setJ({ ...j, [k]: e.target.value })} /></Field>)}
    <label className="flex gap-2"><input type="checkbox" checked={p.is_public} onChange={(e) => setP({ ...p, is_public: e.target.checked })} /> Public (self-service)</label>
    <label className="flex gap-2"><input type="checkbox" checked={p.active} onChange={(e) => setP({ ...p, active: e.target.checked })} /> Active</label>
  </Modal>
}
