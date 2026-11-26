import {useCallback,useEffect,useState} from 'react'
import {Link} from 'react-router-dom'
import {useTourismoAuth} from '../app/Auth'
import {enquiryAbuseReports,moderateEnquiryReport,reportedEnquiryThread,type EnquiryAbuseReport,type EnquiryThread} from '../lib/api'

export function EnquiryReportModeration(){
  const auth=useTourismoAuth()
  const [rows,setRows]=useState<EnquiryAbuseReport[]>([])
  const [state,setState]=useState<'open'|'dismissed'|'actioned'>('open')
  const [reason,setReason]=useState<Record<string,string>>({})
  const [busy,setBusy]=useState('')
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [evidence,setEvidence]=useState<Record<string,EnquiryThread>>({})
  const load=useCallback(async()=>{const token=await auth.token();if(token)setRows(await enquiryAbuseReports(token,state))},[auth.token,state])
  useEffect(()=>{if(auth.signedIn)void load().catch(e=>setError(String(e)))},[auth.signedIn,auth.profileState,load])
  async function decide(id:string,decision:'dismissed'|'block_thread'){
    setBusy(id);setError('');setNotice('')
    try{
      const token=await auth.token();if(!token)throw new Error('Please sign in')
      await moderateEnquiryReport(id,decision,(reason[id]||'').trim(),token)
      setNotice('Report decision saved');await load()
    }catch(e){setError(e instanceof Error?e.message:'Unable to review report')}
    finally{setBusy('')}
  }
  function confirmBlock(id:string){
    if((reason[id]||'').trim().length<15){setError('Enter a decision reason of at least 15 characters.');return}
    if(window.confirm('Block both parties from messaging in this enquiry?'))void decide(id,'block_thread')
  }
  async function viewEvidence(id:string){
    setError('');try{const token=await auth.token();if(!token)throw new Error('Please sign in');const thread=await reportedEnquiryThread(id,token);setEvidence(items=>({...items,[id]:thread}))}
    catch(e){setError(e instanceof Error?e.message:'Unable to view evidence')}
  }
  return <main className="wrap py-14 pb-24 min-h-[65vh]">
    <span className="small-label">TRUST OPERATIONS</span><h1 className="page-title">Enquiry abuse reports</h1>
    <p className="lead">Review reported private conversations carefully. Dismiss false reports or block an unsafe conversation. These actions never verify prices or confirm bookings.</p>
    <Link to="/admin/customer-reviews" className="text-pine underline text-sm mt-5 block">Customer review moderation</Link>
    {!auth.signedIn||!auth.profile?.roles.includes('admin')?<p className="error-banner mt-7">An administrator account is required.</p>:<>
      <label className="field max-w-sm mt-8">Report queue<select value={state} onChange={e=>setState(e.target.value as typeof state)}><option value="open">Open</option><option value="dismissed">Dismissed</option><option value="actioned">Actioned</option></select></label>
      {error&&<p role="alert" className="error-banner mt-4">{error}</p>}{notice&&<p role="status" className="success-banner mt-4">{notice}</p>}
      {!rows.length&&<p className="info-banner mt-6">No reports in this queue.</p>}
      <div className="space-y-4 mt-6">{rows.map(report=><section key={report.id} className="form-panel space-y-3">
        <div className="flex justify-between gap-3 flex-wrap"><h2 className="text-lg font-bold">{report.subject}</h2><span className="text-sm">Thread: {report.thread_state}</span></div>
        <p className="text-sm text-ink/60">Listing: {report.listing_title} · Reason: {report.reason} · Report status: {report.state}</p>
        <p className="whitespace-pre-wrap break-words">{report.explanation}</p>
        <button type="button" className="text-pine underline text-sm" onClick={()=>void viewEvidence(report.id)}>Review private conversation evidence</button>
        {evidence[report.id]&&<div className="rounded-xl border border-ink/10 p-4 space-y-3"><p className="font-bold text-sm">Private conversation (admin-only)</p>
          {evidence[report.id].messages.map(m=><div key={m.id} className="rounded-lg bg-white border border-ink/10 p-3"><p className="text-xs font-bold">{m.sender} · {m.created_at&&new Date(m.created_at).toLocaleString()}</p><p className="text-sm whitespace-pre-wrap break-words mt-2">{m.body}</p></div>)}
          {evidence[report.id].has_more&&<p className="text-xs text-ink/60">Only the 50 latest messages are shown. Older messages must be requested through the paginated API.</p>}
        </div>}
        {report.state==='open'&&<form onSubmit={e=>{e.preventDefault();void decide(report.id,'dismissed')}} className="space-y-3">
          <label className="field">Decision reason<textarea required minLength={15} maxLength={600} rows={2} value={reason[report.id]||''} onChange={e=>setReason(old=>({...old,[report.id]:e.target.value}))}/></label>
          <div className="flex flex-wrap gap-3"><button type="submit" className="btn-secondary" disabled={busy===report.id}>Dismiss report</button><button type="button" className="btn-secondary" disabled={busy===report.id} onClick={()=>confirmBlock(report.id)}>Block conversation</button></div>
        </form>}
      </section>)}</div>
    </>}
  </main>
}
