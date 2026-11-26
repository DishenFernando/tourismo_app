/** Phase 9B-1: LOCAL-ONLY editorial translation handoff review.
 * It never posts translated content, publishes records, or alters the DB.
 */
import {useState} from 'react'
import {Link} from 'react-router-dom'
import {useTourismoAuth} from '../app/Auth'

type Result = {records: number; sinReviewed: number; tamReviewed: number; pending: number; issues: string[]}
type Item = Record<string, unknown>

function object(value: unknown): value is Item {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
function nonblank(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}
function reviewRecord(value: unknown, number: number, seen: Set<string>, result: Result): void {
  const fail = (message: string) => result.issues.push(`Line ${number}: ${message}`)
  if (!object(value)) { fail('Expected an object'); return }
  if (!['destination', 'attraction', 'guide'].includes(String(value.type))) fail('Invalid content type')
  if (!nonblank(value.slug) || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value.slug)) fail('Invalid slug')
  const key = `${value.type}:${value.slug}`
  if (seen.has(key)) fail('Duplicate type and slug')
  seen.add(key)
  if (!nonblank(value.source_url) || !/^https:\/\/[a-z0-9.-]+(?:\/|$)/i.test(value.source_url)) fail('A source HTTPS URL is required')
  if (!object(value.en) || !nonblank(value.en.title) || !nonblank(value.en.summary)) fail('An English title and summary are required')
  for (const locale of ['si', 'ta'] as const) {
    const item = value[locale]
    if (item == null) { result.pending++; continue }
    if (!object(item) || !['missing', 'draft', 'reviewed'].includes(String(item.status))) {
      fail(`${locale}: invalid status`); continue
    }
    if (item.status === 'missing') { result.pending++; continue }
    if (!nonblank(item.title) || !nonblank(item.summary) || !nonblank(item.translated_by)) {
      fail(`${locale}: title, summary and translator required`)
    }
    if (item.status === 'reviewed') {
      if (!nonblank(item.reviewed_by) || !nonblank(item.reviewed_at)) {
        fail(`${locale}: reviewer and review date required`)
      } else {
        if (item.reviewed_by.trim().toLowerCase() === String(item.translated_by ?? '').trim().toLowerCase()) {
          fail(`${locale}: translator cannot self-review`)
        }
        const date = item.reviewed_at
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date)) || date > new Date().toISOString().slice(0,10)) {
          fail(`${locale}: invalid reviewed_at date`)
        }
      }
      if (locale === 'si') result.sinReviewed++
      else result.tamReviewed++
    } else result.pending++
  }
}

export function TranslationWorkbench() {
  const auth = useTourismoAuth()
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')
  const allowed = auth.profile?.roles?.some(role => role === 'admin' || role === 'editor') ?? false

  async function inspect(file: File | undefined) {
    setResult(null); setError('')
    if (!file) return
    if (file.size > 2_000_000) { setError('File exceeds the 2 MB limit. Export a smaller batch.'); return }
    try {
      const lines = (await file.text()).replace(/^\uFEFF/, '').split(/\r?\n/)
      if (lines.length > 2001) { setError('Maximum 2,000 lines per review batch.'); return }
      const result: Result = {records: 0, sinReviewed: 0, tamReviewed: 0, pending: 0, issues: []}
      const seen = new Set<string>()
      lines.forEach((line, i) => {
        if (!line.trim()) return
        result.records++
        try { reviewRecord(JSON.parse(line) as unknown, i+1, seen, result) }
        catch { result.issues.push(`Line ${i+1}: invalid JSON`) }
      })
      if (!result.records) result.issues.push('No records supplied')
      setResult(result)
    } catch { setError('Could not read the selected file.') }
  }

  return <main className="wrap py-12 max-w-5xl" aria-labelledby="translation-workbench-heading">
    <p className="small-label">EDITORIAL QUALITY · PHASE 9B</p>
    <h1 className="page-title mt-3" id="translation-workbench-heading">Translation review workbench</h1>
    <p className="mt-4 text-ink/75">Inspect a Sinhala/Tamil editorial handoff locally before entering content in the approved CMS workflow. No file leaves your browser and nothing is published by this page.</p>
    {!auth.signedIn ? <p className="info-banner mt-6">Sign in as a Tourismo editor or administrator to access this tool.</p> :
      !allowed ? <p className="info-banner mt-6">This workbench is restricted to editors and administrators.</p> : <>
        <section className="form-panel mt-6" aria-label="Review translation handoff">
          <label className="block font-semibold" htmlFor="translation-file">Choose an editorial JSONL handoff</label>
          <input id="translation-file" className="mt-3 block w-full" type="file" accept=".jsonl,.ndjson,application/x-ndjson" onChange={e=>void inspect(e.currentTarget.files?.[0])}/>
          <p className="mt-2 text-sm text-ink/65">Maximum 2 MB / 2,000 records. Required: type, slug, HTTPS source, English text, translation status and independent reviewer evidence.</p>
        </section>
        {error && <p role="alert" className="error-banner mt-5">{error}</p>}
        {result && <section className="form-panel mt-6" aria-live="polite" aria-label="Translation readiness results">
          <h2 className="text-xl font-bold">Handoff audit</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-4 text-sm">
            <p><strong className="block text-2xl">{result.records}</strong> Records</p>
            <p><strong className="block text-2xl">{result.sinReviewed}</strong> Sinhala reviewed</p>
            <p><strong className="block text-2xl">{result.tamReviewed}</strong> Tamil reviewed</p>
            <p><strong className="block text-2xl">{result.pending}</strong> Missing/draft locales</p>
          </div>
          {result.issues.length ? <><h3 className="font-semibold mt-5">Issues ({result.issues.length})</h3><ul className="list-disc pl-6 mt-2 space-y-1">{result.issues.slice(0,100).map((issue,i)=><li key={i}>{issue}</li>)}</ul>{result.issues.length>100&&<p className="mt-2 text-sm">Only the first 100 issues are displayed.</p>}</> : <p className="mt-5 text-pine font-semibold">Format checks passed. Human factual, language, licensing and publishing review are still required.</p>}
        </section>}
      </>}
    <Link to="/admin" className="mt-8 inline-block underline text-pine">Back to content administration</Link>
  </main>
}
