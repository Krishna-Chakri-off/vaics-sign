import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { pub, errMsg, fetchBuf } from '../api'
import { t, setLang, getLang, LANGS } from '../i18n'
import { PublicShell } from '../components/Layout'
import { Alert, Modal, Field, Tabs } from '../components/ui'
import PdfPages from '../components/PdfPages'

const STYLES = [['great_vibes', 'Great Vibes'], ['allura', 'Allura'], ['sacramento', 'Sacramento']]
const AUTO = ['date_signed', 'name', 'email', 'formula']
const nowStamp = () => { const d = new Date(); return `${d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'medium' })} IST | ${d.toISOString().replace('T', ' ').slice(0, 19)} UTC` }

function SignaturePad({ onChange }) {
  const c = useRef(null); const wrap = useRef(null); const pts = useRef([]); const strokes = useRef([]); const drawing = useRef(false)
  const [empty, setEmpty] = useState(true)
  const ink = '#000000'; const LW = 2.5
  const ctx = () => c.current.getContext('2d')
  const setup = () => {
    const el = c.current; if (!el) return; const r = el.getBoundingClientRect(); const dpr = window.devicePixelRatio || 1
    el.width = Math.round(r.width * dpr); el.height = Math.round(r.height * dpr)
    const x = ctx(); x.setTransform(dpr, 0, 0, dpr, 0, 0); x.lineCap = 'round'; x.lineJoin = 'round'; x.strokeStyle = ink; x.fillStyle = ink; x.lineWidth = LW
    strokes.current.forEach(drawStroke)
  }
  const drawStroke = (p) => {
    const x = ctx(); if (!p.length) return
    if (p.length < 3) { x.beginPath(); x.arc(p[0][0], p[0][1], LW / 2, 0, Math.PI * 2); x.fill(); if (p.length === 2) { x.beginPath(); x.moveTo(...p[0]); x.lineTo(...p[1]); x.stroke() } return }
    x.beginPath(); x.moveTo(...p[0])
    for (let i = 1; i < p.length - 1; i++) { const mx = (p[i][0] + p[i + 1][0]) / 2; const my = (p[i][1] + p[i + 1][1]) / 2; x.quadraticCurveTo(p[i][0], p[i][1], mx, my) }
    x.lineTo(...p[p.length - 1]); x.stroke()
  }
  useEffect(() => { setup(); const ro = new ResizeObserver(() => setup()); ro.observe(c.current); return () => ro.disconnect() }, []) // eslint-disable-line
  const pos = (e) => { const b = c.current.getBoundingClientRect(); return [e.clientX - b.left, e.clientY - b.top] }
  const redraw = () => { const el = c.current; const x = ctx(); x.save(); x.setTransform(1, 0, 0, 1, 0, 0); x.clearRect(0, 0, el.width, el.height); x.restore(); strokes.current.forEach(drawStroke) }
  const exportPng = () => {
    // Re-render strokes at 2x into an offscreen canvas, trim to the ink bounds (+ padding), transparent background.
    const all = strokes.current.flat(); if (!all.length) return ''
    const pad = 8; const S = 2
    const minX = Math.min(...all.map((p) => p[0])) - pad; const minY = Math.min(...all.map((p) => p[1])) - pad
    const maxX = Math.max(...all.map((p) => p[0])) + pad; const maxY = Math.max(...all.map((p) => p[1])) + pad
    const o = document.createElement('canvas'); o.width = Math.ceil((maxX - minX) * S); o.height = Math.ceil((maxY - minY) * S)
    const x = o.getContext('2d'); x.setTransform(S, 0, 0, S, -minX * S, -minY * S); x.lineCap = 'round'; x.lineJoin = 'round'; x.strokeStyle = ink; x.fillStyle = ink; x.lineWidth = LW
    const real = c.current; c.current = o; strokes.current.forEach(drawStroke); c.current = real
    return o.toDataURL('image/png')
  }
  const commit = () => { const has = strokes.current.some((p) => p.length); setEmpty(!has); onChange(has ? exportPng() : '') }
  const down = (e) => { e.preventDefault(); drawing.current = true; c.current.setPointerCapture(e.pointerId); pts.current = [pos(e)]; strokes.current.push(pts.current); redraw() }
  const move = (e) => {
    if (!drawing.current) return
    const evs = e.nativeEvent.getCoalescedEvents ? e.nativeEvent.getCoalescedEvents() : [e.nativeEvent]
    evs.forEach((ev) => { const q = pos(ev); const l = pts.current[pts.current.length - 1]; if (!l || Math.hypot(q[0] - l[0], q[1] - l[1]) > 0.8) pts.current.push(q) })
    redraw()
  }
  const up = () => { if (!drawing.current) return; drawing.current = false; commit() }
  const clear = () => { strokes.current = []; redraw(); setEmpty(true); onChange('') }
  const undo = () => { strokes.current.pop(); redraw(); commit() }
  return <div ref={wrap} className="space-y-2">
    <div className="relative w-full select-none border border-[#B8D0E8] bg-white shadow-inner" style={{ aspectRatio: '3 / 1', maxHeight: 220 }}>
      <div className="pointer-events-none absolute bottom-[26%] left-[6%] right-[6%] border-b border-dashed border-[#94A3B8]" />
      <span className="pointer-events-none absolute bottom-[27%] left-[6%] text-lg leading-none text-[#94A3B8]">✕</span>
      {empty && <span className="pointer-events-none absolute inset-x-0 top-[30%] text-center text-sm text-[#94A3B8]">Sign here</span>}
      <canvas ref={c} className="absolute inset-0 h-full w-full cursor-crosshair" style={{ touchAction: 'none' }} aria-label="Draw your signature"
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={up} onPointerLeave={up} />
    </div>
    <div className="flex items-center gap-2">
      <button type="button" className="btn-secondary" disabled={empty} onClick={undo}>Undo</button>
      <button type="button" className="btn-secondary" disabled={empty} onClick={clear}>{t('clear')}</button>
      <span className="ml-auto text-xs text-slate-500">Use your mouse, finger or stylus.</span>
    </div>
  </div>
}

