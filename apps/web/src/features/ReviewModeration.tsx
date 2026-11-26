import {useCallback, useEffect, useState} from 'react'
import {Link} from 'react-router-dom'
import {ClipboardCheck, ShieldAlert} from 'lucide-react'
import {useTourismoAuth} from '../app/Auth'
import {customerReviewQueue,customerReplyQueue,customerReportQueue,moderateCustomerReview,
  moderateProviderResponse,moderateCustomerReport,removeCustomerReview,
  type ReviewModerationItem,type ReplyModerationItem,type CustomerReportItem,type ReviewDecision} from '../lib/api'

type Tab = 'reviews'|'replies'|'reports'
export function ReviewModeration(){
  const auth=useTourismoAuth()
  const allowed=auth.profile?.roles.includes('admin')===true
  const [tab,setTab]=useState<Tab>('reviews')
  const [reviewState,setReviewState]=useState<'pending'|'published'>('pending')
  const [reviews,setReviews]=useState<ReviewModerationItem[]>([])
  const [replies,setReplies]=useState<ReplyModerationItem[]>([])
  const [reports,setReports]=useState<CustomerReportItem[]>([])
  const [reason,setReason]=useState('')
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const load=useCallback(async()=>{
    const jwt=await auth.token();if(!jwt)return
    if(tab==='reviews')setReviews(await customerReviewQueue(jwt,reviewState))
    if(tab==='replies')setReplies(await customerReplyQueue(jwt))
    if(tab==='reports')setReports(await customerReportQueue(jwt))
  },[auth.token,tab,reviewState])
  useEffect(()=>{if(allowed)void load().catch(e=>setError(String(e)))},[allowed,load])
  async function decide(id:string,decision:ReviewDecision|'dismissed'|'hide_review'){
    if(reason.trim().length<15){setError('Provide at least 15 characters explaining your moderation decision');return}
    setBusy(id);setError('');setNotice('')
    try{const jwt=await auth.token();if(!jwt)throw new Error('Sign in again')
      if(tab==='reviews')await moderateCustomerReview(id,decision as ReviewDecision,reason,jwt)
      if(tab==='replies')await moderateProviderResponse(id,decision as ReviewDecision,reason,jwt)
      if(tab==='reports')await moderateCustomerReport(id,decision as 'dismissed'|'hide_review',reason,jwt)
      setNotice('Moderation decision recorded.');setReason('');await load()
    }catch(err){setError(err instanceof Error?err.message:'Unable to moderate')}
    finally{setBusy('')}
  }
  async function removeReview(id:string){
    if(reason.trim().length<15){setError('Explain which policy the review violates (15 characters minimum).');return}
    if(!window.confirm('Remove this review from public view? The action will be audited.'))return
    setBusy(id);setError('');setNotice('')
    try{const jwt=await auth.token();if(!jwt)throw new Error('Sign in again')
      await removeCustomerReview(id,reason,jwt)
      setNotice('Review removed from public view and audit trail retained.');setReason('');await load()
    }catch(err){setError(err instanceof Error?err.message:'Unable to remove review')}
    finally{setBusy('')}
  }
  return <main className="wrap py-14 pb-24 min-h-[70vh]">
    <span className="small-label">TOURISMO INTERNAL TRUST OPERATIONS</span><h1 className="page-title">Customer feedback moderation</h1>
    <p className="lead">Reviews passing automatic safety checks publish without admin approval. Only flagged reviews require moderation; admins can remove policy violations from public view. Staff decisions are audit logged. Account-only feedback is not verified proof of a visit.</p>
    {!auth.signedIn?<button className="btn-primary mt-8" onClick={auth.login}>Admin sign-in</button>:
    !allowed?<section className="empty-state mt-8"><ShieldAlert size={30}/><p>Administrator access required.</p></section>:
    <div className="space-y-5 mt-8">
      <div className="flex gap-3 flex-wrap">{(['reviews','replies','reports'] as Tab[]).map(t=><button key={t} className={tab===t?'btn-primary':'btn-secondary'} aria-pressed={tab===t} onClick={()=>{setTab(t);setError('');setNotice('')}}>{t==='reviews'?'Traveler reviews':t==='replies'?'Provider responses':'Abuse reports'}</button>)}</div>
      {error&&<p role="alert" className="error-banner">{error}</p>}{notice&&<p role="status" className="success-banner">{notice}</p>}
      <section className="form-panel space-y-2"><label className="field">Decision reason (required, minimum 15 characters)<textarea rows={3} minLength={15} maxLength={600} value={reason} onChange={e=>setReason(e.target.value)} placeholder="Record the policy reason and evidence used in the decision"/></label>
        <p className="text-xs text-ink/60">Protect privacy. Do not include unnecessary personal data in moderation notes. Sensitive moderator actions require recent MFA in production.</p>
      </section>
      {tab==='reviews'&&<section className="space-y-4"><div className="flex flex-wrap gap-3 items-center justify-between"><h2 className="text-xl font-bold">{reviewState==='pending'?'Flagged reviews awaiting safety decision':'Published reviews'} ({reviews.length})</h2>
        <div className="flex gap-2"><button type="button" className={reviewState==='pending'?'btn-primary':'btn-secondary'} onClick={()=>setReviewState('pending')}>Flagged / pending</button>
        <button type="button" className={reviewState==='published'?'btn-primary':'btn-secondary'} onClick={()=>setReviewState('published')}>Published</button></div></div>
        {reviews.length===0&&<p>No {reviewState==='pending'?'flagged':'published'} reviews in this page.</p>}
        {reviews.map(r=><article className="form-panel space-y-3" key={r.id}>
          <p className="small-label"><Link to={`/listings/${r.listing_slug}`} className="underline">{r.listing_title}</Link></p><div className="flex gap-3 justify-between"><b>{r.title}</b><span className="text-amber-700">{r.rating}/5</span></div>
          <p className="whitespace-pre-wrap break-words text-sm">{r.body}</p><div className="flex gap-2 flex-wrap">{reviewState==='pending'&&<><button className="btn-primary" disabled={!!busy} onClick={()=>void decide(r.id,'published')}><ClipboardCheck size={16}/> Approve flagged review</button><button className="btn-secondary" disabled={!!busy} onClick={()=>void decide(r.id,'changes_requested')}>Request changes</button></>}
            <button className="btn-secondary text-red-700" disabled={!!busy} onClick={()=>void removeReview(r.id)}>Remove policy violation</button></div>
        </article>)}
      </section>}
      {tab==='replies'&&<section className="space-y-4"><h2 className="text-xl font-bold">Provider responses awaiting review ({replies.length})</h2>{replies.length===0&&<p>No pending provider replies.</p>}
        {replies.map(r=><article key={r.review_id} className="form-panel space-y-3"><b>{r.listing_title} — {r.review_title}</b><p className="text-sm whitespace-pre-wrap break-words">{r.body}</p><p className="text-xs">Customer review state: {r.review_state}</p>
          <div className="flex gap-2 flex-wrap"><button className="btn-primary" disabled={!!busy||r.review_state!=='published'} onClick={()=>void decide(r.review_id,'published')}>Publish response</button><button className="btn-secondary" disabled={!!busy} onClick={()=>void decide(r.review_id,'changes_requested')}>Request changes</button><button className="btn-secondary" disabled={!!busy} onClick={()=>void decide(r.review_id,'hidden')}>Hide response</button></div></article>)}
      </section>}
      {tab==='reports'&&<section className="space-y-4"><h2 className="text-xl font-bold">Open reports ({reports.length})</h2>{reports.length===0&&<p>No open reports.</p>}
        {reports.map(r=><article key={r.id} className="form-panel space-y-3"><b>{r.listing_title} — {r.review_title}</b><p className="text-sm"><strong>Report category:</strong> {r.reason}</p><p className="text-sm break-words whitespace-pre-wrap">{r.explanation}</p><p className="text-xs">Review state: {r.review_state}</p><div className="flex flex-wrap gap-2"><button className="btn-secondary" disabled={!!busy} onClick={()=>void decide(r.id,'dismissed')}>Dismiss report</button><button className="btn-primary" disabled={!!busy} onClick={()=>void decide(r.id,'hide_review')}>Hide reported review</button></div></article>)}
      </section>}
    </div>}
  </main>
}
