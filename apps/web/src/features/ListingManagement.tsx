import { useCallback, useEffect, useState, type Dispatch, type FormEvent, type SetStateAction } from 'react'
import { Link } from 'react-router-dom'
import { Building2, CheckCircle2, ImagePlus, Plus, RefreshCw, ShieldCheck } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { addServicePhoto, uploadServiceListingPhoto, archiveServiceListing, createServiceListing, quickStartServiceListing, myServiceListings,
  removeServicePhoto, submitServiceListing, updateServiceListing, vendorOrganizations,
  saveListingRevision, submitListingRevision, submittedListingRevisions, decideListingRevision,
  type ListingPhotoWrite, type ListingWrite, type ListingRevision, type ServiceListing, type VendorCategory, type VendorOrganization } from '../lib/api'
import { listingReadiness, listingSteps, validateListingStep } from '../lib/listingWizard'

const label:Record<string,string> = {accommodation:'Accommodation',restaurant:'Restaurant',guide:'Tour guide',transport:'Transport',tour_operator:'Tour operator',activity:'Activity'}
const defaults=(category:VendorCategory):Record<string,unknown>=>{
  switch(category){
    case 'accommodation':return {room_types:[{name:'Standard room',max_adults:2,max_children:0,number_of_rooms:1,indicative_nightly_lkr_minor:null}],amenities:[],house_rules:''}
    case 'restaurant':return {cuisines:['Sri Lankan'],dietary_options:[],menu_items:[],opening_notes:''}
    case 'guide':return {languages:['English'],service_areas:['Colombo'],qualification_notes:'',indicative_daily_lkr_minor:null}
    case 'transport':return {vehicle_types:[{name:'Passenger van',passenger_seats:6,luggage_bags:4,indicative_day_lkr_minor:null}],service_areas:['Colombo'],transfer_notes:''}
    default:return {experience_types:['Local experience'],service_areas:['Colombo'],duration_notes:'',minimum_age:null,indicative_person_lkr_minor:null}
  }
}
const empty=(category:VendorCategory):ListingWrite=>({title:'',summary:'',description:'',public_email:null,public_phone:null,latitude:null,longitude:null,location_source_url:null,location_note:null,details:defaults(category)})
const blankPhoto:ListingPhotoWrite={image_url:'',source_url:'',credit:'',license_name:'',license_url:'',alt_text:''}
const fromCsv=(v:string)=>v.split(',').map(x=>x.trim()).filter(Boolean)