function AdoptModal({ name, initial, allowed, onClose, onAdopt }) {
  const [kind, setKind] = useState(initial.kind || 'typed'); const [style, setStyle] = useState(initial.style || 'great_vibes'); const [image, setImage] = useState(initial.image || '')
  const [initials, setInitials] = useState(initial.initials || name.split(/\s+/).map((p) => p[0]).join('').toUpperCase())
  const [err, setErr] = useState('')
  const file = (f) => { if (!f) return; if (f.size > 500 * 1024) { setErr('Image must be under 500 KB'); return } const r = new FileReader(); r.onload = () => setImage(r.result); r.readAsDataURL(f) }
  const valid = kind === 'typed' || !!image
  return <Modal title={t('yourSig')} onClose={onClose} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-accent" disabled={!valid} onClick={() => onAdopt({ kind, style, image: kind === 'typed' ? null : image, initials })}>Adopt and sign</button></>}>
    <Tabs value={kind} onChange={(k) => { setKind(k); setImage('') }} tabs={[['typed', t('typed')], ['drawn', t('drawn')], ['uploaded', t('uploaded')]].filter(([k]) => allowed.includes(k))} />
    <Alert>{err}</Alert>
    {kind === 'typed' && <div className="space-y-1">{STYLES.map(([v, l]) => <label key={v} className={`flex cursor-pointer items-center gap-3 border p-2 ${style === v ? 'border-[#0D47A1] bg-[#F2F8FF]' : 'border-gray-200'}`}>
      <input type="radio" checked={style === v} onChange={() => setStyle(v)} /><span className={`sig-${v} min-w-0 flex-1 truncate border-b border-[#CBD5E1] px-1 pb-0.5 text-[34px] leading-[1.35] text-black`}>{name}</span><span className="ml-auto text-slate-400">{l}</span></label>)}</div>}
    {kind === 'drawn' && <SignaturePad onChange={setImage} />}
    {kind === 'uploaded' && <div><input type="file" accept="image/png,image/jpeg" onChange={(e) => file(e.target.files[0])} />{image && <div className="mt-2 flex h-24 items-center justify-center border bg-white p-1"><img src={image} alt="signature" className="max-h-full max-w-full object-contain" /></div>}</div>}
    <Field label="Initials"><input className="input" value={initials} maxLength={10} onChange={(e) => setInitials(e.target.value)} /></Field>
    <p className="text-slate-500">By adopting, you agree this mark is your electronic signature, legally equivalent to your handwritten signature for documents you sign here.</p>
  </Modal>
}

