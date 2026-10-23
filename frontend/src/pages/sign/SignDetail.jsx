import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import api, { errMsg, fmt } from '../../api'
import { useAuth } from '../../auth'
import { PageShell, Alert, Field, Table } from '../../components/ui'
import { SBadge, openPdf, fetchBuf, SIGNER_COLORS } from './common'
import PdfPages from './PdfPages'

const DW = 0.28, DH = 0.09 // default field size (fraction of page)
const clamp = (v, a, b) => Math.max(a, Math.min(b, v))

export default function SignDetail() {
  const { id } = useParams(); const { user } = useAuth()
  const [d, setD] = useState(null); const [err, setErr] = useState(''); const [ok, setOk] = useState('')
  const [rs, setRs] = useState([]); const [fs, setFs] = useState([]); const [msg, setMsg] = useState(''); const [active, setActive] = useState(0); const [buf, setBuf] = useState(null)
  const drag = useRef(null); const [ghost, setGhost] = useState(null)
  const load = () => api.get(`/sign/documents/${id}`).then((r) => { const x = r.data; setD(x); setMsg(x.message)
    setRs(x.recipients.map((r2) => ({ name: r2.name, email: r2.email, id: r2.id })))
    setFs(x.fields.map((f) => ({ ...f, recipient_index: x.recipients.findIndex((r2) => r2.id === f.recipient_id) }))) }).catch((e) => setErr(errMsg(e)))
  useEffect(() => { load(); fetchBuf(`/sign/documents/${id}/file`).then(setBuf).catch((e) => setErr(errMsg(e))) }, [id])
  if (!d) return <Alert>{err || 'Loading…'}</Alert>
  const draft = d.status === 'draft'
  const payload = () => ({ message: msg, recipients: rs.map(({ name, email }) => ({ name, email })), fields: fs.map(({ recipient_index, page, x, y, w, h }) => ({ recipient_index, page, x, y, w, h })) })
  const save = async (quiet) => { setErr(''); setOk(''); try { await api.put(`/sign/documents/${id}`, payload()); if (!quiet) setOk('Draft saved'); await load(); return true } catch (e) { setErr(errMsg(e)); return false } }
  const generate = async () => { if (!(await save(true))) return; try { const r = await api.post(`/sign/documents/${id}/send`); setOk(r.data.email_mode === 'smtp' ? `Signer 1 has been emailed a link and a separate access code (handed to SMTP).` : 'SMTP is not configured — NO email was delivered. The link and access code for signer 1 are in the DEV EMAIL OUTBOX.'); load() } catch (e) { setErr(errMsg(e)) } }
  const act = async (u, okMsg) => { try { await api.post(u); setOk(okMsg || ''); load() } catch (e) { setErr(errMsg(e)) } }
  const move = (i, dir) => { const j = i + dir; if (j < 0 || j >= rs.length) return; const n = [...rs]; [n[i], n[j]] = [n[j], n[i]]; setRs(n)
    setFs(fs.map((f) => ({ ...f, recipient_index: f.recipient_index === i ? j : f.recipient_index === j ? i : f.recipient_index }))); setActive(j) }
  const removeSigner = (i) => { setRs(rs.filter((_, j) => j !== i)); setFs(fs.filter((f) => f.recipient_index !== i).map((f) => ({ ...f, recipient_index: f.recipient_index > i ? f.recipient_index - 1 : f.recipient_index }))); setActive(0) }

  // --- direct manipulation on the rendered page ---
  const rel = (e, el) => { const b = el.getBoundingClientRect(); return [clamp((e.clientX - b.left) / b.width, 0, 1), clamp((e.clientY - b.top) / b.height, 0, 1)] }
  const onDown = (page) => (e) => { if (!draft || !rs.length || e.button !== 0) return; const el = e.currentTarget; const [x, y] = rel(e, el); drag.current = { mode: 'new', page, el, x0: x, y0: y }; setGhost({ page, x, y, w: 0, h: 0 }) }
  const onBoxDown = (i, mode) => (e) => { if (!draft) return; e.stopPropagation(); const el = e.currentTarget.closest('[data-overlay]'); const [x, y] = rel(e, el); drag.current = { mode, i, el, x0: x, y0: y, f0: { ...fs[i] } } }
  const onMove = (e) => { const g = drag.current; if (!g) return; const [x, y] = rel(e, g.el)
    if (g.mode === 'new') setGhost({ page: g.page, x: Math.min(g.x0, x), y: Math.min(g.y0, y), w: Math.abs(x - g.x0), h: Math.abs(y - g.y0) })
    else if (g.mode === 'move') setFs(fs.map((f, j) => j === g.i ? { ...f, x: clamp(g.f0.x + x - g.x0, 0, 1 - f.w), y: clamp(g.f0.y + y - g.y0, 0, 1 - f.h) } : f))
    else setFs(fs.map((f, j) => j === g.i ? { ...f, w: clamp(g.f0.w + x - g.x0, 0.06, 1 - f.x), h: clamp(g.f0.h + y - g.y0, 0.03, 1 - f.y) } : f)) }
  const onUp = () => { const g = drag.current; drag.current = null; if (!g || g.mode !== 'new' || !ghost) { setGhost(null); return }
    let { x, y, w, h } = ghost; if (w < 0.04 || h < 0.02) { w = DW; h = DH; x = clamp(g.x0 - DW / 2, 0, 1 - DW); y = clamp(g.y0 - DH / 2, 0, 1 - DH) }
    setFs([...fs, { recipient_index: active, page: g.page, x: +x.toFixed(4), y: +y.toFixed(4), w: +w.toFixed(4), h: +h.toFixed(4) }]); setGhost(null) }
  const overlay = (page) => (
    <div data-overlay className={`absolute inset-0 ${draft ? 'cursor-crosshair' : ''}`} onMouseDown={onDown(page)} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
      {fs.map((f, i) => f.page === page && (
        <div key={i} className="absolute border-2 bg-white/60" style={{ left: `${f.x * 100}%`, top: `${f.y * 100}%`, width: `${f.w * 100}%`, height: `${f.h * 100}%`, borderColor: SIGNER_COLORS[f.recipient_index % 5], cursor: draft ? 'move' : 'default' }} onMouseDown={onBoxDown(i, 'move')}>
          <div className="truncate px-1 text-[10px] font-semibold text-white" style={{ background: SIGNER_COLORS[f.recipient_index % 5] }}>Signature · {rs[f.recipient_index]?.name || `Signer ${f.recipient_index + 1}`}{f.signed_at ? ' ✓' : ''}</div>
          {draft && <><button className="absolute -top-2 -right-2 h-4 w-4 rounded-full bg-red-600 text-[10px] leading-4 text-white" onMouseDown={(e) => e.stopPropagation()} onClick={() => setFs(fs.filter((_, j) => j !== i))}>×</button>
            <span className="absolute right-0 bottom-0 h-3 w-3 cursor-se-resize" style={{ background: SIGNER_COLORS[f.recipient_index % 5] }} onMouseDown={onBoxDown(i, 'resize')} /></>}
        </div>))}
      {ghost && ghost.page === page && <div className="absolute border-2 border-dashed" style={{ left: `${ghost.x * 100}%`, top: `${ghost.y * 100}%`, width: `${ghost.w * 100}%`, height: `${ghost.h * 100}%`, borderColor: SIGNER_COLORS[active % 5] }} />}
    </div>)
  const current = d.recipients.find((r) => r.status !== 'signed')
  return (
    <PageShell title={d.title} subtitle={<span>Envelope VS-{String(d.id).padStart(6, '0')} · requester {d.owner} (CC) · <SBadge s={d.status} /></span>}
      right={<>{d.status === 'completed' && <button className="btn-accent" onClick={() => openPdf(`/sign/documents/${id}/completed`)}>Download signed PDF</button>}
        <Link className="btn-secondary" to="/vaics-sign/outbox">Email outbox</Link>
        {!['completed', 'cancelled', 'declined', 'draft'].includes(d.status) && <button className="btn-danger" onClick={() => confirm('Cancel this document? All links and codes will be revoked.') && act(`/sign/documents/${id}/cancel`)}>Cancel</button>}</>}>
      <Alert>{err}</Alert><Alert kind="ok">{ok}</Alert>
      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <div className="space-y-4 lg:sticky lg:top-2 lg:self-start">
          <div className="card space-y-2"><h2>Signers (strict order)</h2>
            {rs.map((r, i) => <div key={i} className={`space-y-1 border p-2 ${draft && active === i ? 'border-[#0D47A1] bg-[#F2F8FF]' : 'border-gray-200'}`} onClick={() => setActive(i)}>
              <div className="flex items-center justify-between"><b style={{ color: SIGNER_COLORS[i % 5] }}>Signer {i + 1}{i === 0 ? ' · VAICS representative' : i === 1 ? ' · Countersigner' : ''}</b>
                {draft ? <span className="flex gap-1"><button className="btn-secondary !min-h-0 !px-1.5 !py-0" onClick={() => move(i, -1)}>↑</button><button className="btn-secondary !min-h-0 !px-1.5 !py-0" onClick={() => move(i, 1)}>↓</button><button className="btn-secondary !min-h-0 !px-1.5 !py-0" onClick={() => removeSigner(i)}>✕</button></span>
                  : <SBadge s={d.recipients[i]?.status} />}</div>
              <input disabled={!draft} className="input" placeholder="Full name" value={r.name} onChange={(e) => setRs(rs.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
              <input disabled={!draft} className="input" placeholder="Email" value={r.email} onChange={(e) => setRs(rs.map((x, j) => j === i ? { ...x, email: e.target.value } : x))} />
              <div className="text-slate-500">{fs.filter((f) => f.recipient_index === i).length} signature field(s){d.recipients[i]?.signed_at && ` · signed ${fmt(d.recipients[i].signed_at)}`}{d.recipients[i]?.code_locked && <b className="text-red-700"> · LOCKED (wrong codes)</b>}</div>
              {!draft && current?.id === d.recipients[i]?.id && ['sent', 'viewed'].includes(current.status) && <button className="btn-secondary w-full" onClick={() => act(`/sign/documents/${id}/recipients/${current.id}/resend`, 'New link and new access code issued; previous ones revoked.')}>Revoke & reissue link + code</button>}
            </div>)}
            {draft && <button className="btn-secondary w-full" onClick={() => { setRs([...rs, { name: '', email: '' }]); setActive(rs.length) }}>+ Add signer</button>}
            <div className="border-t border-gray-200 pt-2 text-slate-500">CC (automatic): {d.owner} &lt;{d.owner_email || user?.email}&gt; receives the completed PDF.</div>
          </div>
          {draft && <div className="card space-y-2"><h2>Place signature fields</h2>
            <p className="text-slate-500">Select a signer above, then <b>click</b> on the document to drop a field or <b>drag</b> to draw one. Drag a field to move it, use its corner to resize, × to remove. Each signer can have multiple fields.</p>
            <Field label="Message to signers (optional)"><textarea className="input" rows={2} value={msg} onChange={(e) => setMsg(e.target.value)} /></Field>
            <div className="flex gap-2"><button className="btn-secondary" onClick={() => save()}>Save draft</button><button className="btn-accent flex-1" onClick={generate}>Generate</button></div>
            <p className="text-slate-500">Generate emails signer 1 a signing link and, separately, an access code. Signer 2 is notified only after signer 1 finishes.</p>
          </div>}
        </div>
        <div className="card overflow-x-auto bg-[#F2F8FF]">{buf ? <PdfPages data={buf} overlay={overlay} /> : 'Loading PDF…'}</div>
      </div>
      <div><h2 className="mb-2">Audit trail</h2>
        <Table rows={d.audit} cols={[{ k: 'created_at', label: 'Time', render: (e) => fmt(e.created_at) }, { k: 'event', label: 'Event' }, { k: 'actor', label: 'Actor' }, { k: 'ip', label: 'IP' }, { k: 'detail', label: 'Detail', render: (e) => <span className="break-all">{e.detail}</span> }, { k: 'entry_hash', label: 'Entry hash', render: (e) => <code title={e.entry_hash}>{e.entry_hash.slice(0, 12)}…</code> }]} />
        <p className="mt-1 break-all text-slate-500">Original SHA-256: <code>{d.original_sha256}</code>{d.completed_sha256 && <> · Signed PDF SHA-256: <code>{d.completed_sha256}</code></>}</p></div>
    </PageShell>)
}
