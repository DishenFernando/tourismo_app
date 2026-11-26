import {useCallback,useEffect,useState,type FormEvent} from 'react'
import {Link} from 'react-router-dom'
import {Flag,MessageSquare,Star,ImagePlus} from 'lucide-react'
import {useTourismoAuth} from '../app/Auth'
import {
  myCustomerReviews,publicCustomerReviews,reportCustomerReview,submitCustomerReview,editCustomerReview,
  type CustomerReview,type CustomerReviewSummary,type MyCustomerReview,type ReportReason,
} from '../lib/api'

const empty = {rating:5,title:'',body:''}
const reasonLabels:Record<ReportReason,string> = {
  spam:'Spam / advertising',abuse:'Harassment or abuse',privacy:'Personal information',
  misleading:'Misleading or false information',other:'Other concern',
}

async function asDataUri(file:File):Promise<string>{
  return new Promise((resolve,reject)=>{
    const reader=new FileReader()
    reader.onload=()=>resolve(String(reader.result))
    reader.onerror=()=>reject(new Error('Could not read a selected image'))
    reader.readAsDataURL(file)
  })
}

function ReportForm({review,onDone}:{review:CustomerReview;onDone:()=>void}){
  const auth=useTourismoAuth()
  const [reason,setReason]=useState<ReportReason>('misleading')
  const [explanation,setExplanation]=useState('')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  async function submit(e:FormEvent){
    e.preventDefault();setBusy(true);setError('')
    try{
      const jwt=await auth.token();if(!jwt)throw new Error('Sign in to report this review')
      await reportCustomerReview(review.id,reason,explanation,jwt);onDone()
    }catch(err){setError(err instanceof Error?err.message:'Unable to report review')}
    finally{setBusy(false)}
  }
  return <form onSubmit={e=>void submit(e)} className="mt-3 border-t border-ink/10 pt-3 space-y-3">
    <p className="text-sm font-bold">Report this review privately</p>
    <label className="field">Reason<select value={reason} onChange={e=>setReason(e.target.value as ReportReason)}>
      {Object.entries(reasonLabels).map(([key,value])=><option key={key} value={key}>{value}</option>)}
    </select></label>
    <label className="field">Explanation<textarea required minLength={20} maxLength={600} rows={2}
      value={explanation} onChange={e=>setExplanation(e.target.value)}/></label>
    {error&&<p className="error-banner" role="alert">{error}</p>}
    <button className="btn-secondary" type="submit" disabled={busy}>{busy?'Sending…':'Send report'}</button>
  </form>
}

