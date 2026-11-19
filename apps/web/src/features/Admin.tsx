import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Camera, FilePenLine, MapPin, PlusCircle, ShieldCheck, UploadCloud, ListChecks } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import {
  adminDestinations, adminGuide, attachAdminPhoto, createAdminDestination,
  createAdminPoi, publishAdminDestination, saveAdminGuide, listAdminPois, publishAdminPoi,
  reviewQueue, submitAdminGuide, submitAdminPoi, requestGuideChanges, requestPoiChanges, approveAdminGuide, getContentAudit,
  type ReviewItem, type AdminPoi,
  type AdminGuide, type Destination, type ContentAudit,
} from '../lib/api'

const emptyGuide: AdminGuide = {locale:'en',overview:'',highlights:[],local_tips:[],source_name:'',source_url:'',content_status:'missing'}
const fieldStyle='w-full rounded-lg border border-[#cddfd9] bg-white px-3 py-3 text-sm'
const initialPlace={slug:'',title:'',district:'',province:'',summary:''}
const initialPoi={slug:'',title:'',category:'heritage',description:'',source_url:'',source_name:'',latitude:'',longitude:''}
const initialPhoto={filename:'',photographer:'',license_name:'CC BY-SA 4.0',alt_text:''}

export function Admin() {
  const auth=useTourismoAuth()
  const isAdmin=auth.profile?.roles.includes('admin') ?? false
  const permitted=auth.profile?.roles.some(role=>role==='admin'||role==='editor') ?? false
  const [places,setPlaces]=useState<Destination[]>([])
  const [slug,setSlug]=useState('')
  const [section,setSection]=useState<'guide'|'poi'|'photo'|'new'|'review'|'audit'>('guide')
  const [guide,setGuide]=useState<AdminGuide>(emptyGuide)
  const [highlights,setHighlights]=useState('')
  const [tips,setTips]=useState('')
  const [newPlace,setNewPlace]=useState(initialPlace)
  const [poi,setPoi]=useState(initialPoi)
  const [existingPois,setExistingPois]=useState<AdminPoi[]>([])
  const [reviewItems,setReviewItems]=useState<ReviewItem[]>([])
  const [audit,setAudit]=useState<ContentAudit|null>(null)
  const [onlyIncomplete,setOnlyIncomplete]=useState(true)
  const [reviewReason,setReviewReason]=useState('')
  const [photo,setPhoto]=useState(initialPhoto)
  const [busy,setBusy]=useState(false)
  const [feedback,setFeedback]=useState('')
  const [error,setError]=useState('')

  const reload=useCallback(async()=>{
    const token=await auth.token()
    if(!token)throw new Error('Please sign in again')
    const [result, quality] = await Promise.all([adminDestinations(token), getContentAudit(token)])
    setPlaces(result)
    setAudit(quality)
    if (isAdmin) setReviewItems(await reviewQueue(token))
    setSlug(previous=>previous || result[0]?.slug || '')
  },[auth,isAdmin])
  useEffect(()=>{
    if(!permitted)return
    let active=true
    void reload().catch(e=>{if(active)setError(e instanceof Error?e.message:'Unable to load content')})
    return()=>{active=false}
  },[permitted,reload])
  useEffect(()=>{
    if(!permitted || !slug)return
    let active=true
    setError('')
    void auth.token().then(t=>t?adminGuide(slug,t,guide.locale):Promise.reject(new Error('Session unavailable'))).then(data=>{
      if(!active)return
      setGuide(data)
      setHighlights(data.highlights.join('\n'))
      setTips(data.local_tips.join('\n'))
    }).catch(e=>{if(active)setError(e instanceof Error?e.message:'Unable to load guide')})
    return()=>{active=false}
  },[slug,guide.locale,permitted,auth,feedback])
  useEffect(()=>{if(!slug||!permitted)return;let active=true;void auth.token().then(t=>t?listAdminPois(slug,t):[]).then(items=>{if(active)setExistingPois(items)}).catch(()=>{if(active)setExistingPois([])});return()=>{active=false}},[slug,permitted,auth,feedback])
  const selected=places.find(p=>p.slug===slug)

  async function action(perform:(token:string)=>Promise<unknown>,done:string){
    setBusy(true);setError('');setFeedback('')
    try{
      const token=await auth.token()
      if(!token)throw new Error('Session unavailable')
      await perform(token)
      setFeedback(done)
      await reload()
    }catch(e){setError(e instanceof Error?e.message:'Request failed')}
    finally{setBusy(false)}
  }
  const saveGuide=(event:FormEvent)=>{
    event.preventDefault()
    void action(t=>saveAdminGuide(slug,{
      locale:guide.locale,overview:guide.overview,highlights:highlights.split('\n').map(x=>x.trim()).filter(Boolean),
      local_tips:tips.split('\n').map(x=>x.trim()).filter(Boolean),source_url:guide.source_url,
      source_name:guide.source_name,
    },t),'Guide saved as draft. An administrator must review and publish it.')
  }
  if(!auth.loaded || auth.profileState==='syncing')return <main className="wrap py-20">Loading your account…</main>
  if(!auth.signedIn)return <main className="wrap py-20"><h1 className="page-title">Tourismo editorial dashboard</h1><p className="lead">Sign in with your authorized account to manage content.</p><button className="btn-primary mt-5" onClick={auth.login}>Sign in</button></main>
  if(!permitted)return <main className="wrap py-20"><h1 className="page-title">Editorial access required</h1><p className="lead">Admin and editor permissions are assigned by a trusted platform operator, not through public registration.</p><button className="btn-secondary mt-5" onClick={()=>{void auth.refreshProfile()}}>Refresh my permissions</button></main>
  return <main className="wrap py-12 pb-24">
    <div className="flex flex-wrap justify-between gap-6 items-center"><div><div className="small-label flex items-center gap-2"><ShieldCheck size={16}/> TOURISMO CONTENT STUDIO</div><h1 className="page-title">Editorial dashboard</h1><p className="lead">Build trustworthy destination guides. Editors draft; administrators approve publication.</p></div>
      <div className="rounded-2xl bg-[#e7f5ed] px-6 py-4"><div className="text-2xl font-black text-pine">{places.length}</div><div className="text-sm text-ink/60">Destinations in database</div><div className="text-xs mt-1">{audit?.published ?? '–'} approved destinations · {audit?.needs_attention ?? '–'} need editorial attention</div><div className="text-xs mt-1">Your role: {isAdmin?'Administrator':'Editor'}</div></div>
    </div>
    {error && <div className="error-banner mt-6" role="alert">{error}</div>}
    {feedback && <div className="success-banner mt-6" role="status">{feedback}</div>}
    <div className="mt-9 grid gap-5 lg:grid-cols-[310px_1fr]">
      <aside className="form-panel self-start">
        <label className="field"><span>Choose a destination</span><select value={slug} onChange={e=>setSlug(e.target.value)}>{places.map(p=><option key={p.slug} value={p.slug}>{p.title} · {p.content_status}</option>)}</select></label>
        {selected && <div className="mt-4 rounded-xl bg-[#f3f8f4] p-4 text-sm"><div className="font-bold">{selected.title}</div><div>{selected.district} · {selected.province}</div><div className="mt-2 text-xs uppercase tracking-wider">Status: {selected.content_status}</div>{selected.photo && <img src={selected.photo.image_url} alt={selected.photo.alt_text} className="mt-3 rounded-xl h-28 w-full object-cover" loading="lazy"/>}<Link className="inline-block mt-3 underline text-pine" to={`/destinations/${selected.slug}`}>View public page</Link></div>}
        <div className="mt-5 flex flex-col gap-2">
          {([{id:'guide',label:'Destination guide',icon:FilePenLine},{id:'poi',label:'Add attraction',icon:MapPin},{id:'photo',label:'Photo & attribution',icon:Camera},{id:'new',label:'New destination',icon:PlusCircle},{id:'audit',label:'Content quality audit',icon:ListChecks},...(isAdmin?[{id:'review' as const,label:'Review queue',icon:ShieldCheck}]:[])] as const).map(item=><button key={item.id} onClick={()=>setSection(item.id)} className={`rounded-xl px-4 py-3 flex gap-3 text-left items-center font-semibold text-sm ${section===item.id?'bg-pine text-white':'bg-[#f2f8f5] text-ink'}`}><item.icon size={18}/>{item.label}</button>)}
        </div>
        {isAdmin && selected && <div className="mt-8 rounded-xl border border-amber-200 bg-amber-50 p-4"><div className="font-bold text-amber-900">Publish destination</div><p className="mt-2 text-xs text-amber-900">Requires a sourced English guide. Check accuracy, image rights, and translations before publication. Attractions stay drafts.</p><button disabled={busy} onClick={()=>{void action(t=>publishAdminDestination(slug,t),'Destination published successfully.')}} className="btn-primary mt-4">Approve & publish</button></div>}
      </aside>
      <div className="form-panel">
        {section==='guide' && <form onSubmit={saveGuide} className="space-y-5"><h2 className="text-2xl font-extrabold">Destination guide</h2><label className="field"><span>Language</span><select value={guide.locale} onChange={e=>{const locale=e.target.value as AdminGuide['locale'];setGuide(g=>({...g,locale}))}}><option value="en">English</option><option value="si">Sinhala</option><option value="ta">Tamil</option></select></label>
          <label className="field"><span>Overview</span><textarea rows={6} className={fieldStyle} required minLength={30} value={guide.overview} onChange={e=>setGuide(g=>({...g,overview:e.target.value}))}/></label>
          <label className="field"><span>Highlights (one per line)</span><textarea rows={4} className={fieldStyle} value={highlights} onChange={e=>setHighlights(e.target.value)}/></label>
          <label className="field"><span>Local tips (one per line)</span><textarea rows={4} className={fieldStyle} value={tips} onChange={e=>setTips(e.target.value)}/></label>
          <div className="grid gap-4 sm:grid-cols-2"><label className="field"><span>Source / organization</span><input value={guide.source_name || ''} onChange={e=>setGuide(g=>({...g,source_name:e.target.value}))} placeholder="e.g., UNESCO"/></label><label className="field"><span>Source URL (HTTPS)</span><input type="url" value={guide.source_url || ''} onChange={e=>setGuide(g=>({...g,source_url:e.target.value}))} placeholder="https://..."/></label></div>
          <div className="text-xs text-ink/60">Edits to a live published guide are stored as a separate revision. Visitors keep seeing the approved version until an administrator approves the update.</div><button className="btn-primary" disabled={busy} type="submit"><UploadCloud size={17}/> Save guide draft</button> {guide.content_status==='draft' && <button className="btn-secondary" type="button" disabled={busy} onClick={()=>{void action(t=>submitAdminGuide(slug,guide.locale,t),'Guide submitted for administrator review.')}}>Submit for review</button>}</form>}
        {section==='poi' && <form onSubmit={e=>{e.preventDefault();void action(t=>createAdminPoi(slug,{
          ...poi, ...(poi.latitude.trim() && poi.longitude.trim()?{latitude:Number(poi.latitude), longitude:Number(poi.longitude)}:{}),
        },t),'Attraction saved as an unpublished draft.')}} className="space-y-5"><h2 className="text-2xl font-extrabold">Add an attraction</h2>{(['title','slug','description'] as const).map(k=><label key={k} className="field"><span>{k==='slug'?'URL slug':k[0].toUpperCase()+k.slice(1)}</span>{k==='description'?<textarea className={fieldStyle} required minLength={10} rows={5} value={poi[k]} onChange={e=>setPoi(v=>({...v,[k]:e.target.value}))}/>:<input className={fieldStyle} required value={poi[k]} onChange={e=>setPoi(v=>({...v,[k]:e.target.value}))}/>}</label>)}<label className="field"><span>Category</span><select value={poi.category} onChange={e=>setPoi(p=>({...p,category:e.target.value}))}>{['heritage','nature','landmark','beach','wildlife','culture','adventure'].map(x=><option key={x} value={x}>{x}</option>)}</select></label><label className="field"><span>Source name</span><input value={poi.source_name} onChange={e=>setPoi(p=>({...p,source_name:e.target.value}))} placeholder="Official tourism authority"/></label><label className="field"><span>Source URL</span><input type="url" value={poi.source_url} onChange={e=>setPoi(p=>({...p,source_url:e.target.value}))} placeholder="https://..."/></label><div className="grid grid-cols-2 gap-3"><label className="field"><span>Latitude (optional)</span><input className={fieldStyle} type="number" step="any" min="-90" max="90" value={poi.latitude} onChange={e=>setPoi(p=>({...p,latitude:e.target.value}))}/></label><label className="field"><span>Longitude (optional)</span><input className={fieldStyle} type="number" step="any" min="-180" max="180" value={poi.longitude} onChange={e=>setPoi(p=>({...p,longitude:e.target.value}))}/></label></div><p className="help">Add both coordinates with a source link. These should be verified reference points, not guessed entrances.</p><button className="btn-primary" disabled={busy || (!!poi.latitude !== !!poi.longitude)} type="submit">Add attraction draft</button>
          <div className="border-t mt-6 pt-5"><h3 className="font-bold mb-3">Existing attractions</h3>{existingPois.length===0?<p className="help">No attractions have been added.</p>:existingPois.map(item=><div key={item.slug} className="flex items-center justify-between gap-3 py-3 border-b"><div className="text-sm"><b>{item.title}</b><div className="text-xs text-ink/60">{item.content_status} · {item.has_source?'sourced':'source required'}</div></div><div className="flex gap-2">{item.content_status==='draft' && <button type="button" disabled={busy||!item.has_source} className="btn-secondary" onClick={()=>{void action(t=>submitAdminPoi(slug,item.slug,t),'Attraction submitted for review.')}}>Submit</button>}{isAdmin&&item.content_status!=='published'&&<button type="button" disabled={busy || !item.has_source} className="btn-secondary" onClick={()=>{void action(t=>publishAdminPoi(slug,item.slug,t),'Attraction published.')}}>Approve</button>}</div></div>)}</div></form>}
        {section==='photo' && <form onSubmit={e=>{e.preventDefault();void action(t=>attachAdminPhoto(slug,photo,t),'Photo and attribution recorded.')}} className="space-y-5"><h2 className="text-2xl font-extrabold">Add a licensed photograph</h2>{!isAdmin && <div className="info-banner">Photo assignment currently requires administrator approval.</div>}<p className="help">Use a real Wikimedia Commons file with its matching photographer and license. Verify the original file page before submission. Remote images need internet access.</p>{(['filename','photographer','alt_text'] as const).map(k=><label key={k} className="field"><span>{k==='filename'?'Commons file name (underscores, .jpg/.png)':k==='alt_text'?'Accessible description':'Photographer / creator'}</span><input value={photo[k]} className={fieldStyle} onChange={e=>setPhoto(v=>({...v,[k]:e.target.value}))} required/></label>)}<label className="field"><span>License</span><select value={photo.license_name} onChange={e=>setPhoto(v=>({...v,license_name:e.target.value}))}><option>CC BY-SA 4.0</option><option>CC BY 4.0</option><option>CC BY-SA 3.0</option></select></label><button className="btn-primary" disabled={busy||!isAdmin} type="submit">Add photographed destination</button></form>}
        {section==='review' && isAdmin && <div className="space-y-4"><h2 className="text-2xl font-extrabold">Awaiting editorial review</h2><p className="help">Only submitted drafts appear here. Check the original source, descriptions, coordinates, and license before approving.</p><label className="field"><span>Review feedback (required to request changes)</span><textarea className={fieldStyle} rows={2} minLength={8} maxLength={300} value={reviewReason} onChange={e=>setReviewReason(e.target.value)} placeholder="Explain what needs correction or further source verification"/></label>{reviewItems.length===0?<p className="info-banner">No items waiting for review.</p>:reviewItems.map((item,i)=><div className="border rounded-xl p-4" key={`${item.kind}-${item.destination_slug}-${item.poi_slug||item.locale||i}`}><b>{item.destination_slug}</b> · {item.kind==='poi'?`Attraction ${item.poi_slug}`:`Guide ${item.locale}`}<p className="text-xs text-ink/60 mt-1">{item.has_source?'Source attached':'Missing source'}</p><div className="mt-3 flex gap-2 flex-wrap"><button type="button" disabled={busy} className="btn-primary" onClick={()=>{setSlug(item.destination_slug);if(item.kind==='guide'&&item.locale)setGuide(g=>({...g,locale:item.locale!}));setSection(item.kind==='poi'?'poi':'guide')}}>Inspect content</button><button type="button" disabled={busy||!item.has_source} className="btn-secondary" onClick={()=>{void action(t=>item.kind==='guide'?approveAdminGuide(item.destination_slug,item.locale||'en',t):publishAdminPoi(item.destination_slug,item.poi_slug!,t),'Review approved and published.')}}>Approve</button><button type="button" disabled={busy||reviewReason.trim().length<8} className="btn-secondary" onClick={()=>{void action(t=>item.kind==='guide'?requestGuideChanges(item.destination_slug,item.locale||'en',reviewReason.trim(),t):requestPoiChanges(item.destination_slug,item.poi_slug!,reviewReason.trim(),t),'Returned to draft with review feedback logged.')}}>Request changes</button></div></div>)}</div>}
        {section==='audit' && <section className="space-y-5" aria-label="Editorial content quality">
          <h2 className="text-2xl font-extrabold">Destination readiness audit</h2>
          <p className="help">This is a completeness checklist, not proof that data or photograph licensing has been independently verified. A name in the catalog does not mean its guide is ready for visitors.</p>
          {audit && <>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-[#eff8f3] p-4"><div className="text-2xl font-black text-pine">{audit.total}</div><div className="text-sm">Catalog records</div></div>
              <div className="rounded-xl bg-[#eff8f3] p-4"><div className="text-2xl font-black text-pine">{audit.published}</div><div className="text-sm">Published destination entries</div></div>
              <div className="rounded-xl bg-[#fff3df] p-4"><div className="text-2xl font-black text-amber-900">{audit.needs_attention}</div><div className="text-sm">Require content work</div></div>
            </div>
            <label className="flex gap-2 items-center text-sm font-semibold"><input type="checkbox" checked={onlyIncomplete} onChange={e=>setOnlyIncomplete(e.target.checked)}/> Show only destinations with missing content</label>
            <div className="max-h-[600px] overflow-y-auto space-y-3">
              {audit.destinations.filter(row=>!onlyIncomplete || row.missing.length>0).map(row=><article key={row.slug} className="border rounded-xl p-4">
                <div className="flex flex-wrap justify-between items-center gap-3"><div><b>{row.title}</b> <span className="text-xs text-ink/60">({row.slug})</span><div className="text-xs text-ink/60 mt-1">{row.status} · {row.photo_count} photo(s) · {row.approved_poi_count} approved attraction(s) · published languages: {row.reviewed_locales.join(', ')||'none'}</div></div><button className="btn-secondary" type="button" onClick={()=>{setSlug(row.slug);setSection('guide')}}>Edit content</button></div>
                {row.missing.length?<ul className="mt-3 flex flex-wrap gap-2">{row.missing.map(m=><li className="bg-amber-50 text-amber-900 text-xs px-2 py-1 rounded-md" key={m}>{m.replaceAll('_',' ')}</li>)}</ul>:<p className="text-xs text-pine mt-2">Core editorial checklist satisfied; source accuracy still needs human validation.</p>}
              </article>)}
            </div>
          </>}
        </section>}
        {section==='new' && <form onSubmit={e=>{e.preventDefault();void action(async t=>{const p=await createAdminDestination(newPlace,t);setSlug(p.slug);setSection('guide')},'Destination draft created. Add a sourced guide before publishing.')}} className="space-y-5"><h2 className="text-2xl font-extrabold">Create a destination</h2>{(['title','slug','district','province','summary'] as const).map(k=><label key={k} className="field"><span>{k[0].toUpperCase()+k.slice(1)}</span><input className={fieldStyle} required={k!=='summary'} value={newPlace[k]} onChange={e=>setNewPlace(v=>({...v,[k]:e.target.value}))}/></label>)}<button className="btn-primary" disabled={busy} type="submit">Create draft</button></form>}
      </div>
    </div>
  </main>
}
