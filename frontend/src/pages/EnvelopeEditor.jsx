import { useEffect, useRef, useState } from 'react'
import api, { errMsg, fetchBuf } from '../api'
import { useAuth } from '../auth'
import { Alert, Field, COLORS, Modal , ask } from '../components/ui'
import PdfPages from '../components/PdfPages'

const clamp = (v, a, b) => Math.max(a, Math.min(b, v))
export const FIELD_TYPES = [
  ['signature', 'Signature', 0.28, 0.09], ['initials', 'Initials', 0.1, 0.06], ['date_signed', 'Date signed', 0.18, 0.035], ['name', 'Full name', 0.25, 0.035], ['email', 'Email', 0.25, 0.035],
  ['company', 'Company', 0.25, 0.035], ['title', 'Title', 0.2, 0.035], ['text', 'Text', 0.25, 0.035], ['number', 'Number', 0.15, 0.035], ['date', 'Date', 0.15, 0.035],
  ['checkbox', 'Checkbox', 0.03, 0.022], ['radio', 'Radio', 0.03, 0.022], ['dropdown', 'Dropdown', 0.2, 0.035], ['attachment', 'Attachment', 0.2, 0.04], ['stamp', 'Company stamp', 0.18, 0.1], ['formula', 'Formula', 0.15, 0.035],
]
const FT = Object.fromEntries(FIELD_TYPES.map((x) => [x[0], x]))
// DocuSign-style essential palette; other types stay supported for existing envelopes but are not offered
const PALETTE = ['signature', 'initials', 'date_signed', 'name', 'email', 'company', 'title', 'text', 'checkbox', 'stamp']
const isRep = (r) => /vaics/i.test(r?.role_name || '')
const repIndex = (rs) => { const i = rs.findIndex(isRep); return i >= 0 ? i : 0 }
const RTYPES = [['signer', 'Needs to sign'], ['approver', 'Approver'], ['viewer', 'Needs to view'], ['cc', 'Receives a copy (CC)'], ['in_person', 'In-person signer'], ['witness', 'Witness']]
const AUTH = [['access_code', 'Access code (sent separately)'], ['email_otp', 'Email one-time code'], ['none', 'Email link only']]

