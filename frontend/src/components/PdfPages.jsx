import { useEffect, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

// Renders every page of a PDF (ArrayBuffer) to canvas; overlay(pageNumber) is drawn on top, sized to the page.
export default function PdfPages({ data, overlay, maxWidth = 900 }) {
  const [pages, setPages] = useState([]); const [err, setErr] = useState(''); const wrap = useRef(null)
  useEffect(() => {
    if (!data) return; let cancelled = false
    pdfjs.getDocument({ data: data.slice(0) }).promise.then(async (doc) => {
      const out = []
      const width = Math.min(maxWidth, (wrap.current?.clientWidth || maxWidth) - 2)
      for (let i = 1; i <= doc.numPages; i++) {
        const p = await doc.getPage(i); const v0 = p.getViewport({ scale: 1 }); const scale = width / v0.width
        const v = p.getViewport({ scale: scale * (window.devicePixelRatio || 1) })
        const c = document.createElement('canvas'); c.width = v.width; c.height = v.height
        await p.render({ canvasContext: c.getContext('2d'), viewport: v }).promise
        out.push({ n: i, url: c.toDataURL('image/png'), w: width, h: v0.height * scale })
      }
      if (!cancelled) setPages(out)
    }).catch((e) => setErr(e.message))
    return () => { cancelled = true }
  }, [data, maxWidth])
  return (
    <div ref={wrap} className="space-y-4">
      {err && <div className="text-red-700">Could not render PDF: {err}</div>}
      {!pages.length && !err && <div className="text-slate-500">Rendering document…</div>}
      {pages.map((p) => (
        <div key={p.n} id={`pdf-page-${p.n}`} className="relative mx-auto border border-[#B8D0E8] bg-white shadow-sm" style={{ width: p.w, height: p.h }}>
          <img src={p.url} alt={`Page ${p.n}`} className="pointer-events-none absolute inset-0 h-full w-full select-none" draggable={false} />
          <div className="absolute top-1 right-2 text-[10px] text-slate-400">Page {p.n}</div>
          {overlay && overlay(p.n)}
        </div>))}
    </div>)
}