function DetailFields({category,details,onChange}:{category:VendorCategory;details:Record<string,unknown>;onChange:(v:Record<string,unknown>)=>void}) {
  const text=(key:string)=>String(details[key]??'')
  const set=(key:string,v:unknown)=>onChange({...details,[key]:v})
  const tags=(key:string)=>Array.isArray(details[key])?(details[key] as string[]).join(', '):''
  const list=(key:string)=>Array.isArray(details[key])?details[key] as Record<string,unknown>[]:[]
  const updateRow=(key:string,i:number,field:string,val:unknown)=>set(key,list(key).map((x,j)=>i===j?{...x,[field]:val}:x))
  const addRow=(key:string,row:Record<string,unknown>)=>set(key,[...list(key),row])
  const dropRow=(key:string,i:number)=>set(key,list(key).filter((_,j)=>i!==j))
  const csvField=(key:string,title:string)=><label className="field">{title}<input value={tags(key)} onChange={e=>set(key,fromCsv(e.target.value))} placeholder="Separate with commas"/></label>
  const price=(title:string,value:unknown,onChangePrice:(v:number|null)=>void)=><label className="field">{title} (LKR, optional)<input type="number" min="0" step="0.01" value={typeof value==='number'?value/100:''} onChange={e=>onChangePrice(e.target.value===''?null:Math.round(Number(e.target.value)*100))} placeholder="Estimate only"/></label>
  const rows=(key:string,heading:string,defaultsRow:Record<string,unknown>,fields:{key:string;label:string;kind:'text'|'number';min?:number}[],priceKey:string)=>
    <section className="space-y-3"><div className="flex items-center justify-between"><h3 className="font-bold">{heading}</h3><button type="button" className="btn-secondary" onClick={()=>addRow(key,defaultsRow)}><Plus size={14}/> Add</button></div>
      {list(key).map((row,i)=><div className="border rounded-xl p-3 grid gap-3 sm:grid-cols-2" key={i}>
        {fields.map(field=><label className="field" key={field.key}>{field.label}<input type={field.kind} min={field.min??0} required maxLength={field.kind==='text'?100:undefined} value={String(row[field.key]??'')} onChange={e=>updateRow(key,i,field.key,field.kind==='number'?Number(e.target.value):e.target.value)}/></label>)}
        {price('Indicative price',row[priceKey],v=>updateRow(key,i,priceKey,v))}
        <button type="button" className="btn-secondary self-end justify-center" onClick={()=>dropRow(key,i)}>Remove entry</button>
      </div>)}
    </section>
  return <div className="space-y-4 border-t pt-5 mt-3">
    <h3 className="font-extrabold text-lg">{label[category]} details</h3>
    {category==='accommodation'&&<>
      {rows('room_types','Room types',{name:'Room',max_adults:2,max_children:0,number_of_rooms:1,indicative_nightly_lkr_minor:null},[
        {key:'name',label:'Room type',kind:'text'},{key:'max_adults',label:'Maximum adults',kind:'number',min:1},{key:'max_children',label:'Maximum children',kind:'number'},{key:'number_of_rooms',label:'Number of rooms',kind:'number',min:1}
      ],'indicative_nightly_lkr_minor')}
      {list('room_types').map((room,i)=><div key={`age-${i}`} className="rounded-xl border border-pine/20 p-3 grid sm:grid-cols-3 gap-3">
        <label className="field">{String(room.name)} · Youngest child age<input type="number" min="0" max="17" value={String(room.min_child_age??'')} placeholder="Not specified" onChange={e=>updateRow('room_types',i,'min_child_age',e.target.value===''?null:Number(e.target.value))}/></label>
        <label className="field">Oldest child age<input type="number" min="0" max="17" value={String(room.max_child_age??'')} placeholder="Not specified" onChange={e=>updateRow('room_types',i,'max_child_age',e.target.value===''?null:Number(e.target.value))}/></label>
        <label className="field">Total guests limit<input type="number" min="1" max="60" value={String(room.max_total_guests??'')} placeholder="Optional" onChange={e=>updateRow('room_types',i,'max_total_guests',e.target.value===''?null:Number(e.target.value))}/></label>
      </div>)}
      <p className="text-xs text-ink/60">Child age policy is optional but must be accurate. Counts are maximums, not live room inventory or a booking guarantee.</p>
      {csvField('amenities','Amenities')}<label className="field">House rules<textarea rows={2} maxLength={600} value={text('house_rules')} onChange={e=>set('house_rules',e.target.value)}/></label>
    </>}
    {category==='restaurant'&&<>
      {csvField('cuisines','Cuisine types (required)')}{csvField('dietary_options','Dietary options')}
      {rows('menu_items','Menu highlights',{name:'Menu item',indicative_price_lkr_minor:null},[{key:'name',label:'Item',kind:'text'}],'indicative_price_lkr_minor')}
      <label className="field">Opening information (verify before publishing)<textarea rows={2} maxLength={500} value={text('opening_notes')} onChange={e=>set('opening_notes',e.target.value)}/></label>
    </>}
    {category==='guide'&&<>
      {csvField('languages','Guide languages (required)')}{csvField('service_areas','Service areas (required)')}
      <label className="field">Qualification notes<textarea rows={2} maxLength={600} value={text('qualification_notes')} onChange={e=>set('qualification_notes',e.target.value)}/></label>
      {price('Typical guide day rate',details.indicative_daily_lkr_minor,v=>set('indicative_daily_lkr_minor',v))}
    </>}
    {category==='transport'&&<>
      {rows('vehicle_types','Vehicle types',{name:'Vehicle',passenger_seats:4,luggage_bags:2,indicative_day_lkr_minor:null},[
        {key:'name',label:'Vehicle',kind:'text'},{key:'passenger_seats',label:'Passenger seats',kind:'number',min:1},{key:'luggage_bags',label:'Luggage bags',kind:'number'}
      ],'indicative_day_lkr_minor')}
      {csvField('service_areas','Operating areas')}<label className="field">Transfer notes<textarea rows={2} maxLength={600} value={text('transfer_notes')} onChange={e=>set('transfer_notes',e.target.value)}/></label>
    </>}
    {['activity','tour_operator'].includes(category)&&<>
      {csvField('experience_types','Experiences offered')}{csvField('service_areas','Operating areas')}
      <label className="field">Duration and inclusions<textarea rows={2} maxLength={400} value={text('duration_notes')} onChange={e=>set('duration_notes',e.target.value)}/></label>
      <label className="field">Minimum guest age (optional)<input type="number" min="0" max="100" value={String(details.minimum_age??'')} onChange={e=>set('minimum_age',e.target.value===''?null:Number(e.target.value))}/></label>
      {price('Indicative person rate',details.indicative_person_lkr_minor,v=>set('indicative_person_lkr_minor',v))}
    </>}
    <p className="text-xs text-ink/60">Prices are estimates only, in LKR. Do not publish false availability, guarantees, or unsupported qualifications.</p>
  </div>
}


