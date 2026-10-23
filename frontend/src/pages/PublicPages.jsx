import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { pub, errMsg, fmtIST } from '../api'
import { PublicShell } from '../components/Layout'
import { Alert, Field, SBadge } from '../components/ui'

export function CompletedAccess() {
  const { token } = useParams(); const base = `/public/completed/${token}`
  const [info, setInfo] = useState(null); const [err, setErr] = useState(''); const [sent, setSent] = useState(false); const [code, setCode] = useState(''); const [ok, setOk] = useState('')
  useEffect(() => { pub.get(base).then((r) => setInfo(r.data)).catch((e) => setErr(errMsg(e))) }, [token]) // eslint-disable-line
  const dl = async (e) => {
    e.preventDefault(); setErr('')
    try { const r = await pub.post(`${base}/download`, { code }, { responseType: 'blob' }); const a = document.createElement('a'); a.href = URL.createObjectURL(r.data); a.download = `${info.envelope_id}-signed.pdf`; a.click(); setOk('Downloaded.') }
    catch (ex) { let m = errMsg(ex); try { m = JSON.parse(await ex.response.data.text()).detail } catch { /* blob */ } setErr(m) }
  }
  return (
    <PublicShell brand={info?.branding}>
      <div className="card mx-auto max-w-md space-y-3">
        <h1>{info?.title || 'Completed document'}</h1><Alert>{err}</Alert><Alert kind="ok">{ok}</Alert>
        {info && <>
          <p className="text-slate-500">For your security we confirm it is you before downloading. A one-time code will be emailed to {info.email_hint}.</p>
          <button className="btn-secondary w-full" onClick={async () => { try { await pub.post(`${base}/otp`); setSent(true) } catch (e) { setErr(errMsg(e)) } }}>Email me a code</button>
          {sent && <Alert kind="ok">Code requested. (Development mode: if SMTP is not configured the code is only in the sender's Email outbox.)</Alert>}
          <form onSubmit={dl} className="space-y-2"><input className="input text-center text-xl tracking-[0.4em]" inputMode="numeric" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} placeholder="••••••" />
            <button className="btn-primary w-full" disabled={code.length < 6}>Download signed PDF</button></form>
        </>}
      </div>
    </PublicShell>)
}

export function PowerFormPublic() {
  const { slug } = useParams(); const nav = useNavigate()
  const [info, setInfo] = useState(null); const [err, setErr] = useState(''); const [f, setF] = useState({ name: '', email: '' }); const [vid, setVid] = useState(''); const [code, setCode] = useState(''); const [msg, setMsg] = useState('')
  useEffect(() => { pub.get(`/public/pf/${slug}`).then((r) => setInfo(r.data)).catch((e) => setErr(errMsg(e))) }, [slug])
  const start = async (e) => { e.preventDefault(); setErr(''); try { setVid((await pub.post(`/public/pf/${slug}/start`, f)).data.verification_id) } catch (ex) { setErr(errMsg(ex)) } }
  const verify = async (e) => {
    e.preventDefault(); setErr('')
    try { const r = await pub.post(`/public/pf/${slug}/verify`, { verification_id: vid, code }); if (r.data.token) { sessionStorage.setItem(`vs_${r.data.token}`, r.data.session); nav(`/s/${r.data.token}`) } else setMsg(r.data.message) } catch (ex) { setErr(errMsg(ex)) }
  }
  return (
    <PublicShell brand={info?.branding}>
      <div className="card mx-auto max-w-md space-y-3">
        <h1>{info?.name || 'Form'}</h1>{info && <p className="text-slate-500">{info.organization} · you will sign as {info.role}</p>}
        <Alert>{err}</Alert><Alert kind="ok">{msg}</Alert>
        {info && !vid && <form onSubmit={start} className="space-y-2">
          <Field label="Full name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
          <Field label="Email"><input className="input" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required /></Field>
          <button className="btn-primary w-full">Verify my email</button></form>}
        {vid && !msg && <form onSubmit={verify} className="space-y-2"><p>Enter the code we emailed to {f.email}.</p>
          <input className="input text-center text-xl tracking-[0.4em]" inputMode="numeric" maxLength={8} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} />
          <button className="btn-accent w-full" disabled={code.length < 6}>Continue to sign</button></form>}
      </div>
    </PublicShell>)
}

export function VerifyPage() {
  const [res, setRes] = useState(null); const [err, setErr] = useState(''); const [id, setId] = useState(''); const [busy, setBusy] = useState(false)
  const up = async (file) => { if (!file) return; setErr(''); setBusy(true); const fd = new FormData(); fd.append('file', file); try { setRes((await pub.post('/public/verify', fd)).data) } catch (e) { setErr(errMsg(e)) } finally { setBusy(false) } }
  const byId = async (e) => { e.preventDefault(); setErr(''); try { setRes({ record: (await pub.get(`/public/verify/${encodeURIComponent(id)}`)).data, by_id: true }) } catch (ex) { setErr(errMsg(ex)); setRes(null) } }
  const r = res?.record
  return (
    <PublicShell>
      <div className="card mx-auto max-w-2xl space-y-3">
        <h1>Verify a VAICS Sign document</h1>
        <p className="text-slate-500">Upload a completed PDF to check that it is exactly the file VAICS Sign issued and that its embedded PAdES seal is intact. The file is hashed and not stored.</p>
        <label className="btn-primary w-full cursor-pointer">{busy ? 'Checking…' : 'Choose signed PDF'}<input type="file" hidden accept="application/pdf" onChange={(e) => up(e.target.files[0])} /></label>
        <form onSubmit={byId} className="flex gap-2"><input className="input" placeholder="…or enter an envelope ID (VS-…)" value={id} onChange={(e) => setId(e.target.value)} /><button className="btn-secondary">Look up</button></form>
        <Alert>{err}</Alert>
        {res && !res.by_id && (res.verdict === 'authentic' ? <Alert kind="ok">Authentic: this file matches the record and its seal is intact.</Alert> : <Alert>Not verified: this file does not match a VAICS Sign record or it was modified.</Alert>)}
        {res?.signature && <div className="text-slate-600">Embedded signatures: {res.signature.signatures}{(res.signature.results || []).map((s, i) => <div key={i}>• {s.signer || s.field}: intact {String(s.intact)}, trusted {String(!!s.trusted)}{s.trusted ? '' : ' (seal certificate not from a trusted CA in this deployment)'}</div>)}</div>}
        {res?.sha256 && <div className="break-all">SHA-256: <code>{res.sha256}</code></div>}
        {r && <div className="border border-[#B8D0E8] bg-[#F2F8FF] p-3"><div><b>{r.envelope_id}</b> · {r.organization} · <SBadge s={r.status} /></div><div>Completed {fmtIST(r.completed_at)} · seal {r.seal}</div>
          {r.signers.map((s) => <div key={s.name + s.completed_at}>✓ {s.name} — {fmtIST(s.completed_at)}</div>)}<div className="break-all text-slate-500">Record SHA-256: {r.sha256}</div></div>}
      </div>
    </PublicShell>)
}
