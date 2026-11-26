import {useCallback, useEffect, useState, type FormEvent} from 'react'
import {Link} from 'react-router-dom'
import {MessageSquare, ShieldCheck} from 'lucide-react'
import {useTourismoAuth} from '../app/Auth'
import {providerCustomerReviews, submitProviderResponse, vendorOrganizations,
  type ProviderCustomerReview, type VendorOrganization} from '../lib/api'

export function ProviderFeedback(){
  const auth=useTourismoAuth()
  const [orgs,setOrgs]=useState<VendorOrganization[]>([])
  const [orgId,setOrgId]=useState('')
  const [feedback,setFeedback]=useState<ProviderCustomerReview[]>([])
  const [drafts,setDrafts]=useState<Record<string,string>>({})
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const load=useCallback(async(id:string)=>{
    const jwt=await auth.token();if(!jwt)return
    const data=await providerCustomerReviews(id,jwt)
    setFeedback(data)
    setDrafts(Object.fromEntries(data.map(item=>[item.review.id,item.response_draft?.body||''])))
  },[auth.token])
  useEffect(()=>{
    if(!auth.signedIn){setOrgs([]);return}
    let active=true
    void auth.token().then(jwt=>jwt?vendorOrganizations(jwt):[]).then(data=>{
      if(active){setOrgs(data);setOrgId(previous=>previous||data[0]?.id||'')}
    }).catch(e=>{if(active)setError(String(e))})
    return()=>{active=false}
  },[auth.signedIn,auth.token])
  useEffect(()=>{if(!orgId){setFeedback([]);return}
    void load(orgId).catch(e=>setError(e instanceof Error?e.message:'Unable to load feedback'))
  },[orgId,load])
  async function submit(e:FormEvent,reviewId:string){
    e.preventDefault();setBusy(reviewId);setNotice('');setError('')
    try{const jwt=await auth.token();if(!jwt)throw new Error('Please sign in')
      const res=await submitProviderResponse(orgId,reviewId,drafts[reviewId]||'',jwt)
      setNotice(res.message);await load(orgId)
    }catch(err){setError(err instanceof Error?err.message:'Unable to submit response')}
    finally{setBusy('')}
  }
  return <main className="wrap py-14 pb-24 min-h-[65vh]">
    <span className="small-label">PROVIDER FEEDBACK</span><h1 className="page-title">Customer reviews & replies</h1>
    <p className="lead">Read published traveler feedback and offer a respectful response. Tourismo reviews provider replies before they appear publicly. Customer visits are not verified.</p>
    {!auth.signedIn?<section className="empty-state mt-8"><button className="btn-primary" onClick={auth.login}>Sign in to your business</button></section>:
      <div className="mt-8 space-y-5">
        <label className="field max-w-lg">Business<select value={orgId} onChange={e=>setOrgId(e.target.value)}><option value="">Select business</option>{orgs.map(o=><option key={o.id} value={o.id}>{o.business_name}</option>)}</select></label>
        {notice&&<p role="status" className="success-banner">{notice}</p>}{error&&<p role="alert" className="error-banner">{error}</p>}
        {orgId&&feedback.length===0&&<p className="info-banner">No published customer reviews for this business yet.</p>}
        <div className="space-y-5">{feedback.map(item=><section key={item.review.id} className="form-panel space-y-3">
          <p className="small-label"><Link className="underline" to={`/listings/${item.listing_slug}`}>{item.listing_title}</Link></p>
          <div className="flex flex-wrap justify-between gap-2"><h2 className="text-lg font-bold">{item.review.title}</h2><span className="text-amber-700">{'★'.repeat(item.review.rating)}{'☆'.repeat(5-item.review.rating)}</span></div>
          <p className="whitespace-pre-wrap break-words text-sm">{item.review.body}</p>
          {item.review.response&&<p className="text-sm bg-[#f4f7f3] p-3 rounded-lg"><ShieldCheck size={16} className="inline mr-1"/>Published provider reply: {item.review.response.body}</p>}
          {item.response_draft&&<p className="text-sm text-ink/60">Your reply status: <strong>{item.response_draft.state.replace('_',' ')}</strong>{item.response_draft.state==='changes_requested'&&item.response_draft.moderation_note&&` · ${item.response_draft.moderation_note}`}</p>}
          <form className="border-t border-ink/10 pt-3 space-y-3" onSubmit={e=>void submit(e,item.review.id)}>
            <label className="field">Your business response<textarea minLength={20} maxLength={1500} rows={3} required value={drafts[item.review.id]||''} onChange={e=>setDrafts(p=>({...p,[item.review.id]:e.target.value}))} placeholder="A helpful, professional response to this feedback"/></label>
            <p className="text-xs text-ink/60">Submitting or editing a reply sends it to moderation. A published reply will be hidden while its replacement is reviewed.</p>
            <button className="btn-secondary" type="submit" disabled={busy===item.review.id}><MessageSquare size={16}/>{busy===item.review.id?'Sending…':'Submit response for review'}</button>
          </form>
        </section>)}</div>
      </div>}
  </main>
}
