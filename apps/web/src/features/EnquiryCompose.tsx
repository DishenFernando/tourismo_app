import {useState, type FormEvent} from 'react'
import {Link, useNavigate} from 'react-router-dom'
import {MessageSquareText} from 'lucide-react'
import {useTourismoAuth} from '../app/Auth'
import {createEnquiry} from '../lib/api'

export function EnquiryCompose({slug}:{slug:string}){
  const auth=useTourismoAuth()
  const navigate=useNavigate()
  const [subject,setSubject]=useState('')
  const [message,setMessage]=useState('')
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  async function submit(e:FormEvent){
    e.preventDefault();setError('');setBusy(true)
    try{
      const token=await auth.token()
      if(!token)throw new Error('Sign in before sending an enquiry')
      const result=await createEnquiry(slug,subject.trim(),message.trim(),token)
      navigate(`/enquiries?id=${encodeURIComponent(result.enquiry.id)}`)
    }catch(e){setError(e instanceof Error?e.message:'Unable to send enquiry')}
    finally{setBusy(false)}
  }
  return <section className="form-panel mt-8 space-y-3" aria-labelledby="enquiry-compose-title">
    <div className="flex items-center gap-2"><MessageSquareText size={20} className="text-pine"/><h2 id="enquiry-compose-title" className="text-xl font-bold">Ask the provider</h2></div>
    <p className="text-sm text-ink/70">Request availability details or a quotation in a private Tourismo conversation. The provider may respond, but this does <strong>not</strong> reserve a room, vehicle, guide, or service. Quotes are provider statements, not Tourismo guarantees.</p>
    {!auth.signedIn ? <button type="button" className="btn-primary" onClick={auth.login}>Sign in to send an enquiry</button> :
      !auth.profile?.profile_completed ? <p className="info-banner">Complete your <Link to="/account" className="font-bold underline">traveler profile</Link> before sending an enquiry.</p> :
        <form onSubmit={e=>void submit(e)} className="space-y-3">
          <label className="field">Subject<input required minLength={8} maxLength={140} value={subject} onChange={e=>setSubject(e.target.value)} placeholder="Availability for 2 adults in December"/></label>
          <label className="field">Your enquiry<textarea required rows={5} minLength={20} maxLength={2000} value={message} onChange={e=>setMessage(e.target.value)} placeholder="Share dates, group size and what information you need. Avoid passports, payment details or sensitive information."/></label>
          <p className="text-xs text-ink/60">Messages are visible to you, eligible business managers and authorized Tourismo safety reviewers when a report is investigated. Do not share payment information. One active conversation per service; daily limits apply.</p>
          {error&&<p className="error-banner" role="alert">{error}</p>}
          <div className="flex flex-wrap items-center gap-3"><button className="btn-primary" disabled={busy} type="submit">{busy?'Sending…':'Send private enquiry'}</button><Link className="text-pine text-sm underline" to="/enquiries">My enquiries</Link></div>
        </form>}
  </section>
}