export default function SignPortal() {
  const { token } = useParams(); const [q] = useSearchParams(); const nav = useNavigate(); const kiosk = q.get('kiosk') === '1'
  const base = `/public/s/${token}`; const skey = `vs_${token}`
  const [info, setInfo] = useState(null); const [err, setErr] = useState(''); const [code, setCode] = useState(''); const [otpSent, setOtpSent] = useState('')
  const [sess, setSess] = useState(sessionStorage.getItem(skey) || ''); const [env, setEnv] = useState(null); const [bufs, setBufs] = useState({})
  const [values, setValues] = useState({}); const [reasons, setReasons] = useState({}); const [consent, setConsent] = useState(false); const [intent, setIntent] = useState(false); const [meaning, setMeaning] = useState('Approved'); const [sig, setSig] = useState(null)
  const [adopt, setAdopt] = useState(false); const [done, setDone] = useState(''); const [busy, setBusy] = useState(false); const [focus, setFocus] = useState(null); const [declining, setDeclining] = useState(false)
  const [, force] = useState(0); const refs = useRef({})
  const H = { headers: { 'X-Signer-Session': sess } }
  useEffect(() => { pub.get(base).then((r) => { setInfo(r.data); if (r.data.recipient.language && !localStorage.getItem('vs_lang')) setLang(r.data.recipient.language); force((x) => x + 1) }).catch((e) => setErr(errMsg(e))) }, [token]) // eslint-disable-line
  useEffect(() => {
    if (!sess) return
    pub.get(`${base}/envelope`, H).then((r) => {
      setEnv(r.data)
      const v = {}; const rs = {}
      r.data.fields.forEach((f) => { if (f.value != null && f.type !== 'signature') v[f.id] = f.value; else if (f.default_value && !['signature', 'initials'].includes(f.type)) v[f.id] = f.default_value; if (f.reason) rs[f.id] = f.reason })
      setValues(v); setReasons(rs)
      r.data.documents.forEach((d) => fetchBuf(`${base}/documents/${d.id}`, pub, H.headers).then((b) => setBufs((x) => ({ ...x, [d.id]: b }))).catch(() => {}))
    }).catch((e) => { if ([401, 403].includes(e?.response?.status)) { sessionStorage.removeItem(skey); setSess(''); setErr(errMsg(e)) } else setErr(errMsg(e)) })
  }, [sess]) // eslint-disable-line
  const startSession = (s) => { sessionStorage.setItem(skey, s); setSess(s) }
  const unlock = async (e) => { e.preventDefault(); setErr(''); setBusy(true); try { startSession((await pub.post(`${base}/unlock`, { code })).data.session) } catch (ex) { setErr(errMsg(ex)); setCode('') } finally { setBusy(false) } }
  const openNoCode = async () => { setErr(''); try { startSession((await pub.post(`${base}/open`)).data.session) } catch (ex) { setErr(errMsg(ex)) } }
  const sendOtp = async () => { setErr(''); try { const r = await pub.post(`${base}/otp`); setOtpSent(r.data.mode === 'dev_outbox' ? 'Development mode: the code was NOT delivered; it is in the sender\'s Email outbox.' : `Code sent by ${r.data.channel}.`) } catch (ex) { setErr(errMsg(ex)) } }

  const fields = env?.fields || []
  const active = (f) => { const c = f.condition || {}; return !c.field_id || String(values[c.field_id] ?? '') === String(c.equals ?? '') }
  const needs = (f) => {
    if (!active(f) || f.read_only || AUTO.includes(f.type)) return false
    if (f.type === 'signature') return !sig || (f.reason_required && !(reasons[f.id] || '').trim())
    if (f.type === 'initials') return !sig
    return f.required && !(values[f.id] ?? '').toString().trim()
  }
  const pending = fields.filter(needs)
  const order = useMemo(() => [...fields].sort((a, b) => (a.document_id - b.document_id) || (a.page - b.page) || (a.y - b.y) || (a.x - b.x)), [fields])
  const goNext = () => {
    const f = order.find(needs) || order[0]; if (!f) return; setFocus(f.id)
    const el = refs.current[f.id]; el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (['signature', 'initials'].includes(f.type) && !sig) setAdopt(true); else setTimeout(() => el?.querySelector('input,select')?.focus(), 400)
  }
  const finish = async () => {
    setErr(''); setBusy(true)
    try {
      const r = await pub.post(`${base}/finish`, { consent, intent, signature_meaning: meaning, signature: sig || { kind: 'typed' }, values, reasons }, H)
      sessionStorage.removeItem(skey); setDone(r.data.completed ? t('thanksDone') : t('thanksNext'))
    } catch (e) { setErr(errMsg(e)) } finally { setBusy(false) }
  }
  const saveLater = async () => { try { await pub.post(`${base}/save`, { values, reasons }, H); setDone(t('saved')) } catch (e) { setErr(errMsg(e)) } }
  const decline = async (reason) => { try { await pub.post(`${base}/decline`, { reason }, H); sessionStorage.removeItem(skey); setDeclining(false); setDone(t('declined')) } catch (e) { setErr(errMsg(e)) } }
  const brand = info?.branding
  const name = env?.recipient.name || info?.recipient.name || ''

  const sigMark = (f) => sig?.kind && sig.kind !== 'typed' && sig.image ? <img src={sig.image} alt="signature" className="h-full max-h-[64px] w-full object-contain object-left" />
    : f.type === 'initials' ? <span className={`sig-${sig?.style || 'great_vibes'} text-black`} style={{ fontSize: 'clamp(12px, 2vw, 22px)' }}>{sig?.initials || env.recipient.initials}</span>
      : <span className={`sig-${sig?.style || 'great_vibes'} truncate leading-tight text-black`} style={{ fontSize: 'clamp(14px, 2.4vw, 26px)' }}>{name}</span>
  const input = (f) => {
    const set = (v) => setValues({ ...values, [f.id]: v }); const v = values[f.id] ?? ''
    const cls = 'h-full w-full bg-transparent px-1 text-[11px] outline-none focus:bg-white'
    if (f.read_only) return <div className="px-1 text-[11px]">{v}</div>
    if (f.type === 'checkbox') return <input type="checkbox" className="m-auto block h-full" checked={v === 'true'} onChange={(e) => set(e.target.checked ? 'true' : '')} />
    if (f.type === 'radio') return <select className={cls} value={v} onChange={(e) => set(e.target.value)}><option value="">—</option>{(f.options || []).map((o) => <option key={o}>{o}</option>)}</select>
    if (f.type === 'dropdown') return <select className={cls} value={v} onChange={(e) => set(e.target.value)}><option value="">Select…</option>{(f.options || []).map((o) => <option key={o}>{o}</option>)}</select>
    if (f.type === 'date') return <input type="date" className={cls} value={v} onChange={(e) => set(e.target.value)} />
    if (f.type === 'attachment') return <input className={cls} placeholder="Reference / note (file upload not available)" value={v} onChange={(e) => set(e.target.value)} />
    return <input className={cls} inputMode={f.type === 'number' ? 'decimal' : undefined} placeholder={f.label || f.tooltip || f.type} value={v} onChange={(e) => set(e.target.value)} />
  }
  const overlay = (docId) => (page) => <>
    {(env.completed_fields || []).filter((f) => f.document_id === docId && f.page === page).map((f) => <div key={`o${f.id}`} title={`Completed by ${f.by} (read-only)`}
      className="pointer-events-none absolute flex flex-col overflow-hidden border border-dashed border-slate-400 bg-white/90 text-slate-700" style={{ left: `${f.x * 100}%`, top: `${f.y * 100}%`, width: `${f.w * 100}%`, height: `${f.h * 100}%` }}>
      {['signature', 'initials'].includes(f.type) ? <>
        <div className="flex min-h-0 flex-1 items-center px-1">{f.signature_image && f.signature_kind !== 'typed'
          ? <img src={f.signature_image} alt={`Signature of ${f.by}`} className="h-full max-h-[64px] w-full object-contain object-left" />
          : <span className={`sig-${f.signature_style || 'great_vibes'} truncate leading-tight text-black`} style={{ fontSize: f.type === 'initials' ? 'clamp(12px, 2vw, 22px)' : 'clamp(14px, 2.4vw, 26px)' }}>{f.type === 'initials' ? f.by.split(/\s+/).map((p) => p[0]).join('').toUpperCase() : f.by}</span>}</div>
        {f.type === 'signature' && <div className="px-1 pb-0.5 text-[9px] leading-tight text-slate-600">Name: {f.by}{f.reason ? <><br />Reason: {f.reason}</> : null}<br />Signed: {f.signed_at ? new Date(f.signed_at.endsWith('Z') ? f.signed_at : `${f.signed_at}Z`).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'medium' }) + ' IST' : '-'}</div>}
      </> : <div className="flex h-full items-center px-1 text-[11px]">{f.type === 'checkbox' ? (['true', '1', 'yes', 'on', 'X'].includes(f.value) ? '✓' : '') : `${f.value ?? ''}`}</div>}
      <span className="absolute right-0 top-0 bg-slate-600 px-1 text-[8px] uppercase tracking-wide text-white">Signed · {f.by}</span>
    </div>)}
    {fields.filter((f) => f.document_id === docId && f.page === page && active(f)).map((f) => {
      const need = needs(f)
      return <div key={f.id} ref={(el) => (refs.current[f.id] = el)} title={f.tooltip || f.label || ''} onClick={() => setFocus(f.id)}
        className={`absolute flex flex-col overflow-visible border-2 ${focus === f.id ? 'ring-4 ring-[#E6007E]/30' : ''} ${f.type === 'signature' ? 'bg-white/95' : 'bg-[#FFF7FB]/90'}`}
        style={{ left: `${f.x * 100}%`, top: `${f.y * 100}%`, width: `${f.w * 100}%`, minHeight: `${f.h * 100}%`, borderColor: need ? '#E6007E' : '#059669' }}>
        {f.type === 'signature' ? <>
          <button className="flex flex-1 items-center px-1 text-left" onClick={() => !sig && setAdopt(true)}>{sig ? sigMark(f) : <span className="font-semibold text-[#E6007E]">Click to sign</span>}</button>
          <div className="px-1 text-[9px] leading-tight text-slate-600">Name: {name}<br />{sig ? nowStamp() : 'Timestamp & SHA-256 added on signing'}</div>
          <input className="w-full border-t border-[#CBD5E1] bg-[#F2F8FF] px-1 py-0.5 text-[11px] outline-none focus:bg-white" placeholder={f.reason_required ? t('reason') : 'Reason (optional)'} value={reasons[f.id] || ''} onFocus={() => setFocus(f.id)} onChange={(e) => setReasons({ ...reasons, [f.id]: e.target.value })} />
        </> : f.type === 'initials' ? <button className="flex h-full items-center justify-center" onClick={() => !sig && setAdopt(true)}>{sig ? sigMark(f) : <span className="text-[10px] font-semibold text-[#E6007E]">Initial</span>}</button>
          : AUTO.includes(f.type) ? <div className="px-1 text-[11px] text-slate-600">{f.type === 'name' ? name : f.type === 'email' ? env.recipient.email : f.type === 'date_signed' ? new Date().toLocaleDateString('en-IN') : 'calculated'}</div>
            : input(f)}
      </div>
    })}</>

  return (
    <PublicShell brand={brand}>
      <div className="flex justify-end gap-2">{!kiosk && <select className="input !w-auto" value={getLang()} onChange={(e) => { setLang(e.target.value); force((x) => x + 1) }} aria-label={t('language')}>{LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>}</div>
      <Alert>{err}</Alert>
      {done ? <div className="card space-y-3 text-base font-medium text-green-800"><p>{done}</p>{kiosk && <button className="btn-primary" onClick={() => nav('/envelopes')}>Return the device to the host</button>}</div>
        : !sess ? info && (
          <div className="card mx-auto max-w-md space-y-3">
            <h1>{info.title}</h1>
            <p className="text-slate-500">{info.sender} ({info.sender_email}) sent you a document. Hello {info.recipient.name} (step {info.recipient.order}).</p>
            {info.recipient.locked ? <Alert>Too many incorrect codes. The sender has been alerted and must reissue your access.</Alert>
              : info.recipient.auth_method === 'none' ? <button className="btn-primary w-full" onClick={openNoCode}>Continue</button>
                : <form onSubmit={unlock} className="space-y-3">
                  {info.recipient.auth_method === 'access_code' ? <p>{t('enterCode')}</p> : <><button type="button" className="btn-secondary w-full" onClick={sendOtp}>{info.recipient.auth_method === 'sms_otp' ? t('sendSms') : t('sendCode')}</button>{otpSent && <Alert kind="ok">{otpSent}</Alert>}</>}
                  <input className="input text-center text-xl tracking-[0.4em]" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} placeholder="••••••" autoFocus aria-label="Code" />
                  <button className="btn-primary w-full" disabled={busy || code.length < 6}>{t('unlock')}</button>
                </form>}
            <details className="text-slate-500"><summary className="cursor-pointer">Privacy notice</summary><p className="mt-1 whitespace-pre-line">{info.privacy_text}</p></details>
          </div>)
          : env && <>
            <div className="card sticky top-0 z-10 space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <div className="mr-auto"><h1>{env.title}</h1><p className="text-slate-500">{name} · {env.envelope_id} · {pending.length ? t('fieldsLeft', { n: pending.length }) : '✓'}</p></div>
                <button className="btn-primary" onClick={goNext}>{pending.length === fields.length ? t('start') : pending.length ? t('next') : t('review')}</button>
                <button className="btn-accent" disabled={busy || pending.length > 0 || !consent || (env.recipient.type !== 'approver' && env.recipient.type !== 'viewer' && !intent)} onClick={finish}>{t('finish')}</button>
                <button className="btn-secondary" onClick={saveLater}>{t('later')}</button>
                <button className="btn-danger" onClick={() => setDeclining(true)}>{t('decline')}</button>
              </div>
              <div className="h-1.5 bg-[#D6E8FF]"><div className="h-full bg-[#E6007E]" style={{ width: `${fields.length ? (100 * (fields.length - pending.length)) / fields.length : 100}%` }} /></div>
              <label className="flex items-start gap-2"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5" /><span>{t('consent')}. <details className="inline"><summary className="inline cursor-pointer text-[#0D47A1]">Read the disclosure</summary><span className="mt-1 block whitespace-pre-line text-slate-500">{info?.consent_text}</span></details></span></label>
              {!['approver', 'viewer', 'editor'].includes(env.recipient.type) && <label className="flex flex-wrap items-center gap-2"><input type="checkbox" checked={intent} onChange={(e) => setIntent(e.target.checked)} />
                <span>I, <b>{name}</b>, intend to sign this document electronically. My signature means:</span>
                <select className="input !min-h-8 !w-auto !py-1" value={meaning} onChange={(e) => setMeaning(e.target.value)} aria-label="Signature meaning">{['Approved', 'Reviewed', 'Agreed', 'Authored', 'Acknowledged'].map((m) => <option key={m}>{m}</option>)}</select></label>}
              {sig && <div className="flex items-center gap-2 text-slate-500">Adopted signature: {sig.kind} {sig.kind === 'typed' && `(${sig.style})`} <button className="text-[#0D47A1]" onClick={() => setAdopt(true)}>Change</button></div>}
            </div>
            {(env.message || env.private_message) && <div className="card border-l-4 border-l-[#E6007E] whitespace-pre-line">{[env.message, env.private_message].filter(Boolean).join('\n\n')}</div>}
            <p className="text-slate-500">Click <b>{t('start')}</b> to be guided through each field. Enter a reason under every signature, tick the consent and signature-intent boxes, then <b>{t('finish')}</b>. Each signature is stamped with your name, reason, IST and UTC time and a SHA-256 hash.</p>
            {env.documents.map((d) => <div key={d.id} className="space-y-2">{env.documents.length > 1 && <h2>{d.name}</h2>}{bufs[d.id] ? <PdfPages data={bufs[d.id]} overlay={overlay(d.id)} /> : 'Loading document…'}</div>)}
          </>}
      {adopt && <AdoptModal name={name} initial={sig || {}} allowed={info?.allowed_signature_kinds || ['typed', 'drawn', 'uploaded']} onClose={() => setAdopt(false)} onAdopt={(s) => { setSig(s); setAdopt(false) }} />}
      {declining && <DeclineModal onClose={() => setDeclining(false)} onOk={decline} />}
    </PublicShell>)
}

function DeclineModal({ onClose, onOk }) {
  const [r, setR] = useState('')
  return <Modal title={t('decline')} onClose={onClose} footer={<><button className="btn-secondary" onClick={onClose}>Cancel</button><button className="btn-danger" disabled={!r.trim()} onClick={() => onOk(r)}>{t('decline')}</button></>}>
    <p>Declining ends this envelope for everyone. The sender will see your reason.</p>
    <Field label="Reason"><textarea className="input" rows={3} value={r} onChange={(e) => setR(e.target.value)} autoFocus /></Field></Modal>
}