/** Progressive editor: existing server validation and publication gates stay authoritative. */
function GuidedListingForm({category,form,setForm,editingId,revising,canWrite,busy,onSave,onQuickStart}:{
  category:VendorCategory; form:ListingWrite; setForm:Dispatch<SetStateAction<ListingWrite>>;
  editingId:string; revising:boolean; canWrite:boolean;busy:boolean;
  onSave:(event:FormEvent)=>void;onQuickStart:()=>Promise<void>
}) {
  const [step,setStep]=useState(0)
  const [hint,setHint]=useState('')
  const readiness=listingReadiness(category,form)
  const next=()=>{
    const issue=validateListingStep(step,category,form)
    if(issue){setHint(issue);return}
    setHint('');setStep(v=>Math.min(v+1,3))
  }
  const jump=(to:number)=>{
    if(to>step){for(let i=step;i<to;i++){
      const issue=validateListingStep(i,category,form)
      if(issue){setHint(issue);return}
    }}
    setHint('');setStep(to)
  }
  const submit=(event:FormEvent)=>{
    for(let i=0;i<3;i++){
      const issue=validateListingStep(i,category,form)
      if(issue){event.preventDefault();setHint(issue);setStep(i);return}
    }
    setHint('');onSave(event)
  }
  const textInput=(key:'title'|'summary'|'description',value:string)=>setForm(v=>({...v,[key]:value}))
  return <div className="space-y-5 mt-5">
    <div aria-label="Listing setup steps" className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {listingSteps.map((item,index)=><button key={item.title} type="button" aria-current={step===index?'step':undefined}
        className={`rounded-xl border p-3 text-left text-sm ${step===index?'border-pine bg-[#eef8f2] font-semibold':'border-ink/15'}`}
        onClick={()=>jump(index)}><span className="block text-xs text-ink/60">Step {index+1} of 4</span>{item.title}</button>)}
    </div>
    <p className="text-sm text-ink/60">{listingSteps[step].subtitle}. You can return to previous steps any time.</p>
    {hint&&<p role="alert" className="error-banner">{hint}</p>}
    <form className="space-y-4" onSubmit={submit} noValidate>
      {step===0&&<div className="space-y-4">
        <h3 className="text-lg font-bold">Start with a simple introduction</h3>
        <label className="field">What is the service called? *<input required minLength={3} maxLength={160} disabled={!canWrite}
          value={form.title} onChange={e=>textInput('title',e.target.value)} placeholder="e.g. Family room, Sri Lankan breakfast, heritage walk"/></label>
        <label className="field">A short introduction (25–350 characters)<textarea rows={3} minLength={25} maxLength={350}
          disabled={!canWrite} value={form.summary} onChange={e=>textInput('summary',e.target.value)}
          placeholder="Tell visitors what makes this service useful. Include only verified details."/></label>
        {!editingId&&canWrite&&<div className="rounded-xl border border-pine/20 p-4 space-y-2">
          <p className="text-sm font-semibold">Not ready to fill out the rest?</p>
          <p className="text-xs text-ink/65">Save just the title to your private vendor account and finish later. Nothing becomes public.</p>
          <button type="button" className="btn-secondary" disabled={busy||form.title.trim().length<3||form.title.length>160}
            onClick={()=>void onQuickStart()}>{busy?'Saving…':'Save title-only starter'}</button>
        </div>}
      </div>}
      {step===1&&<fieldset disabled={!canWrite}><DetailFields category={category} details={form.details}
        onChange={details=>setForm(v=>({...v,details}))}/></fieldset>}
      {step===2&&<div className="space-y-4">
        <h3 className="text-lg font-bold">Add public-facing details</h3>
        <label className="field">Full description (60–3500 characters) *<textarea required minLength={60} maxLength={3500}
          rows={5} disabled={!canWrite} value={form.description} onChange={e=>textInput('description',e.target.value)}
          placeholder="What can visitors expect? Add facts, inclusions and important restrictions."/></label>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="field">Public email (optional)<input type="email" disabled={!canWrite}
            value={form.public_email||''} onChange={e=>setForm(v=>({...v,public_email:e.target.value||null}))}/></label>
          <label className="field">Public phone (optional)<input disabled={!canWrite}
            value={form.public_phone||''} onChange={e=>setForm(v=>({...v,public_phone:e.target.value||null}))}/></label>
        </div>
        <p className="text-xs text-ink/60">One contact method is required for publishing review, but not for saving a draft. Private registration details stay private.</p>
        <details className="rounded-2xl border border-pine/20 p-4 space-y-3">
          <summary className="font-bold cursor-pointer">Add map coordinates (optional)</summary>
          <fieldset disabled={!canWrite} className="space-y-3 mt-3">
            <p className="text-xs text-ink/60">Enter both coordinates and an HTTPS reference. These are not verified entrances.</p>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="field">Latitude<input type="number" step="any" min="-90" max="90" value={form.latitude??''}
                onChange={e=>setForm(v=>({...v,latitude:e.target.value===''?null:Number(e.target.value)}))}/></label>
              <label className="field">Longitude<input type="number" step="any" min="-180" max="180" value={form.longitude??''}
                onChange={e=>setForm(v=>({...v,longitude:e.target.value===''?null:Number(e.target.value)}))}/></label>
            </div>
            <label className="field">Location source link<input type="url" maxLength={2048} value={form.location_source_url??''}
              placeholder="https://..." onChange={e=>setForm(v=>({...v,location_source_url:e.target.value||null}))}/></label>
            <label className="field">Location note<input maxLength={250} value={form.location_note??''}
              onChange={e=>setForm(v=>({...v,location_note:e.target.value||null}))}/></label>
          </fieldset>
        </details>
      </div>}
      {step===3&&<div className="space-y-4">
        <h3 className="text-lg font-bold">Preview your listing</h3>
        <div className="rounded-2xl border border-pine/20 bg-white p-5 space-y-3">
          <span className="small-label">PRIVATE PREVIEW · NOT PUBLISHED</span>
          <h4 className="text-2xl font-extrabold">{form.title||'Untitled service'}</h4>
          <p className="font-semibold">{form.summary||'Your introduction will appear here.'}</p>
          <p className="whitespace-pre-line text-sm">{form.description||'Your description will appear here.'}</p>
          <p className="text-sm"><strong>Service:</strong> {label[category]}</p>
          <p className="text-sm"><strong>Contact:</strong> {form.public_email||form.public_phone||'Not yet supplied'}</p>
          {form.latitude!=null&&<p className="text-sm">Map reference: {form.latitude}, {form.longitude}</p>}
          <details className="text-sm"><summary className="font-semibold cursor-pointer">Category-specific information</summary>
            <div className="mt-2 space-y-1">{Object.entries(form.details).map(([key,value])=><p key={key} className="break-words">
              <strong>{key.replaceAll('_',' ')}:</strong> {Array.isArray(value)?value.map(v=>typeof v==='object'?JSON.stringify(v):String(v)).join(' · '):String(value??'—')}</p>)}</div>
          </details>
        </div>
        <p className="info-banner">This is a private preview, not a live provider listing. Indicative pricing is not a quote or confirmed availability.</p>
        {readiness.length>0&&<div className="rounded-xl border p-3 space-y-2">
          <h4 className="font-semibold">Before requesting publication</h4>
          {readiness.map(issue=><p className="text-sm text-ink/70" key={issue}>• {issue}</p>)}
        </div>}
        <p className="text-sm text-ink/70">Save privately first. Next, attach credited service photographs if available and request review when business verification is approved.</p>
      </div>}
      <div className="flex flex-wrap gap-3 items-center border-t pt-4">
        {step>0&&<button type="button" className="btn-secondary" onClick={()=>jump(step-1)}>← Previous</button>}
        {step<3&&<button type="button" className="btn-primary" onClick={next}>Continue →</button>}
        {step===3&&canWrite&&<button type="submit" className="btn-primary" disabled={busy}>
          {busy?'Saving…':revising?'Save private revision':editingId?'Save draft changes':'Create private draft'}
        </button>}
        {!canWrite&&<p className="info-banner">Submitted listings and revisions are locked during independent review.</p>}
      </div>
    </form>
  </div>
}

