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
  const c = useRef(null); const drawing = useRef(false)
  useEffect(() => { const x = c.current.getContext('2d'); x.lineWidth = 2.4; x.lineCap = 'round'; x.strokeStyle = '#0D47A1' }, [])
  const pos = (e) => { const b = c.current.getBoundingClientRect(); return [(e.clientX - b.left) * (c.current.width / b.width), (e.clientY - b.top) * (c.current.height / b.height)] }
  return <div>
    <canvas ref={c} width={600} height={180} className="w-full border border-[#B8D0E8] bg-white" style={{ touchAction: 'none' }}
      onPointerDown={(e) => { drawing.current = true; c.current.setPointerCapture(e.pointerId); const x = c.current.getContext('2d'); x.beginPath(); x.moveTo(...pos(e)) }}
      onPointerMove={(e) => { if (!drawing.current) return; const x = c.current.getContext('2d'); x.lineTo(...pos(e)); x.stroke() }}
      onPointerUp={() => { drawing.current = false; onChange(c.current.toDataURL('image/png')) }} />
    <button className="btn-secondary mt-1" onClick={() => { c.current.getContext('2d').clearRect(0, 0, 600, 180); onChange('') }}>{t('clear')}</button>
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
      <input type="radio" checked={style === v} onChange={() => setStyle(v)} /><span className={`sig-${v} text-[30px] text-[#0D47A1]`}>{name}</span><span className="ml-auto text-slate-400">{l}</span></label>)}</div>}
    {kind === 'drawn' && <SignaturePad onChange={setImage} />}
    {kind === 'uploaded' && <div><input type="file" accept="image/png,image/jpeg" onChange={(e) => file(e.target.files[0])} />{image && <img src={image} alt="signature" className="mt-2 max-h-24 border" />}</div>}
    <Field label="Initials"><input className="input" value={initials} maxLength={10} onChange={(e) => setInitials(e.target.value)} /></Field>
    <p className="text-slate-500">By adopting, you agree this mark is your electronic signature, legally equivalent to your handwritten signature for documents you sign here.</p>
  </Modal>
}

export default function SignPortal() {
  const { token } = useParams(); const [q] = useSearchParams(); const nav = useNavigate(); const kiosk = q.get('kiosk') === '1'
  const base = `/public/s/${token}`; const skey = `vs_${token}`
  const [info, setInfo] = useState(null); const [err, setErr] = useState(''); const [code, setCode] = useState(''); const [otpSent, setOtpSent] = useState('')
  const [sess, setSess] = useState(sessionStorage.getItem(skey) || ''); const [env, setEnv] = useState(null); const [bufs, setBufs] = useState({})
  const [values, setValues] = useState({}); const [reasons, setReasons] = useState({}); const [consent, setConsent] = useState(false); const [sig, setSig] = useState(null)
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
      const r = await pub.post(`${base}/finish`, { consent, signature: sig || { kind: 'typed' }, values, reasons }, H)
      sessionStorage.removeItem(skey); setDone(r.data.completed ? t('thanksDone') : t('thanksNext'))
    } catch (e) { setErr(errMsg(e)) } finally { setBusy(false) }
  }
  const saveLater = async () => { try { await pub.post(`${base}/save`, { values, reasons }, H); setDone(t('saved')) } catch (e) { setErr(errMsg(e)) } }
  const decline = async (reason) => { try { await pub.post(`${base}/decline`, { reason }, H); sessionStorage.removeItem(skey); setDeclining(false); setDone(t('declined')) } catch (e) { setErr(errMsg(e)) } }
  const brand = info?.branding
  const name = env?.recipient.name || info?.recipient.name || ''

  const sigMark = (f) => sig?.kind && sig.kind !== 'typed' && sig.image ? <img src={sig.image} alt="signature" className="h-[60%] max-w-full object-contain" />
    : f.type === 'initials' ? <span className={`sig-${sig?.style || 'great_vibes'} text-[#0D47A1]`} style={{ fontSize: 'clamp(12px, 2vw, 22px)' }}>{sig?.initials || env.recipient.initials}</span>
      : <span className={`sig-${sig?.style || 'great_vibes'} truncate leading-tight text-[#0D47A1]`} style={{ fontSize: 'clamp(14px, 2.4vw, 26px)' }}>{name}</span>
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
    {(env.completed_fields || []).filter((f) => f.document_id === docId && f.page === page).map((f) => <div key={`o${f.id}`} className="absolute overflow-hidden border border-green-600 bg-green-50/80 p-0.5 text-[9px] text-green-800" style={{ left: `${f.x * 100}%`, top: `${f.y * 100}%`, width: `${f.w * 100}%`, height: `${f.h * 100}%` }}>
      {f.type === 'signature' ? <>Signed by {f.by}{f.reason ? ` · ${f.reason}` : ''}</> : `${f.value ?? ''}`}</div>)}
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
      {info?.is_sandbox && <Alert kind="warn">SANDBOX envelope — for testing only, not legally binding.</Alert>}
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
                <button className="btn-accent" disabled={busy || pending.length > 0 || !consent} onClick={finish}>{t('finish')}</button>
                <button className="btn-secondary" onClick={saveLater}>{t('later')}</button>
                <button className="btn-danger" onClick={() => setDeclining(true)}>{t('decline')}</button>
              </div>
              <div className="h-1.5 bg-[#D6E8FF]"><div className="h-full bg-[#E6007E]" style={{ width: `${fields.length ? (100 * (fields.length - pending.length)) / fields.length : 100}%` }} /></div>
              <label className="flex items-start gap-2"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5" /><span>{t('consent')}. <details className="inline"><summary className="inline cursor-pointer text-[#0D47A1]">Read the disclosure</summary><span className="mt-1 block whitespace-pre-line text-slate-500">{info?.consent_text}</span></details></span></label>
              {sig && <div className="flex items-center gap-2 text-slate-500">Adopted signature: {sig.kind} {sig.kind === 'typed' && `(${sig.style})`} <button className="text-[#0D47A1]" onClick={() => setAdopt(true)}>Change</button></div>}
            </div>
            {(env.message || env.private_message) && <div className="card border-l-4 border-l-[#E6007E] whitespace-pre-line">{[env.message, env.private_message].filter(Boolean).join('\n\n')}</div>}
            <p className="text-slate-500">Click <b>{t('start')}</b> to be guided through each field. Enter a reason under every signature, tick the consent box, then <b>{t('finish')}</b>. Each signature is stamped with your name, reason, IST and UTC time and a SHA-256 hash.</p>
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
