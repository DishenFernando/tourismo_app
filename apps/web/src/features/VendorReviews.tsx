import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ClipboardCheck, LockKeyhole, ShieldAlert, ShieldCheck } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { vendorDecision, vendorReviewCase, vendorReviewQueue, downloadVendorDocument,
  type VendorCase, type VendorOrganization, type VendorState } from '../lib/api'

export function VendorReviews() {
  const auth=useTourismoAuth()
  const authorized=auth.profile?.roles.includes('admin')===true
  const [state,setState]=useState<Exclude<VendorState,'draft'>>('submitted')
  const [queue,setQueue]=useState<VendorOrganization[]>([])
  const [selected,setSelected]=useState<VendorCase|null>(null)
  const [reason,setReason]=useState('')
  const [source,setSource]=useState('')
  const [decision,setDecision]=useState<'approved'|'rejected'|'changes_requested'>('changes_requested')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [message,setMessage]=useState('')
  const refresh=useCallback(async()=>{
    const jwt=await auth.token();if(!jwt)return
    setQueue(await vendorReviewQueue(jwt,state))
    setSelected(null)
  },[auth.token,state])
  useEffect(()=>{if(authorized)void refresh().catch(e=>setError(String(e)))},[authorized,refresh])
  const open=async (id:string)=>{
    setError('');setMessage('')
    try{const jwt=await auth.token();if(jwt)setSelected(await vendorReviewCase(id,jwt))}
    catch(e){setError(e instanceof Error?e.message:'Could not load case')}
  }
  const submit=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();if(!selected)return
    setBusy(true);setError('');setMessage('')
    try{const jwt=await auth.token();if(!jwt)throw new Error('Please sign in again')
      await vendorDecision(selected.organization.id,decision,reason,source||null,jwt)
      setMessage(`Review decision recorded: ${decision.replace('_',' ')}.`)
      setReason('');setSource('');await refresh()
    }catch(e){setError(e instanceof Error?e.message:'Review failed')}finally{setBusy(false)}
  }
  return <main className="wrap py-12 pb-24 min-h-[70vh]">
    <span className="small-label">TOURISMO INTERNAL OPERATIONS</span><h1 className="page-title">Vendor verification</h1>
    <p className="lead">Private applications, independent manual checks, and auditable decisions. Only authorized platform administrators can access this area.</p>
    {!auth.signedIn&&<section className="empty-state mt-8"><LockKeyhole size={32}/><button className="btn-primary mt-4" onClick={auth.login}>Administrator sign-in</button></section>}
    {auth.signedIn&&!authorized&&<section className="empty-state mt-8"><ShieldAlert size={32}/><p>Administrator permission required.</p><Link className="btn-secondary mt-4" to="/vendors">Business dashboard</Link></section>}
    {authorized&&<div className="space-y-6 mt-8">
      {error&&<p role="alert" className="error-banner">{error}</p>}{message&&<p role="status" className="success-banner">{message}</p>}
      <div className="flex gap-3 items-center flex-wrap"><label className="field">Review state<select value={state} onChange={e=>setState(e.target.value as Exclude<VendorState,'draft'>)}><option value="submitted">Awaiting review</option><option value="changes_requested">Changes requested</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="expired_license">Expired license</option></select></label><Link className="btn-secondary" to="/admin">Content Studio</Link></div>
      <div className="grid gap-5 lg:grid-cols-[minmax(240px,.85fr)_minmax(0,1.4fr)] items-start">
        <section className="form-panel space-y-2"><h2 className="font-bold text-lg mb-3">Applications ({queue.length})</h2>{queue.length===0&&<p className="text-sm text-ink/60">No cases in this state.</p>}{queue.map(o=><button key={o.id} onClick={()=>void open(o.id)} className="w-full text-left border border-ink/10 rounded-xl p-3 hover:border-pine"><b className="block">{o.business_name}</b><span className="text-xs text-ink/60">{o.category.replace('_',' ')} · {o.district}</span></button>)}</section>
        {selected&&<section className="form-panel space-y-4"><h2 className="text-xl font-extrabold">{selected.organization.business_name}</h2><div className="rounded-lg bg-[#f4f7f3] p-4 text-sm space-y-1"><p><b>Applicant ID:</b> {selected.organization.owner_id}</p><p><b>Category:</b> {selected.organization.category}</p><p><b>Registration:</b> {selected.organization.registration_no||'Not provided'}</p><p><b>License:</b> {selected.organization.license_no||'Not provided'}</p><p><b>Contact:</b> {selected.organization.contact_email}</p><p><b>Phone:</b> {selected.organization.contact_phone||'Not provided'}</p><p><b>Address:</b> {selected.organization.operating_address}, {selected.organization.district}, {selected.organization.province}</p></div>
          <h3 className="font-bold">Submitted evidence references</h3>{selected.evidence.map(r=><div key={r.id} className="text-sm p-3 border border-ink/10 rounded-lg">{r.evidence_type.replaceAll('_',' ')} · {r.issuer} · {r.reference_number} · Expiry: {r.expires_on||'Not provided'}</div>)}
          {selected.evidence.length===0&&<p className="text-sm text-red-700">No evidence references provided.</p>}
          <h3 className="font-bold">Private uploaded documents</h3>
          {(selected.documents||[]).map(doc=><div className="flex justify-between gap-3 items-center border border-ink/10 p-3 rounded-lg text-sm" key={doc.id}><div><b>{doc.name}</b><p className="text-xs text-ink/60">{Math.ceil(doc.size_bytes/1024)} KB · {doc.scan_state.replace('_',' ')}</p></div>{doc.downloadable&&<button className="btn-secondary" onClick={()=>void (async()=>{try{const jwt=await auth.token();if(jwt)await downloadVendorDocument(selected.organization.id,doc.id,jwt,true)}catch(e){setError(String(e))}})()}>Download reviewed file</button>}</div>)}
          {(selected.documents||[]).some(d=>d.scan_state!=='clean')&&<p className="text-sm text-amber-800">Approval will be blocked until uploaded files pass antivirus scanning.</p>}
          <p className="text-xs text-ink/60">Entered reference numbers are unverified claims. Check the actual registry/issuer outside Tourismo before approval. Private uploads are available, but registry verification still requires a real external check.</p>
          {selected.history.length>0&&<div><h3 className="font-bold">Decision history</h3>{selected.history.map((item,i)=><p key={i} className="text-sm mt-2">{item.decision}: {item.reason}{item.source_url&&<> · <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="underline">Source</a></>}</p>)}</div>}
          {selected.organization.verification_state==='submitted'&&<form onSubmit={e=>void submit(e)} className="space-y-4 border-t border-ink/10 pt-4">
            <label className="field">Decision<select value={decision} onChange={e=>setDecision(e.target.value as 'approved'|'rejected'|'changes_requested')}><option value="changes_requested">Request changes</option><option value="approved">Approve after manual checks</option><option value="rejected">Reject</option></select></label>
            <label className="field">Review explanation (required)<textarea required minLength={15} maxLength={600} rows={3} value={reason} onChange={e=>setReason(e.target.value)}/></label>
            <label className="field">Verification source HTTPS URL {decision==='approved'?'(required)':'(optional)'}<input type="url" required={decision==='approved'} value={source} onChange={e=>setSource(e.target.value)} placeholder="https://official-registry.example/..."/></label>
            <button className="btn-primary" type="submit" disabled={busy}><ClipboardCheck size={17}/>{busy?'Saving…':'Record review decision'}</button>
            <p className="text-xs text-ink/60 flex gap-2"><ShieldCheck size={15}/> Business approval does not publish a listing or start a 30-day subscription trial.</p>
          </form>}
        </section>}
      </div>
    </div>}
  </main>
}
