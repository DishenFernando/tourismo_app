import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, RefreshCw } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { getGeoQualityReport, type GeoAuditReport } from '../lib/api'

const reasonText:Record<string,string>={
  missing_coordinates:'No map coordinates',
  missing_location_source:'Location reference missing',
  outside_sri_lanka_review_bounds:'Coordinate outside approximate Sri Lanka review region',
  shared_coordinates_review:'Another record shares this coordinate; check whether intentional',
}

/** An editorial queue, not an unlicensed third-party geocoding service. */
export function GeoQuality(){
  const auth=useTourismoAuth()
  const canEdit=auth.profile?.roles.some(r=>r==='admin'||r==='editor')??false
  const [report,setReport]=useState<GeoAuditReport|null>(null)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  async function load(){
    setBusy(true);setError('')
    try{
      const token=await auth.token()
      if(!token)throw new Error('Please sign in to review geographic content.')
      setReport(await getGeoQualityReport(token))
    }catch(e){setError(e instanceof Error?e.message:'Unable to load location report')}
    finally{setBusy(false)}
  }
  useEffect(()=>{if(canEdit)void load()},[canEdit])
  return <main className="wrap py-12 min-h-[70vh]">
    <span className="small-label">EDITORIAL LOCATION QUALITY</span>
    <h1 className="page-title">Map coverage & source review</h1>
    <p className="lead">Review missing coordinates and location references before publishing more map pins. This report does not change any data or verify exact entrances.</p>
    <div className="mt-4 flex flex-wrap gap-2">
      <Link className="btn-secondary" to="/admin">Content Studio</Link>
      <Link className="btn-secondary" to="/map">Public map</Link>
      {canEdit&&<button type="button" className="btn-primary" disabled={busy} onClick={()=>void load()}><RefreshCw size={16}/>{busy?'Checking…':'Refresh report'}</button>}
    </div>
    {!auth.loaded&&<p role="status" className="mt-6">Loading authentication…</p>}
    {auth.loaded&&!auth.signedIn&&<p className="mt-6">Editor access requires sign-in.</p>}
    {auth.signedIn&&!canEdit&&<p role="alert" className="error-banner mt-6">Only platform editors and administrators can view the location review queue.</p>}
    {error&&<p role="alert" className="error-banner mt-6">{error}</p>}
    {report&&canEdit&&<>
      <div className="grid sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-7" aria-label="Geographic content metrics">
        {([['Records checked',report.scanned],['Mapped',report.mapped],['Mapped with source',report.sourced_mapped],
          ['Missing coordinates',report.missing_coordinates],['Missing source',report.missing_location_source],
          ['Outside review region',report.outside_review_bounds]] as [string,number][]).map(([label,value])=><div className="form-panel p-4" key={label}>
          <strong className="text-2xl">{value}</strong><p className="text-xs mt-1 text-ink/70">{label}</p></div>)}
      </div>
      <p className="mt-4 text-sm text-ink/70">{report.note} {report.shared_coordinate_groups} shared-coordinate group(s) flagged for checking.
        {report.scan_limited&&' Audit scan capped at 5,001 public records; results are partial.'}
        {report.issues_limited&&' Showing the first issues; this is not the complete issue list.'}</p>
      <section className="form-panel mt-6 p-5" aria-label="Location issues">
        <h2 className="text-xl font-bold flex gap-2 items-center"><MapPin size={20}/> Items requiring attention</h2>
        {report.issues.length===0?<p className="mt-4 text-sm">No issues were found among the checked public records.</p>:
          <div className="mt-4 divide-y divide-ink/10">{report.issues.map((item,index)=><article key={`${item.kind}-${item.detail_path}-${item.reason}-${index}`} className="py-3 flex flex-wrap justify-between gap-3">
            <div><p className="font-bold">{item.label}</p><p className="text-xs text-ink/60">{item.kind} · {item.district}</p>
              <p className="text-sm text-amber-800 mt-1">{reasonText[item.reason]||item.reason}</p></div>
            <Link to={item.detail_path} className="text-sm underline text-pine">View current public page</Link>
          </article>)}</div>}
      </section>
      <p className="text-sm text-ink/70 mt-5">Correct editorial destination and attraction locations in Content Studio. Published service-location revisions must continue through independent listing moderation. Do not enter guessed coordinates to clear the report.</p>
    </>}
  </main>
}