function PrivateListingPhoto({url,orgId,listingId,alt}:{url:string;orgId:string;listingId:string;alt:string}) {
  const auth=useTourismoAuth()
  const [image,setImage]=useState('')
  const id=url.startsWith('/api/v1/listing-media/')?url.split('/').pop():null
  useEffect(()=>{
    if(!id){setImage(url);return}
    let active=true
    let local=''
    void (async()=>{
      const token=await auth.token();if(!token)return
      const result=await fetch(`/api/v1/vendor/organizations/${orgId}/listings/${listingId}/photos/${id}/preview`,{
        headers:{Authorization:`Bearer ${token}`}
      })
      if(!result.ok)return
      local=URL.createObjectURL(await result.blob())
      if(active)setImage(local)
      else URL.revokeObjectURL(local)
    })().catch(()=>{})
    return()=>{active=false;if(local)URL.revokeObjectURL(local)}
  },[id,orgId,listingId,url,auth.token])
  return image?<img src={image} alt={alt} referrerPolicy="no-referrer" className="w-20 h-16 rounded object-cover"/>:
    <div className="w-20 h-16 rounded bg-ink/10 flex items-center justify-center text-xs">Private image</div>
}

export function ListingManagement() {
  const auth=useTourismoAuth()
  const [orgs,setOrgs]=useState<VendorOrganization[]>([])
  const [orgId,setOrgId]=useState('')
  const [items,setItems]=useState<ServiceListing[]>([])
  const [editingId,setEditingId]=useState('')
  const [form,setForm]=useState<ListingWrite>(empty('accommodation'))
  const [photo,setPhoto]=useState<ListingPhotoWrite>(blankPhoto)
  const [uploadFile,setUploadFile]=useState<File|null>(null)
  const [uploadCreator,setUploadCreator]=useState('')
  const [uploadAlt,setUploadAlt]=useState('')
  const [uploadRights,setUploadRights]=useState(false)
  const [proposalPhotos,setProposalPhotos]=useState<ListingPhotoWrite[]>([])
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  const [error,setError]=useState('')
  const org=orgs.find(x=>x.id===orgId)
  const active=items.find(x=>x.id===editingId)
  const canWrite=!active||['draft','changes_requested','published'].includes(active.status) && active.revision?.status!=='submitted'
  const revising=active?.status==='published'
  const load=useCallback(async()=>{const jwt=await auth.token();if(!jwt)return;setOrgs(await vendorOrganizations(jwt))},[auth])
  const loadItems=useCallback(async(id:string)=>{if(!id)return;const jwt=await auth.token();if(!jwt)return;setItems(await myServiceListings(id,jwt))},[auth])
  useEffect(()=>{if(auth.signedIn)void load().catch(e=>setError(String(e)))},[auth.signedIn,load])
  useEffect(()=>{setItems([]);setEditingId('');if(orgId){void loadItems(orgId).catch(e=>setError(String(e)))}},[orgId,loadItems])
  useEffect(()=>{if(org){setForm(empty(org.category))}},[org?.category,orgId])
  const run=async(fn:(jwt:string)=>Promise<unknown>,notice:string)=>{setBusy(true);setMessage('');setError('');try{const jwt=await auth.token();if(!jwt)throw new Error('Sign in to manage listings');await fn(jwt);setMessage(notice);await loadItems(orgId)}catch(e){setError(e instanceof Error?e.message:'Action failed')}finally{setBusy(false)}}
  const selectItem=(item:ServiceListing)=>{
    const draft=item.revision?.snapshot
    setEditingId(item.id)
    setForm({title:draft?.title??item.title,summary:draft?.summary??item.summary,
      description:draft?.description??item.description,public_email:draft?.public_email??item.public_email,
      public_phone:draft?.public_phone??item.public_phone,details:{...defaults(item.category),...structuredClone(draft?.details??item.details)},
      latitude:draft?draft.latitude:item.latitude,longitude:draft?draft.longitude:item.longitude,
      location_source_url:draft?draft.location_source_url:item.location_source_url,
      location_note:draft?draft.location_note:item.location_note})
    setProposalPhotos(structuredClone(draft?.photos??item.photos.map(({id:_,...fields})=>fields)))
    setPhoto(blankPhoto)
  }
  const save=async(e:FormEvent)=>{e.preventDefault();if(!orgId)return;const target=editingId
    await run(async jwt=>{
      if(target&&revising){await saveListingRevision(orgId,target,{...form,photos:proposalPhotos},jwt)}
      else {const saved=target?await updateServiceListing(orgId,target,form,jwt):await createServiceListing(orgId,form,jwt);setEditingId(saved.id)}
    },revising?'Private revision saved. Your published listing remains unchanged.':target?'Listing draft updated.':'Listing draft created.')}
  const quickStart=async()=>{
    if(!orgId||editingId||form.title.trim().length<3)return
    await run(async jwt=>{
      const created=await quickStartServiceListing(orgId,form.title,jwt)
      setEditingId(created.id)
    },'Private starter saved. Add more information whenever you are ready. Nothing is published.')
  }
  if(!auth.signedIn)return <main className="wrap py-16 min-h-[70vh]"><h1 className="page-title">Manage business listings</h1><p className="lead">Sign in with your Tourismo account to create service listings.</p><button className="btn-primary mt-6" onClick={auth.login}>Sign in</button></main>
  return <main className="wrap py-14 pb-24 min-h-[70vh]"><span className="small-label">TOURISMO PARTNER STUDIO</span><h1 className="page-title">Your services, beautifully presented</h1>
    <p className="lead">Create drafts for your verified business. Listing publication requires separate administrator approval. No subscriptions or tourist bookings are activated here.</p>
    <div className="flex flex-wrap items-center gap-3 mt-6"><Link to="/vendors" className="btn-secondary"><Building2 size={17}/> Business verification</Link><button className="btn-secondary" type="button" onClick={()=>void load().catch(e=>setError(String(e)))}><RefreshCw size={17}/> Refresh</button></div>
    {error&&<p role="alert" className="error-banner mt-5">{error}</p>}{message&&<p role="status" className="success-banner mt-5"><CheckCircle2 size={17}/>{message}</p>}
    <label className="field mt-7 max-w-xl">Choose your business<select value={orgId} onChange={e=>setOrgId(e.target.value)}><option value="">Select organization</option>{orgs.map(o=><option value={o.id} key={o.id}>{o.business_name} ({o.verification_state})</option>)}</select></label>
    {!org&&<div className="empty-state mt-7"><Building2 size={33}/><h2 className="font-bold mt-2">No business selected</h2><p>First register your business in the Vendor Dashboard, then create listing drafts here.</p><Link className="btn-primary mt-4" to="/vendors">Open vendor dashboard</Link></div>}
    {org&&<div className="grid lg:grid-cols-[300px_1fr] gap-6 mt-7 items-start"><aside className="form-panel space-y-3"><div className="flex justify-between items-center gap-2"><h2 className="font-extrabold">Listings</h2><button type="button" className="btn-secondary" onClick={()=>{setEditingId('');setForm(empty(org.category));setPhoto(blankPhoto);setProposalPhotos([])}}><Plus size={14}/> New</button></div>
      {items.length===0&&<p className="text-sm text-ink/60">No listing drafts yet.</p>}
      {items.map(item=><button type="button" key={item.id} onClick={()=>selectItem(item)} className={`rounded-xl p-3 w-full text-left border ${editingId===item.id?'border-pine bg-[#eef8f2]':'border-ink/10'}`}><b className="block">{item.title}</b><span className="text-xs text-ink/60">{item.status.replaceAll('_',' ')}</span></button>)}
    </aside><section className="space-y-5"><div className="form-panel"><h2 className="text-xl font-extrabold">{editingId?'Listing details':'Create a new listing'}</h2><p className="text-sm mt-1 text-ink/60">{label[org.category]} · {org.district}, {org.province}</p>
      {org.verification_state!=='approved'&&<p className="info-banner mt-4">You can create a draft, but must complete business verification before submitting it for publication.</p>}
      {active?.review_feedback&&<p className="error-banner mt-4">Reviewer feedback: {active.review_feedback}</p>}
      <GuidedListingForm key={`${orgId}:${editingId}`} category={org.category} form={form} setForm={setForm}
        editingId={editingId} revising={Boolean(revising)} canWrite={Boolean(canWrite)} busy={busy}
        onSave={save} onQuickStart={quickStart}/></div>
      {active&&<div className="form-panel space-y-4"><div className="flex justify-between gap-2"><h2 className="text-lg font-extrabold">Credited photographs</h2><span className="text-xs text-ink/60">{active.photos.length}/10</span></div><p className="text-sm text-ink/60">Add only photographs of this actual provider/service, with rights to publish and a verifiable license/source URL. Remote images are not stored by Tourismo.</p>
        {active.photos.map(p=><div className="flex gap-3 border rounded-xl p-2 items-center" key={p.id}><PrivateListingPhoto url={p.image_url} alt={p.alt_text} orgId={orgId} listingId={active.id}/><div className="flex-1 text-xs"><b>{p.credit}</b><p>{p.license_name}</p></div>{canWrite&&!revising&&<button className="btn-secondary" type="button" disabled={busy} onClick={()=>void run(jwt=>removeServicePhoto(orgId,active.id,p.id,jwt),'Photo removed.')}>Remove</button>}</div>)}
        {revising&&<div className="rounded-xl border p-4 space-y-2"><p className="font-bold">Proposed photos ({proposalPhotos.length}/10)</p><p className="text-xs">The live gallery stays visible until admin approval. Add or remove photo references here, then save your revision.</p>
          {proposalPhotos.map((p,i)=><div key={`${p.source_url}-${i}`} className="flex items-center justify-between gap-3 text-sm border-b py-2"><span className="truncate">{p.alt_text} · {p.credit}</span><button type="button" className="underline text-red-700" disabled={!canWrite} onClick={()=>setProposalPhotos(v=>v.filter((_,j)=>j!==i))}>Remove from proposal</button></div>)}
          {canWrite&&<form onSubmit={e=>{e.preventDefault();if(!proposalPhotos.some(p=>p.source_url===photo.source_url)&&proposalPhotos.length<10){setProposalPhotos(v=>[...v,photo]);setPhoto(blankPhoto)}else setError('Photo already attached or gallery limit reached')}} className="grid sm:grid-cols-2 gap-3">{(Object.keys(blankPhoto) as (keyof ListingPhotoWrite)[]).map(key=><label className="field" key={key}>{key.replaceAll('_',' ')}<input type={key.includes('url')?'url':'text'} required value={photo[key]} onChange={e=>setPhoto(v=>({...v,[key]:e.target.value}))}/></label>)}<button className="btn-secondary" disabled={proposalPhotos.length>=10} type="submit">Add to revision</button></form>}
        </div>}
        {canWrite&&!revising&&<form className="rounded-xl border border-pine/20 p-4 grid gap-3 sm:grid-cols-2" onSubmit={e=>{
          e.preventDefault()
          if(!uploadFile||!uploadRights||!active)return
          void run(async jwt=>{
            await uploadServiceListingPhoto(orgId,active.id,uploadFile,uploadCreator,uploadAlt,jwt)
            setUploadFile(null);setUploadCreator('');setUploadAlt('');setUploadRights(false)
          },'Photograph uploaded privately. It becomes public only after listing approval.')
        }}>
          <h3 className="font-bold sm:col-span-2">Upload a real service photo (local development)</h3>
          <p className="text-xs sm:col-span-2 text-ink/60">No source URL needed for photos you own. JPEG/PNG only, up to 3 MB. AI illustrations are not accepted as photographic evidence of a real business.</p>
          <label className="field sm:col-span-2">Photograph<input type="file" accept="image/jpeg,image/png" required onChange={e=>setUploadFile(e.target.files?.[0]||null)}/></label>
          <label className="field">Photographer or business name<input required minLength={2} maxLength={160} value={uploadCreator} onChange={e=>setUploadCreator(e.target.value)}/></label>
          <label className="field">Description for accessibility<input required minLength={8} maxLength={240} value={uploadAlt} onChange={e=>setUploadAlt(e.target.value)}/></label>
          <label className="sm:col-span-2 text-sm flex items-start gap-2"><input type="checkbox" required checked={uploadRights} onChange={e=>setUploadRights(e.target.checked)}/> I own this photograph or have permission to publish it, and it accurately depicts this service.</label>
          <button type="submit" className="btn-secondary sm:col-span-2 justify-center" disabled={busy||!uploadFile||uploadFile.size>3*1024*1024||!uploadRights||active.photos.length>=10}>Upload photograph</button>
          {uploadFile&&uploadFile.size>3*1024*1024&&<p className="error-banner sm:col-span-2">Image exceeds 3 MB.</p>}
        </form>}
        {canWrite&&!revising&&<form onSubmit={e=>{e.preventDefault();void run(async jwt=>{await addServicePhoto(orgId,active.id,photo,jwt);setPhoto(blankPhoto)},'Credited photograph attached.')}} className="grid sm:grid-cols-2 gap-3">{(Object.keys(blankPhoto) as (keyof ListingPhotoWrite)[]).map(key=><label key={key} className="field capitalize">{key.replaceAll('_',' ')}<input type={key.includes('url')?'url':'text'} required value={photo[key]} maxLength={key==='alt_text'?240:undefined} onChange={e=>setPhoto(v=>({...v,[key]:e.target.value}))}/></label>)}<button type="submit" className="btn-secondary justify-center" disabled={busy||active.photos.length>=10}><ImagePlus size={17}/> Add photo</button></form>}
        {canWrite&&!revising&&<button className="btn-primary mt-4" type="button" disabled={busy||org.verification_state!=='approved'} onClick={()=>void run(jwt=>submitServiceListing(orgId,active.id,jwt),'Listing submitted for independent administrator review.')}>Submit for publishing review</button>}
        {revising&&<div className="info-banner">Live content remains public until your proposed changes are approved. {active.revision&&`Revision status: ${active.revision.status}.`}{active.revision?.review_feedback&&<p>Reviewer: {active.revision.review_feedback}</p>}
          {active.revision&&['draft','changes_requested'].includes(active.revision.status)&&<button type="button" disabled={busy||org.verification_state!=='approved'} className="btn-primary mt-3" onClick={()=>void run(jwt=>submitListingRevision(orgId,active.id,jwt),'Revision submitted for independent review. Live listing unchanged.')}>Submit saved revision for review</button>}
        </div>}
        {active.status==='published'&&<Link className="text-pine underline block text-sm" to={`/listings/${active.slug}`}>Open public listing</Link>}
        {active.status!=='archived'&&<button className="text-red-700 underline text-sm" type="button" disabled={busy} onClick={()=>{if(window.confirm('Archive this listing? It will disappear from public discovery.'))void run(jwt=>archiveServiceListing(orgId,active.id,jwt),'Listing archived.')}}>Archive listing</button>}
      </div>}
    </section></div>}
  </main>
}

