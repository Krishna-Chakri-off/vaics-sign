import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import axios from 'axios'
import { API_URL } from '../../api'
import PdfPages from './PdfPages'

const e2m = (e) => { const d = e?.response?.data?.detail; return Array.isArray(d) ? d.map((x) => x.msg).join('; ') : d || e.message }
const nowStamp = () => { const d = new Date(); return `${d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'medium' })} IST | ${d.toISOString().replace('T', ' ').slice(0, 19)} UTC` }

export default function SignPublic() {
  const { token } = useParams(); const base = `${API_URL}/sign/public/${token}`
  const [info, setInfo] = useState(null); const [err, setErr] = useState(''); const [code, setCode] = useState(''); const [sess, setSess] = useState(sessionStorage.getItem(`vs_${token}`) || '')
  const [doc, setDoc] = useState(null); const [buf, setBuf] = useState(null); const [reasons, setReasons] = useState({}); const [consent, setConsent] = useState(false); const [done, setDone] = useState(''); const [busy, setBusy] = useState(false); const [focus, setFocus] = useState(null)
  const refs = useRef({})
  useEffect(() => { axios.get(base).then((r) => setInfo(r.data)).catch((e) => setErr(e2m(e))) }, [token])
  useEffect(() => { if (!sess) return; const h = { headers: { 'X-Sign-Session': sess } }
    axios.get(`${base}/doc`, h).then((r) => setDoc(r.data)).catch((e) => { if (e?.response?.status === 401) { sessionStorage.removeItem(`vs_${token}`); setSess('') } else setErr(e2m(e)) })
    axios.get(`${base}/file`, { ...h, responseType: 'arraybuffer' }).then((r) => setBuf(r.data)).catch(() => {}) }, [sess])
  const unlock = async (e) => { e.preventDefault(); setErr(''); setBusy(true); try { const r = await axios.post(`${base}/unlock`, { code }); sessionStorage.setItem(`vs_${token}`, r.data.session); setSess(r.data.session) } catch (ex) { setErr(e2m(ex)) } finally { setBusy(false) } }
  const fields = doc?.fields || []
  const pending = fields.filter((f) => !(reasons[f.id] || '').trim())
  const goNext = () => { const f = pending[0] || fields[0]; if (!f) return; setFocus(f.id); const el = refs.current[f.id]; el?.scrollIntoView({ behavior: 'smooth', block: 'center' }); setTimeout(() => el?.querySelector('input')?.focus(), 400) }
  const finish = async () => { setErr(''); setBusy(true); try { const r = await axios.post(`${base}/sign`, { consent, reasons }, { headers: { 'X-Sign-Session': sess } }); sessionStorage.removeItem(`vs_${token}`); setDone(r.data.status === 'completed' ? 'Thank you — you were the final signer. The completed document will be emailed to all parties.' : 'Thank you — your signature has been recorded. The next signer has now been notified.') } catch (e) { setErr(e2m(e)) } finally { setBusy(false) } }
  const decline = async () => { const reason = prompt('Reason for declining?'); if (reason === null) return; const fd = new FormData(); fd.append('reason', reason); try { await axios.post(`${base}/decline`, fd, { headers: { 'X-Sign-Session': sess } }); setDone('You declined this document. The requester has been informed.') } catch (e) { setErr(e2m(e)) } }
  const b = info?.branding || doc?.branding
  const overlay = (page) => <>
    {(doc?.signed_by_others || []).filter((f) => f.page === page).map((f, i) => <div key={`o${i}`} className="absolute border border-green-600 bg-green-50/70 p-0.5 text-[9px] text-green-800" style={{ left: `${f.x * 100}%`, top: `${f.y * 100}%`, width: `${f.w * 100}%`, height: `${f.h * 100}%` }}>Signed by {f.name}</div>)}
    {fields.filter((f) => f.page === page).map((f) => { const filled = (reasons[f.id] || '').trim(); return (
      <div key={f.id} ref={(el) => (refs.current[f.id] = el)} className={`absolute border-2 bg-white/90 ${focus === f.id ? 'ring-4 ring-[#E6007E]/30' : ''}`} style={{ left: `${f.x * 100}%`, top: `${f.y * 100}%`, width: `${f.w * 100}%`, minHeight: `${f.h * 100}%`, borderColor: filled ? '#059669' : '#E6007E' }}>
        <div className="sig-script truncate px-1 leading-tight text-[#0D47A1]" style={{ fontSize: 'clamp(14px, 2.4vw, 26px)' }}>{doc.recipient.name}</div>
        <div className="px-1 text-[9px] leading-tight text-slate-600">Name: {doc.recipient.name}<br />{filled ? nowStamp() : 'Timestamp & SHA-256 added on signing'}</div>
        <input className="w-full border-t border-[#CBD5E1] bg-[#F2F8FF] px-1 py-0.5 text-[11px] outline-none focus:bg-white" placeholder="Reason for signing *" value={reasons[f.id] || ''} onFocus={() => setFocus(f.id)} onChange={(e) => setReasons({ ...reasons, [f.id]: e.target.value })} />
      </div>) })}</>
  return (
    <div className="min-h-screen bg-[#F2F8FF]">
      <header className="flex items-center gap-3 bg-[#0D47A1] px-4 py-2"><img src={b?.logo || '/vaics-logo-full.png'} alt="VAICS" className="h-9 bg-white p-1" /><span className="font-semibold text-white">{b?.product_name || 'VAICS Sign'}</span><span className="ml-auto text-white/80">{b?.org_name}</span></header>
      <main className="mx-auto max-w-5xl space-y-4 p-4">
        {err && <div className="border border-red-200 bg-red-50 px-4 py-2.5 font-medium text-red-800">{err}</div>}
        {done ? <div className="card text-base font-medium text-green-800">{done}</div>
          : !sess ? info && <form onSubmit={unlock} className="card mx-auto max-w-md space-y-3">
            <h1>{info.title}</h1><p className="text-slate-500">Hello {info.recipient.name} (signer {info.recipient.order}). Enter the signature access code that was emailed to you separately.</p>
            <input className="input text-center text-xl tracking-[0.4em]" inputMode="numeric" autoComplete="one-time-code" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} placeholder="••••••" autoFocus />
            <button className="btn-primary w-full" disabled={busy || code.length < 6}>Unlock document</button>
          </form>
          : doc && <>
            <div className="card sticky top-0 z-10 flex flex-wrap items-center gap-3">
              <div className="mr-auto"><h1>{doc.title}</h1><p className="text-slate-500">{doc.recipient.name} · {fields.length} signature field(s) · {fields.length - pending.length} completed</p></div>
              <button className="btn-primary" onClick={goNext}>{pending.length === fields.length ? 'Start' : pending.length ? 'Next field' : 'Review'}</button>
              <label className="flex items-center gap-2"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> I agree to sign electronically</label>
              <button className="btn-accent" disabled={busy || pending.length > 0 || !consent} onClick={finish}>Sign & finish</button>
              <button className="btn-danger" onClick={decline}>Decline</button>
            </div>
            {doc.message && <div className="card border-l-4 border-l-[#E6007E]">{doc.message}</div>}
            <p className="text-slate-500">Your signature is generated from your name. Enter a reason under each highlighted field, tick consent, then Sign & finish. This is an electronic signature, not a certificate-based digital signature.</p>
            {buf ? <PdfPages data={buf} overlay={overlay} /> : 'Loading document…'}
          </>}
      </main>
    </div>)
}
