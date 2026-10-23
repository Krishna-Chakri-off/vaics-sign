import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { errMsg } from '../../api'
import { PageShell, Alert, Field } from '../../components/ui'

export default function SignNew() {
  const [f, setF] = useState({ title: '', description: '', category: 'General' }); const [file, setFile] = useState(null); const [err, setErr] = useState(''); const [busy, setBusy] = useState(false); const nav = useNavigate()
  const pick = (e) => { const x = e.target.files[0]; setErr(''); if (!x) return; if (x.type !== 'application/pdf' && !x.name.toLowerCase().endsWith('.pdf')) { setErr('Only PDF files are accepted'); return } if (x.size > 15 * 1024 * 1024) { setErr('File exceeds 15 MB'); return } setFile(x); if (!f.title) setF({ ...f, title: x.name.replace(/\.pdf$/i, '') }) }
  const submit = async (e) => { e.preventDefault(); if (!file) return setErr('Choose a PDF'); setBusy(true)
    const fd = new FormData(); fd.append('file', file); Object.entries(f).forEach(([k, v]) => fd.append(k, v))
    try { const r = await api.post('/sign/documents', fd); nav(`/vaics-sign/${r.data.id}`) } catch (e2) { setErr(errMsg(e2)) } finally { setBusy(false) } }
  return (
    <PageShell title="New document" subtitle="Upload a PDF. It is stored privately and its SHA-256 fingerprint is recorded.">
      <form onSubmit={submit} className="card grid max-w-3xl gap-3 md:grid-cols-2">
        <Alert>{err}</Alert>
        <Field label="PDF file *" className="md:col-span-2"><input type="file" accept="application/pdf,.pdf" className="input" onChange={pick} /></Field>
        <Field label="Title *"><input className="input" required value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Category"><select className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{['General', 'HR', 'Legal / NDA', 'Finance', 'Procurement', 'Policy'].map((c) => <option key={c}>{c}</option>)}</select></Field>
        <Field label="Description" className="md:col-span-2"><textarea className="input" rows={3} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        {file && <iframe title="preview" src={URL.createObjectURL(file)} className="h-96 w-full border border-gray-200 md:col-span-2" />}
        <div className="md:col-span-2"><button className="btn-primary" disabled={busy}>{busy ? 'Uploading…' : 'Upload & continue to prepare'}</button></div>
      </form>
    </PageShell>)
}