export function AdminListingReviews() {
  const auth=useTourismoAuth()
  const [items,setItems]=useState<ServiceListing[]>([])
  const [selected,setSelected]=useState('')
  const [decision,setDecision]=useState<'published'|'changes_requested'>('published')
  const [reason,setReason]=useState('')
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [busy,setBusy]=useState(false)
  const [revisions,setRevisions]=useState<ListingRevision[]>([])
  const [revisionId,setRevisionId]=useState('')
  const [revisionDecision,setRevisionDecision]=useState<'approved'|'changes_requested'>('approved')
  const refresh=useCallback(async()=>{const jwt=await auth.token();if(jwt){setItems(await (await import('../lib/api')).listingReviewQueue(jwt));setRevisions(await submittedListingRevisions(jwt))}},[auth])
  useEffect(()=>{if(auth.profile?.roles.includes('admin'))void refresh().catch(e=>setError(String(e)))},[auth.profile?.roles,refresh])
  const item=items.find(x=>x.id===selected)
  const revision=revisions.find(x=>x.id===revisionId)
  const submit=async(e:FormEvent)=>{e.preventDefault();if(!item)return;setBusy(true);setError('');setNotice('');try{const jwt=await auth.token();if(!jwt)throw new Error('Please sign in');await (await import('../lib/api')).decideServiceListing(item.id,decision,reason,jwt);setNotice('Moderation decision recorded.');setSelected('');setReason('');await refresh()}catch(e){setError(e instanceof Error?e.message:'Review failed')}finally{setBusy(false)}}
  const reviewRevision=async(e:FormEvent)=>{e.preventDefault();if(!revision)return;setBusy(true);setError('');setNotice('');try{const jwt=await auth.token();if(!jwt)throw new Error('Sign in required');await decideListingRevision(revision.id,revisionDecision,reason,jwt);setNotice('Revision review recorded.');setReason('');setRevisionId('');await refresh()}catch(e){setError(e instanceof Error?e.message:'Revision review failed')}finally{setBusy(false)}}
  return <main className="wrap py-14 pb-24 min-h-[70vh]"><span className="small-label">TOURISMO PLATFORM ADMIN</span><h1 className="page-title">Service listing approvals</h1><p className="lead">Independent moderation of vendor-submitted public listings. Business verification alone never publishes a service.</p>
    {!auth.profile?.roles.includes('admin')?<p className="error-banner mt-7">Administrator access required.</p>:<div className="grid lg:grid-cols-[300px_1fr] gap-6 mt-8"><aside className="form-panel space-y-3"><h2 className="font-bold">Submitted listings ({items.length})</h2><button type="button" className="btn-secondary" onClick={()=>void refresh().catch(e=>setError(String(e)))}><RefreshCw size={15}/> Refresh</button>{items.length===0&&<p className="text-sm text-ink/60">No pending listing reviews.</p>}{items.map(x=><button key={x.id} type="button" className={`w-full text-left p-3 rounded-xl border ${selected===x.id?'border-pine':'border-ink/10'}`} onClick={()=>setSelected(x.id)}><b>{x.title}</b><span className="block text-xs text-ink/60">{label[x.category]} · {x.district}</span></button>)}</aside>
      <section className="form-panel">{error&&<p role="alert" className="error-banner">{error}</p>}{notice&&<p className="success-banner">{notice}</p>}{!item?<div className="empty-state"><ShieldCheck size={32}/><p>Select a submitted listing to review its public content.</p></div>:<><h2 className="text-xl font-bold">{item.title}</h2><p className="text-sm text-ink/60">{item.category} · {item.district} · Business ID {item.organization_id}</p><p className="my-4">{item.summary}</p><p className="whitespace-pre-line text-sm">{item.description}</p><details className="my-4"><summary className="cursor-pointer font-semibold">Category data</summary><pre className="whitespace-pre-wrap text-xs mt-2">{JSON.stringify(item.details,null,2)}</pre></details><p className="text-xs text-ink/60">{item.photos.length} credited images</p>{item.photos.map(p=><div key={p.id} className="text-xs mt-2"><a className="underline text-pine" href={p.source_url} target="_blank" rel="noopener noreferrer">{p.alt_text}</a> — {p.credit}, {p.license_name}</div>)}<p className="mt-4 text-sm">Public contact: {item.public_email||item.public_phone||'None'}</p>
        <form onSubmit={submit} className="space-y-4 mt-6 border-t pt-5"><label className="field">Decision<select value={decision} onChange={e=>setDecision(e.target.value as 'published'|'changes_requested')}><option value="published">Approve and publish</option><option value="changes_requested">Request corrections</option></select></label><label className="field">Reason (15 characters minimum)<textarea minLength={15} maxLength={600} required rows={3} value={reason} onChange={e=>setReason(e.target.value)}/></label><p className="text-xs text-ink/60">Verify provider status, category-specific claims and photo licensing independently before approving. You cannot approve listings belonging to an organization you own or belong to.</p><button disabled={busy} className="btn-primary" type="submit"><ShieldCheck size={17}/>{busy?'Recording…':'Record review decision'}</button></form>
      </>}</section></div>}
    {auth.profile?.roles.includes('admin')&&<section className="form-panel mt-8 space-y-4"><h2 className="text-2xl font-extrabold">Published-listing revisions ({revisions.length})</h2><p className="text-sm text-ink/60">Changes to already published services remain private until a separate administrator reviews them. Compare the full proposed replacement carefully.</p>
      <div className="grid sm:grid-cols-[300px_1fr] gap-4"><div className="space-y-2">{revisions.map(r=><button key={r.id} type="button" onClick={()=>{setRevisionId(r.id);setReason('')}} className={`border rounded-xl p-3 text-left w-full ${revisionId===r.id?'border-pine':''}`}><b>{r.live_title}</b><span className="block text-xs">Proposed: {r.snapshot.title}</span></button>)}{revisions.length===0&&<p className="text-sm text-ink/60">No submitted listing revisions.</p>}</div>
        <div>{revision&&<><h3 className="font-bold">Proposed content: {revision.snapshot.title}</h3><p className="text-sm">{revision.snapshot.summary}</p><p className="whitespace-pre-line text-sm mt-2">{revision.snapshot.description}</p><details className="mt-3"><summary>Full proposed payload including images and coordinates</summary><pre className="whitespace-pre-wrap break-all text-xs mt-2">{JSON.stringify(revision.snapshot,null,2)}</pre></details>
          <form onSubmit={reviewRevision} className="mt-4 space-y-3"><label className="field">Decision<select value={revisionDecision} onChange={e=>setRevisionDecision(e.target.value as 'approved'|'changes_requested')}><option value="approved">Approve replacement</option><option value="changes_requested">Request changes</option></select></label><label className="field">Review explanation<textarea required minLength={15} maxLength={600} rows={3} value={reason} onChange={e=>setReason(e.target.value)}/></label><button type="submit" className="btn-primary" disabled={busy}>Record revision decision</button></form>
        </>}</div></div></section>}
  </main>
}