export function CustomerReviews({slug}:{slug:string}){
  const auth=useTourismoAuth()
  const [data,setData]=useState<CustomerReviewSummary|null>(null)
  const [mine,setMine]=useState<MyCustomerReview[]>([])
  const [form,setForm]=useState(empty)
  const [editing,setEditing]=useState<string|null>(null)
  const [files,setFiles]=useState<File[]>([])
  const [replaceImages,setReplaceImages]=useState(false)
  const [busy,setBusy]=useState(false)
  const [moreBusy,setMoreBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [reportId,setReportId]=useState<string|null>(null)
  const [reported,setReported]=useState<string[]>([])

  const load=useCallback(async(offset:number=0)=>{
    const result=await publicCustomerReviews(slug,offset)
    setData(previous=>offset>0&&previous
      ? {...result,reviews:[...previous.reviews,...result.reviews.filter(r=>!previous.reviews.some(p=>p.id===r.id))]}
      : result)
  },[slug])
  const loadMine=useCallback(async()=>{
    if(!auth.signedIn){setMine([]);return}
    const token=await auth.token();if(!token)return
    const result=await myCustomerReviews(slug,token)
    setMine(result.reviews)
  },[auth.signedIn,auth.token,slug])

  useEffect(()=>{setData(null);setError('');setForm(empty);setEditing(null);setFiles([]);setReplaceImages(false)
    void load(0).catch(()=>setError('Could not load traveler reviews'))
  },[load])
  useEffect(()=>{void loadMine().catch(()=>{})},[loadMine])

  function startEdit(item:MyCustomerReview){
    setEditing(item.id);setForm({rating:item.rating,title:item.title,body:item.body})
    setFiles([]);setReplaceImages(false);setNotice('');setError('')
  }
  function newReview(){setEditing(null);setForm(empty);setFiles([]);setReplaceImages(false);setNotice('');setError('')}
  function pickImages(items:FileList|null){
    const selected=Array.from(items||[])
    if(selected.length>5){setError('You can upload up to five photos per review.');return}
    if(selected.some(f=>!['image/jpeg','image/png','image/webp'].includes(f.type)||f.size>2_000_000)){
      setError('Use JPEG, PNG or WebP photos, each under 2 MB.');return
    }
    setError('');setFiles(selected);setReplaceImages(true)
  }
  async function submit(e:FormEvent){
    e.preventDefault();setBusy(true);setNotice('');setError('')
    try{
      const jwt=await auth.token();if(!jwt)throw new Error('Sign in to leave a review')
      const images = replaceImages ? await Promise.all(files.map(asDataUri)) : undefined
      const payload = {...form, ...(images===undefined?{}:{images})}
      const result=editing
        ? await editCustomerReview(editing,payload,jwt)
        : await submitCustomerReview(slug,payload,jwt)
      setNotice(result.message);newReview();setNotice(result.message)
      await Promise.all([load(0),loadMine()])
    }catch(err){setError(err instanceof Error?err.message:'Could not save your review')}
    finally{setBusy(false)}
  }
  async function loadMore(){
    if(!data)return
    setMoreBusy(true)
    try{await load(data.reviews.length)}
    catch{setError('Could not load more reviews')}
    finally{setMoreBusy(false)}
  }

  const edited=mine.find(item=>item.id===editing)
  const canWrite=(mine.length<5||editing!==null)&&auth.profile?.profile_completed
  return <section className="form-panel mt-9 space-y-5" aria-label="Traveler reviews">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="small-label">COMMUNITY FEEDBACK</p><h2 className="text-2xl font-bold mt-1">Traveler reviews</h2></div>
      <span className="inline-flex gap-2 items-center text-pine font-bold"><Star size={20}/>
        {data?.average_rating?.toFixed(1)??'No ratings yet'} <span className="text-ink/60 font-normal">({data?.count??0})</span>
      </span>
    </div>
    <p className="text-sm text-ink/65">Only the author can edit a review. Reviews that pass automated checks publish automatically. Potential violations are checked by our moderation team. <strong>Tourismo has not independently verified stays or purchases.</strong></p>
    {data?.reviews.length===0&&<p className="info-banner">No published reviews yet. Share a helpful experience.</p>}
    <div className="space-y-4">{data?.reviews.map(review=><article key={review.id} className="rounded-xl border border-ink/10 p-4 space-y-2">
      <div className="flex items-center justify-between gap-2"><b>{review.title}</b><span className="text-amber-700" aria-label={`${review.rating} of 5 stars`}>{'★'.repeat(review.rating)}{'☆'.repeat(5-review.rating)}</span></div>
      <p className="text-xs text-ink/55">{review.author_label} · Visit not verified · {review.created_at?new Date(review.created_at).toLocaleDateString():'Date unavailable'}</p>
      <p className="whitespace-pre-wrap break-words text-sm">{review.body}</p>
      {!!review.images?.length&&<div className="grid grid-cols-2 sm:grid-cols-3 gap-2" aria-label="Review photos">
        {review.images.map(url=><a key={url} href={url} target="_blank" rel="noopener noreferrer"><img src={url} loading="lazy" alt="Photo contributed with this traveler review" className="w-full aspect-square rounded-lg object-cover"/></a>)}
      </div>}
      {mine.find(own=>own.id===review.id&&own.state!=='hidden')&&<button type="button" className="text-xs underline font-semibold text-pine" onClick={()=>{const owned=mine.find(own=>own.id===review.id);if(owned)startEdit(owned)}}>Edit your review</button>}
      {review.response&&<div className="bg-[#f4f7f3] p-3 rounded-lg"><p className="font-bold text-sm"><MessageSquare size={15} className="inline mr-1"/>Provider response</p><p className="text-sm whitespace-pre-wrap break-words mt-1">{review.response.body}</p></div>}
      {auth.signedIn&&!reported.includes(review.id)&&<button className="text-xs underline text-ink/60" onClick={()=>setReportId(v=>v===review.id?null:review.id)}><Flag size={13} className="inline"/> Report a concern</button>}
      {reported.includes(review.id)&&<p className="text-xs text-pine" role="status">Report sent privately.</p>}
      {reportId===review.id&&<ReportForm review={review} onDone={()=>{setReported(v=>[...v,review.id]);setReportId(null)}}/>}
    </article>)}</div>
    {data&&data.reviews.length<data.count&&<button type="button" className="btn-secondary" disabled={moreBusy} onClick={()=>void loadMore()}>
      {moreBusy?'Loading…':`See more reviews (${data.count-data.reviews.length} remaining)`}
    </button>}

    <div className="border-t border-ink/10 pt-5 space-y-3">
      <h3 className="text-lg font-bold">Share your experience</h3>
      {!auth.signedIn?<button className="btn-secondary" onClick={auth.login}>Sign in to review</button>:
        !auth.profile?.profile_completed?<p className="info-banner">Complete your <Link className="underline font-bold" to="/account">Tourismo profile</Link> before reviewing.</p>:
        <>
          <p className="text-sm text-ink/65">Only reviews posted from your signed-in account can be edited here. You've written {mine.length} of 5 permitted reviews for this service. Each review can include up to five photos.</p>
          {!!mine.length&&<div className="flex flex-wrap gap-2" aria-label="Your reviews">{mine.map((r,i)=><button key={r.id} type="button" className="btn-secondary text-xs" onClick={()=>startEdit(r)} disabled={r.state==='hidden'}>
            Edit review {i+1} ({r.state.replace('_',' ')})</button>)}</div>}
          {editing&&<button type="button" className="text-sm underline" onClick={newReview}>Write a new review instead</button>}
          {!editing&&mine.length===5&&<p className="info-banner">You've reached the five-review limit. You can still edit eligible existing reviews.</p>}
          {canWrite&&<form onSubmit={e=>void submit(e)} className="space-y-3">
            {edited&&<p className="text-sm">Editing review: <strong>{edited.state.replace('_',' ')}</strong>. {edited.state==='changes_requested'&&edited.moderation_note}</p>}
            <label className="field">Rating<select value={form.rating} onChange={e=>setForm(v=>({...v,rating:Number(e.target.value)}))}>{[5,4,3,2,1].map(n=><option key={n} value={n}>{n} / 5 stars</option>)}</select></label>
            <label className="field">Review title<input required minLength={4} maxLength={120} value={form.title} onChange={e=>setForm(v=>({...v,title:e.target.value}))} placeholder="A short, useful summary"/></label>
            <label className="field">Your review<textarea required minLength={30} maxLength={2000} rows={4} value={form.body} onChange={e=>setForm(v=>({...v,body:e.target.value}))} placeholder="Describe what happened, without sharing personal information"/></label>
            <label className="field"><span className="inline-flex items-center gap-2"><ImagePlus size={18}/> Photos (optional; up to 5)</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={e=>pickImages(e.target.files)}/></label>
            {!!files.length&&<ul className="text-sm text-ink/70">{files.map((f,i)=><li key={i}>{f.name}</li>)}</ul>}
            {edited?.images?.length&&!replaceImages&&<p className="text-xs text-ink/60">Your {edited.images.length} existing photos will be kept if you don't select replacements.</p>}
            {edited?.images?.length&&<button type="button" className="text-xs underline" onClick={()=>{setFiles([]);setReplaceImages(true)}}>Remove existing photos</button>}
            <p className="text-xs text-ink/60">Only JPEG, PNG and WebP. Each photo max 2 MB. Photos are sent to an automated safety provider before publication; prohibited images are rejected.</p>
            <button type="submit" className="btn-primary" disabled={busy}>{busy?'Checking…':editing?'Save edited review':'Publish review'}</button>
          </form>}
        </>}
      {notice&&<p role="status" className="success-banner">{notice}</p>}
      {error&&<p role="alert" className="error-banner">{error}</p>}
    </div>
  </section>
}