export default function EnvelopeEditor({ env, reload }) {
  const { user } = useAuth()
  const [title, setTitle] = useState(env.title); const [message, setMessage] = useState(env.message || '')
  const [rs, setRs] = useState(env.recipients.length ? env.recipients.map((r) => ({ ...r, access_code: '' })) : [
    { name: '', email: '', order: 1, type: 'signer', auth_method: 'access_code', role_name: 'VAICS representative' },
    { name: '', email: '', order: 2, type: 'signer', auth_method: 'access_code', role_name: 'Countersigner' }])
  const [fs, setFs] = useState(env.fields.map((f) => ({ ...f, ri: env.recipients.findIndex((r) => r.id === f.recipient_id) })))
  const [expires, setExpires] = useState(env.expires_at ? env.expires_at.slice(0, 10) : '')
  const [rem, setRem] = useState({ first: env.reminder_first_days, every: env.reminder_every_days })
  const [labels, setLabels] = useState((env.labels || []).join(', '))
  const [active, setActive] = useState(0); const [ftype, setFtype] = useState('signature'); const [selF, setSelF] = useState(null)
  const [doc, setDoc] = useState(env.documents[0]?.id); const [buf, setBuf] = useState(null)
  const [err, setErr] = useState(''); const [errs, setErrs] = useState([]); const [ok, setOk] = useState(''); const [busy, setBusy] = useState(false)
  const [members, setMembers] = useState([]); const [confirmSend, setConfirmSend] = useState(false)
  const drag = useRef(null); const [ghost, setGhost] = useState(null)
  const [stampOk, setStampOk] = useState(null)
  useEffect(() => { api.get('/org/branding/stamp').then((r) => setStampOk(!!r.data.configured)).catch(() => {}) }, [])
  useEffect(() => { api.get('/org/users').then((r) => setMembers(r.data)).catch(() => {}) }, [])
  useEffect(() => { if (!doc && env.documents[0]) setDoc(env.documents[0].id) }, [env.documents]) // eslint-disable-line
  useEffect(() => { setBuf(null); if (doc) fetchBuf(`/envelopes/${env.id}/documents/${doc}/file`).then(setBuf).catch((e) => setErr(errMsg(e))) }, [doc, env.id])

  const payload = (quietDraft = false) => { const keep = (i) => !quietDraft || !!((rs[i]?.name || '').trim() || (rs[i]?.email || '').trim()); return ({
    title, message, labels: labels.split(',').map((s) => s.trim()).filter(Boolean), expires_at: expires ? `${expires}T23:59:00` : null,
    reminder_first_days: +rem.first, reminder_every_days: +rem.every,
    recipients: rs.map((r, i) => ({ r, i })).filter(({ i }) => keep(i)).map(({ r, i }) => ({ client_id: String(i), name: r.name, email: r.email, phone: r.phone || null, order: +r.order || 1, type: r.type, role_name: r.role_name || null,
      auth_method: r.type === 'in_person' ? 'none' : r.auth_method, access_code: r.access_code || null, host_user_id: r.host_user_id || null, private_message: r.private_message || '', language: r.language || 'en', signature_type: r.signature_type || 'electronic' })),
    fields: fs.filter((f) => f.ri >= 0 && f.ri < rs.length && keep(f.ri)).map((f) => ({ recipient: String(f.ri), document_id: f.document_id, type: f.type, page: f.page, x: f.x, y: f.y, w: f.w, h: f.h,
      required: f.required ?? true, reason_required: f.reason_required ?? true, label: f.label || null, options: f.options || [], validation: f.validation || null, default_value: f.default_value || null,
      read_only: !!f.read_only, formula: f.formula || null, group_name: f.group_name || null, tooltip: f.tooltip || null, condition: f.condition || {} })),
  }) }
  const save = async (quiet) => { setErr(''); setErrs([]); setOk(''); try { await api.put(`/envelopes/${env.id}`, payload(!!quiet && quiet !== 'send')); if (!quiet) { setOk('Draft saved'); reload() } return true } catch (e) { setErr(errMsg(e)); return false } }
  const send = async () => {
    setConfirmSend(false); setBusy(true)
    if (!(await save('send'))) { setBusy(false); return }
    try {
      const r = await api.post(`/envelopes/${env.id}/send`)
      reload(r.data.email_mode === 'smtp' ? 'Sent. The first recipient(s) were emailed a link and, separately, an access code (accepted by the SMTP relay; delivery is not guaranteed).'
        : 'SMTP is not configured — NO email was delivered. The links and access codes are in the Email outbox (development mode).')
    } catch (e) { setErr(errMsg(e)); setErrs(e?.response?.data?.detail?.errors || []); reload() } finally { setBusy(false) }
  }
  const upload = async (files) => {
    setErr(''); setBusy(true)
    try { for (const f of files) { if (!/\.pdf$/i.test(f.name)) throw new Error(`${f.name} is not a PDF. Only PDF files can be uploaded.`); const fd = new FormData(); fd.append('file', f); await api.post(`/envelopes/${env.id}/documents`, fd) } await save(true); reload() } catch (e) { setErr(errMsg(e)) } finally { setBusy(false) }
  }
  const removeDoc = async (id) => { if (!await ask('Remove this document and its fields?')) return; try { setFs(fs.filter((f) => f.document_id !== id)); await api.delete(`/envelopes/${env.id}/documents/${id}`); if (doc === id) setDoc(null); reload() } catch (e) { setErr(errMsg(e)) } }
  const moveDoc = async (i, dir) => { const ids = env.documents.map((d) => d.id); const j = i + dir; if (j < 0 || j >= ids.length) return; [ids[i], ids[j]] = [ids[j], ids[i]]; await api.post(`/envelopes/${env.id}/documents/reorder`, { document_ids: ids }); reload() }
  const setR = (i, k, v) => setRs(rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  const removeR = (i) => { setRs(rs.filter((_, j) => j !== i)); setFs(fs.filter((f) => f.ri !== i).map((f) => ({ ...f, ri: f.ri > i ? f.ri - 1 : f.ri }))); setActive(0) }
  const canSign = (r) => ['signer', 'in_person', 'witness'].includes(r?.type)

  // ---- field placement on the rendered page (pointer events: mouse, pen and touch) ----
  const rel = (e, el) => { const b = el.getBoundingClientRect(); return [clamp((e.clientX - b.left) / b.width, 0, 1), clamp((e.clientY - b.top) / b.height, 0, 1)] }
  const onDown = (page) => (e) => {
    if (!rs.length || e.button > 0) return
    if (['signature', 'initials'].includes(ftype) && !canSign(rs[active])) { setErr(`${rs[active].name || 'This recipient'} (${rs[active].type}) cannot have signature fields.`); return }
    const el = e.currentTarget; el.setPointerCapture?.(e.pointerId); const [x, y] = rel(e, el); drag.current = { mode: 'new', page, el, x0: x, y0: y }; setGhost({ page, x, y, w: 0, h: 0 })
  }
  const onBoxDown = (i, mode) => (e) => { e.stopPropagation(); setSelF(i); const el = e.currentTarget.closest('[data-overlay]'); el.setPointerCapture?.(e.pointerId); const [x, y] = rel(e, el); drag.current = { mode, i, el, x0: x, y0: y, f0: { ...fs[i] } } }
  const onMove = (e) => {
    const g = drag.current; if (!g) return; const [x, y] = rel(e, g.el)
    if (g.mode === 'new') setGhost({ page: g.page, x: Math.min(g.x0, x), y: Math.min(g.y0, y), w: Math.abs(x - g.x0), h: Math.abs(y - g.y0) })
    else if (g.mode === 'move') setFs(fs.map((f, j) => (j === g.i ? { ...f, x: clamp(g.f0.x + x - g.x0, 0, 1 - f.w), y: clamp(g.f0.y + y - g.y0, 0, 1 - f.h) } : f)))
    else setFs(fs.map((f, j) => (j === g.i ? { ...f, w: clamp(g.f0.w + x - g.x0, 0.02, 1 - f.x), h: clamp(g.f0.h + y - g.y0, 0.015, 1 - f.y) } : f)))
  }
  const onUp = () => {
    const g = drag.current; drag.current = null
    if (!g || g.mode !== 'new' || !ghost) { setGhost(null); return }
    const [, , DW, DH] = FT[ftype]; let { x, y, w, h } = ghost
    if (w < 0.02 || h < 0.012) { w = DW; h = DH; x = clamp(g.x0 - DW / 2, 0, 1 - DW); y = clamp(g.y0 - DH / 2, 0, 1 - DH) }
    const f = { ri: ftype === 'stamp' ? repIndex(rs) : active, document_id: doc, type: ftype, page: g.page, x: +x.toFixed(4), y: +y.toFixed(4), w: +w.toFixed(4), h: +h.toFixed(4), required: !['checkbox', 'formula'].includes(ftype), reason_required: ftype === 'signature', options: ftype === 'dropdown' || ftype === 'radio' ? ['Option 1', 'Option 2'] : [] }
    setFs([...fs, f]); setSelF(fs.length); setGhost(null)
  }
  const overlay = (page) => (
    <div data-overlay className="absolute inset-0 cursor-crosshair" style={{ touchAction: 'none' }} onPointerDown={onDown(page)} onPointerMove={onMove} onPointerUp={onUp}>
      {fs.map((f, i) => f.document_id === doc && f.page === page && (
        <div key={i} className={`group absolute ${selF === i ? 'outline outline-1 outline-offset-2' : ''}`} style={{ left: `${f.x * 100}%`, top: `${f.y * 100}%`, width: `${f.w * 100}%`, height: `${f.h * 100}%`, outlineColor: COLORS[f.ri % COLORS.length], cursor: 'move', border: `1.5px dotted ${COLORS[f.ri % COLORS.length]}`, borderRadius: 4, backgroundColor: `${COLORS[f.ri % COLORS.length]}0F` }} onPointerDown={onBoxDown(i, 'move')}>
          <div className="pointer-events-none truncate px-0.5 text-[9px] font-medium leading-tight" style={{ color: COLORS[f.ri % COLORS.length] }}>{f.type === 'signature' ? 'Sign here' : f.type === 'initials' ? 'Initial here' : f.type === 'stamp' ? 'Company stamp' : FT[f.type]?.[1]}{f.required ? '*' : ''} · {rs[f.ri]?.role_name || rs[f.ri]?.name || `Recipient ${f.ri + 1}`}</div>
          <button className={`absolute -top-1.5 -right-1.5 h-3.5 w-3.5 rounded-full border border-slate-300 bg-white text-[9px] leading-3 text-slate-500 shadow-sm hover:border-red-400 hover:text-red-600 ${selF === i ? 'flex' : 'hidden group-hover:flex'} items-center justify-center`} onPointerDown={(e) => e.stopPropagation()} onClick={() => { setFs(fs.filter((_, j) => j !== i)); setSelF(null) }} aria-label="Remove field">×</button>
          <span className={`absolute -right-1 -bottom-1 h-2 w-2 cursor-se-resize rounded-full border border-white shadow-sm ${selF === i ? 'block' : 'hidden group-hover:block'}`} style={{ background: COLORS[f.ri % COLORS.length] }} onPointerDown={onBoxDown(i, 'resize')} />
        </div>))}
      {ghost && ghost.page === page && <div className="absolute border-2 border-dashed" style={{ left: `${ghost.x * 100}%`, top: `${ghost.y * 100}%`, width: `${ghost.w * 100}%`, height: `${ghost.h * 100}%`, borderColor: COLORS[active % COLORS.length] }} />}
    </div>)
  const sf = selF != null ? fs[selF] : null
  const setSf = (k, v) => setFs(fs.map((f, j) => (j === selF ? { ...f, [k]: v } : f)))
  const orders = rs.filter((r) => r.type !== 'cc').map((r) => +r.order)
  const parallel = new Set(orders).size < orders.length
  return (
    <div className="space-y-4">
      <Alert>{err}</Alert>{errs.length > 1 && <ul className="list-disc border border-red-200 bg-red-50 py-2 pl-8 text-red-800">{errs.map((x) => <li key={x}>{x}</li>)}</ul>}<Alert kind="ok">{ok}</Alert>
      <div className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <div className="space-y-4 xl:sticky xl:top-0 xl:max-h-[calc(100vh-220px)] xl:overflow-y-auto">
          <div className="card space-y-2">
            <h2>1 · Documents</h2>
            {env.documents.map((d, i) => (
              <div key={d.id} className={`flex items-center gap-1 border p-1.5 ${doc === d.id ? 'border-[#0D47A1] bg-[#F2F8FF]' : 'border-gray-200'}`}>
                <button className="flex-1 truncate text-left" onClick={() => setDoc(d.id)} title={d.sha256}>{i + 1}. {d.name} <span className="text-slate-400">· {d.pages.length} p</span></button>
                <button className="btn-secondary !min-h-0 !px-1.5 !py-0" onClick={() => moveDoc(i, -1)}>↑</button><button className="btn-secondary !min-h-0 !px-1.5 !py-0" onClick={() => moveDoc(i, 1)}>↓</button>
                <button className="btn-secondary !min-h-0 !px-1.5 !py-0" onClick={() => removeDoc(d.id)}>✕</button>
              </div>))}
            <label className="btn-secondary w-full cursor-pointer">{busy ? 'Working…' : '+ Add PDF documents'}<input type="file" multiple hidden accept="application/pdf,.pdf" onChange={(e) => upload([...e.target.files])} /></label>
          </div>
          <div className="card space-y-2">
            <div className="flex items-center justify-between"><h2>2 · Recipients</h2><span className="text-slate-500">{parallel ? 'Parallel steps in use' : 'Strict order'}</span></div>
            <p className="text-slate-500">Recipients with the same order number act in parallel; lower numbers go first.</p>
            {rs.map((r, i) => (
              <div key={i} className={`space-y-1 border p-2 ${active === i ? 'border-[#0D47A1] bg-[#F2F8FF]' : 'border-gray-200'}`} onClick={() => setActive(i)}>
                <div className="flex items-center gap-2">
                  <span className="round h-3 w-3 shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                  <input className="input !w-14" type="number" min={1} value={r.order} onChange={(e) => setR(i, 'order', e.target.value)} title="Routing order" />
                  <input className="input" placeholder="Role (e.g. VAICS representative)" value={r.role_name || ''} onChange={(e) => setR(i, 'role_name', e.target.value)} />
                  <button className="btn-secondary !min-h-0 !px-1.5 !py-0.5" onClick={(e) => { e.stopPropagation(); removeR(i) }} aria-label="Remove recipient">✕</button>
                </div>
                <input className="input" placeholder="Full name" value={r.name} onChange={(e) => setR(i, 'name', e.target.value)} />
                <input className="input" placeholder="Email" type="email" value={r.email} onChange={(e) => setR(i, 'email', e.target.value)} />
                <div className="grid grid-cols-2 gap-1">
                  <select className="input" value={r.type} onChange={(e) => setR(i, 'type', e.target.value)}>{[...RTYPES, ...(RTYPES.some(([v]) => v === r.type) ? [] : [[r.type, r.type]])].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
                  {r.type === 'in_person' ? <select className="input" value={r.host_user_id || ''} onChange={(e) => setR(i, 'host_user_id', +e.target.value || null)}><option value="">Host…</option>{members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}</select>
                    : <select className="input" value={r.auth_method} onChange={(e) => setR(i, 'auth_method', e.target.value)}>{[...AUTH, ...(AUTH.some(([v]) => v === r.auth_method) ? [] : [[r.auth_method, r.auth_method]])].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>}
                </div>
                {active === i && <>
                  {r.auth_method === 'sms_otp' && <input className="input" placeholder="Mobile (+91…)" value={r.phone || ''} onChange={(e) => setR(i, 'phone', e.target.value)} />}
                  {r.auth_method === 'access_code' && <input className="input" placeholder="Optional: your own 6–8 digit code (share it yourself)" value={r.access_code || ''} onChange={(e) => setR(i, 'access_code', e.target.value.replace(/\D/g, ''))} maxLength={8} />}
                  <input className="input" placeholder="Private message to this recipient" value={r.private_message || ''} onChange={(e) => setR(i, 'private_message', e.target.value)} />
                </>}
                <div className="text-slate-500">{fs.filter((f) => f.ri === i).length} field(s)</div>
              </div>))}
            <button className="btn-secondary w-full" onClick={() => { setRs([...rs, { name: '', email: '', order: Math.max(0, ...rs.map((r) => +r.order)) + 1, type: 'signer', auth_method: 'access_code' }]); setActive(rs.length) }}>+ Add recipient</button>
            <div className="border-t border-gray-200 pt-2 text-slate-500">You ({user.email}) automatically receive the completed PDF and certificate.</div>
          </div>
          <div className="card space-y-2">
            <h2>3 · Fields</h2>
            <p className="text-slate-500">Select a recipient, pick a field type, then <b>click</b> (or tap) the page to drop it or <b>drag</b> to draw it. Drag to move, corner to resize.</p>
            {fs.some((f) => f.type === 'stamp') && stampOk === false && <div className="border border-amber-300 bg-amber-50 p-2 text-amber-900">No official company stamp is configured. An org admin must upload it in Settings before this envelope can be sent.</div>}
            <div className="flex flex-wrap gap-1">{FIELD_TYPES.filter(([v]) => PALETTE.includes(v)).map(([v, l]) => <button key={v} className={`border px-2 py-1 ${ftype === v ? 'border-[#0D47A1] bg-[#0D47A1] text-white' : 'border-gray-300 bg-white'}`} onClick={() => setFtype(v)}>{l}</button>)}</div>
            {sf && <div className="space-y-1 border border-[#B8D0E8] bg-[#F2F8FF] p-2">
              <b>Selected: {FT[sf.type][1]} · {rs[sf.ri]?.name}</b>
              {sf.type === 'stamp' ? <div className="text-slate-600">Applied by: {rs[sf.ri]?.role_name || rs[sf.ri]?.name} (internal signer only). The official stamp image set by your admin is placed when they sign.</div>
                : <select className="input" value={sf.ri} onChange={(e) => setSf('ri', +e.target.value)}>{rs.map((r, i) => <option key={i} value={i}>Assign to: {r.name || `Recipient ${i + 1}`}</option>)}</select>}
              <input className="input" placeholder="Label (also used for prefill/CSV columns)" value={sf.label || ''} onChange={(e) => setSf('label', e.target.value)} />
              <input className="input" placeholder="Tooltip / help text" value={sf.tooltip || ''} onChange={(e) => setSf('tooltip', e.target.value)} />
              <label className="flex gap-2"><input type="checkbox" checked={sf.required ?? true} onChange={(e) => setSf('required', e.target.checked)} /> Required</label>
              {sf.type === 'signature' && <label className="flex gap-2"><input type="checkbox" checked={sf.reason_required ?? true} onChange={(e) => setSf('reason_required', e.target.checked)} /> Reason required</label>}
              {['text', 'number', 'date', 'company', 'title'].includes(sf.type) && <>
                <input className="input" placeholder="Default / prefilled value" value={sf.default_value || ''} onChange={(e) => setSf('default_value', e.target.value)} />
                <label className="flex gap-2"><input type="checkbox" checked={!!sf.read_only} onChange={(e) => setSf('read_only', e.target.checked)} /> Read-only (sender prefill)</label>
                <select className="input" value={sf.validation || ''} onChange={(e) => setSf('validation', e.target.value || null)}>{[['', 'No validation'], ['email', 'Email'], ['phone', 'Phone'], ['pan', 'PAN (India)'], ['gstin', 'GSTIN (India)'], ['pincode', 'PIN code'], ['number', 'Number']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></>}
              {['dropdown', 'radio'].includes(sf.type) && <input className="input" placeholder="Options, comma separated" value={(sf.options || []).join(', ')} onChange={(e) => setSf('options', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))} />}
              {sf.type === 'radio' && <input className="input" placeholder="Radio group name" value={sf.group_name || ''} onChange={(e) => setSf('group_name', e.target.value)} />}
              {sf.type === 'formula' && <input className="input" placeholder="Formula, e.g. {12} * {13}  (field ids)" value={sf.formula || ''} onChange={(e) => setSf('formula', e.target.value)} />}
              {sf.id && <div className="text-slate-400">Field id {sf.id}</div>}
            </div>}
          </div>
          <div className="card space-y-2">
            <h2>4 · Message & options</h2>
            <Field label="Envelope title"><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
            <Field label="Message to all recipients"><textarea className="input" rows={2} value={message} onChange={(e) => setMessage(e.target.value)} /></Field>
            <div className="grid grid-cols-3 gap-2">
              <Field label="Expires on"><input className="input" type="date" value={expires} onChange={(e) => setExpires(e.target.value)} /></Field>
              <Field label="First reminder (days)"><input className="input" type="number" min={0} value={rem.first} onChange={(e) => setRem({ ...rem, first: e.target.value })} /></Field>
              <Field label="Repeat every (days)"><input className="input" type="number" min={0} value={rem.every} onChange={(e) => setRem({ ...rem, every: e.target.value })} /></Field>
            </div>
            <Field label="Labels (comma separated)"><input className="input" value={labels} onChange={(e) => setLabels(e.target.value)} /></Field>
            <div className="flex gap-2"><button className="btn-secondary" onClick={() => save()}>Save draft</button><button className="btn-accent flex-1" disabled={busy} onClick={() => setConfirmSend(true)}>Generate & send</button></div>
            <p className="text-slate-500">Generate emails the first recipient(s) a signing link and, separately, an access code. Later recipients are notified only when it is their turn.</p>
          </div>
        </div>
        <div className="card overflow-x-auto bg-[#F2F8FF]">
          {env.documents.length > 1 && <div className="mb-3 flex flex-wrap gap-1">{env.documents.map((d) => <button key={d.id} className={`border px-2 py-1 ${doc === d.id ? 'border-[#0D47A1] bg-[#0D47A1] text-white' : 'border-gray-300 bg-white'}`} onClick={() => setDoc(d.id)}>{d.name}</button>)}</div>}
          {!env.documents.length ? <div className="py-20 text-center text-slate-500">Add a document to start placing fields.</div> : buf ? <PdfPages data={buf} overlay={overlay} /> : 'Loading document…'}
        </div>
      </div>
      {confirmSend && <Modal title="Send this envelope?" onClose={() => setConfirmSend(false)} footer={<><button className="btn-secondary" onClick={() => setConfirmSend(false)}>Cancel</button><button className="btn-accent" onClick={send}>Send now</button></>}>
        <p>{rs.length} recipient(s), {fs.length} field(s), {env.documents.length} document(s).</p>
        <ol className="list-decimal pl-5">{[...rs].sort((a, b) => a.order - b.order).map((r, i) => <li key={i}>Step {r.order}: {r.name} &lt;{r.email}&gt; · {r.type} · {r.type === 'in_person' ? 'hosted' : r.auth_method}</li>)}</ol>
      </Modal>}
    </div>
  )
}
