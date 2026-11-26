import {useCallback,useEffect,useState,type FormEvent} from 'react'
import {Link,useSearchParams} from 'react-router-dom'
import {Inbox,MessageSquare,ShieldAlert} from 'lucide-react'
import {useTourismoAuth} from '../app/Auth'
import {myEnquiries,myEnquiry,postTravelerMessage,withdrawEnquiry,vendorOrganizations,vendorEnquiries,vendorEnquiry,postVendorMessage,closeVendorEnquiry,reportEnquiry,
  type EnquirySummary,type EnquiryThread,type EnquiryReportReason,type VendorOrganization} from '../lib/api'

const readableDate=(value:string|null)=>value?new Date(value).toLocaleString():'Unknown time'
const mayReply=(state:string)=>state==='open'||state==='answered'

export function Enquiries({vendor=false}:{vendor?:boolean}){
  const auth=useTourismoAuth()
  const [params,setParams]=useSearchParams()
  const selected=params.get('id')||''
  const [orgs,setOrgs]=useState<VendorOrganization[]>([])
  const [orgId,setOrgId]=useState('')
  const [list,setList]=useState<EnquirySummary[]>([])
  const [thread,setThread]=useState<EnquiryThread|null>(null)
  const [offset,setOffset]=useState(0)
  const [draft,setDraft]=useState('')
  const [reason,setReason]=useState<EnquiryReportReason>('spam')
  const [explanation,setExplanation]=useState('')
  const [reportOpen,setReportOpen]=useState(false)
  const [notice,setNotice]=useState('')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)

  const getToken=auth.token
  const loadList=useCallback(async()=>{
    const token=await getToken()
    if(!token)return
    setList(vendor?(orgId?await vendorEnquiries(orgId,token):[]):await myEnquiries(token))
  },[getToken,vendor,orgId])
  const loadThread=useCallback(async(id:string,skip=0)=>{
    const token=await getToken()
    if(!token)return
    const data=vendor?await vendorEnquiry(orgId,id,token,skip):await myEnquiry(id,token,skip)
    setThread(previous=>skip>0&&previous&&previous.id===id?{
      ...data,messages:[...data.messages,...previous.messages]}:data)
    setOffset(skip+data.messages.length)
  },[getToken,vendor,orgId])
  useEffect(()=>{
    if(!vendor||!auth.signedIn)return
    let active=true
    void getToken().then(t=>t?vendorOrganizations(t):[]).then(items=>{
      if(active){setOrgs(items);setOrgId(id=>id||items[0]?.id||'')}
    }).catch(e=>{if(active)setError(String(e))})
    return()=>{active=false}
  },[vendor,auth.signedIn,auth.profileState,getToken])
  useEffect(()=>{
    setList([]);setThread(null);setError('');
    if(auth.signedIn&&(!vendor||orgId))void loadList().catch(e=>setError(String(e)))
  },[auth.signedIn,auth.profileState,vendor,orgId,loadList])
  useEffect(()=>{
    setThread(null);setOffset(0);setNotice('');setError('');setReportOpen(false)
    if(selected&&auth.signedIn&&(!vendor||orgId))void loadThread(selected).catch(e=>setError(e instanceof Error?e.message:'Unable to open enquiry'))
  },[selected,auth.signedIn,auth.profileState,vendor,orgId,loadThread])
  const changeSelected=(id:string)=>setParams(id?{id}:{})

  async function doAction(action:'send'|'withdraw'|'close'|'report',e:FormEvent){
    e.preventDefault();if(!thread)return
    setBusy(true);setError('');setNotice('')
    try{
      const token=await getToken();if(!token)throw new Error('Sign in again')
      if(action==='send'){
        if(vendor)await postVendorMessage(orgId,thread.id,draft.trim(),token)
        else await postTravelerMessage(thread.id,draft.trim(),token)
        setDraft('');setNotice('Message sent')
      } else if(action==='withdraw'){
        await withdrawEnquiry(thread.id,token);setNotice('Enquiry withdrawn')
      }else if(action==='close'){
        await closeVendorEnquiry(orgId,thread.id,token);setNotice('Conversation closed')
      }else{
        await reportEnquiry(thread.id,reason,explanation.trim(),token)
        setReportOpen(false);setExplanation('');setNotice('Report submitted to Tourismo administrators')
      }
      await loadThread(thread.id);await loadList()
    }catch(e){setError(e instanceof Error?e.message:'Action failed')}
    finally{setBusy(false)}
  }
  return <main className="wrap py-14 pb-24 min-h-[65vh]">
    <span className="small-label">{vendor?'PROVIDER INBOX':'MY ENQUIRIES'}</span>
    <h1 className="page-title">{vendor?'Tourist enquiries':'Conversations with providers'}</h1>
    <p className="lead">{vendor?'Respond to interested travelers and clarify your service details. No enquiry implies a confirmed booking.':'Ask businesses questions and view their replies privately. A quotation or response is not a confirmed reservation.'}</p>
    {!auth.signedIn?<div className="form-panel mt-8"><button className="btn-primary" onClick={auth.login}>Sign in to view enquiries</button></div>:<>
      {vendor&&<label className="field max-w-xl mt-6">Business<select value={orgId} onChange={e=>{setOrgId(e.target.value);changeSelected('')}}><option value="">Choose a business</option>{orgs.map(o=><option key={o.id} value={o.id}>{o.business_name}</option>)}</select></label>}
      {notice&&<p className="success-banner mt-5" role="status">{notice}</p>}{error&&<p className="error-banner mt-5" role="alert">{error}</p>}
      <div className="grid lg:grid-cols-[minmax(230px,1fr)_minmax(0,2fr)] gap-5 mt-7 items-start">
        <section className="form-panel space-y-3"><div className="flex items-center gap-2"><Inbox size={20}/><h2 className="font-bold text-lg">Inbox</h2></div>
          {!list.length&&<p className="text-sm text-ink/70">{vendor?'No enquiries received for this business.':'No enquiries yet. Open a real service listing to contact its provider.'}</p>}
          {list.map(item=><button type="button" key={item.id} aria-pressed={selected===item.id} onClick={()=>changeSelected(item.id)} className={`w-full text-left rounded-xl border p-3 ${selected===item.id?'border-pine bg-[#eef8f2]':'border-ink/10 hover:border-pine/40'}`}>
            <b className="block break-words">{item.subject}</b><span className="block text-xs mt-1 text-ink/65">{item.listing_title}</span><span className="block text-xs mt-2">{item.state.replace('_',' ')} · {readableDate(item.updated_at)}</span>
          </button>)}
          {!vendor&&<Link to="/listings" className="text-sm text-pine underline block">Find a provider</Link>}
        </section>
        <section className="form-panel min-w-0 space-y-4">
          {!selected?<p className="text-ink/70">Select an enquiry to read its messages.</p>:!thread?<p role="status">Loading conversation…</p>:<>
            <div><h2 className="text-xl font-bold break-words">{thread.subject}</h2><Link className="text-sm text-pine underline" to={`/listings/${thread.listing_slug}`}>{thread.listing_title}</Link><p className="mt-2 text-sm">Status: <strong>{thread.state}</strong></p></div>
            <p className="text-xs text-ink/60">Private messages only. No in-app booking, payment, availability guarantee, or Tourismo-verified price is provided.</p>
            {thread.has_more&&<button type="button" className="btn-secondary" disabled={busy} onClick={()=>void loadThread(thread.id,offset).catch(e=>setError(String(e)))}>Load older messages</button>}
            <div className="space-y-3" aria-label="Conversation messages">{thread.messages.map(msg=><article key={msg.id} className={`rounded-xl p-4 border ${msg.sender===(vendor?'vendor':'traveler')?'border-pine/30 bg-[#eef8f2]':'border-ink/10 bg-white'}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-2"><b className="text-sm">{msg.sender===(vendor?'vendor':'traveler')?'You':vendor?'Traveler':'Provider'}</b><time className="text-xs text-ink/60">{readableDate(msg.created_at)}</time></div>
              <p className="mt-2 text-sm whitespace-pre-wrap break-words">{msg.body}</p>
            </article>)}</div>
            {mayReply(thread.state)?<>
              <form className="space-y-3 border-t border-ink/10 pt-4" onSubmit={e=>void doAction('send',e)}>
                <label className="field">Reply<textarea rows={4} minLength={10} maxLength={2000} required value={draft} onChange={e=>setDraft(e.target.value)} placeholder="Reply with helpful information, not payment instructions"/></label>
                <button className="btn-primary" disabled={busy} type="submit"><MessageSquare size={17}/>{busy?'Sending…':'Send message'}</button>
              </form>
              <form onSubmit={e=>void doAction(vendor?'close':'withdraw',e)}>
                <button type="submit" className="btn-secondary" disabled={busy}>{vendor?'Close conversation':'Withdraw enquiry'}</button>
              </form>
            </>:<p className="info-banner">This conversation is closed to new messages.</p>}
            <div className="border-t border-ink/10 pt-4 space-y-3">
              <button type="button" className="text-sm text-pine underline flex gap-2 items-center" onClick={()=>setReportOpen(open=>!open)}><ShieldAlert size={16}/>{reportOpen?'Cancel report':'Report this conversation'}</button>
              {reportOpen&&<form className="space-y-3" onSubmit={e=>void doAction('report',e)}>
                <label className="field">Reason<select value={reason} onChange={e=>setReason(e.target.value as EnquiryReportReason)}><option value="spam">Spam</option><option value="abuse">Abuse</option><option value="privacy">Privacy concern</option><option value="misleading">Misleading information</option><option value="other">Other</option></select></label>
                <label className="field">Describe the concern<textarea required minLength={20} maxLength={600} rows={3} value={explanation} onChange={e=>setExplanation(e.target.value)}/></label>
                <button type="submit" disabled={busy} className="btn-secondary">Submit private report</button>
              </form>}
            </div>
          </>}
        </section>
      </div>
    </>}
  </main>
}
