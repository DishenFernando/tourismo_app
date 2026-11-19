import { useCallback, useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { ArrowRight, CalendarDays, Check, CircleHelp, CloudUpload, Plus, Printer, RotateCcw, Trash2, Users } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { type Destination, type TripDraft, type TripPreview, type BudgetCategory, getDestinations, previewTrip, saveTrip } from '../lib/api'
import { DRAFT_KEY, PENDING_SAVE_KEY, calculateLocalPreview, clearDraft, emptyDraft, lkr, persistDraft, readDraft, toMinor } from '../lib/draft'

const categories: {key:BudgetCategory,label:string}[] = [
  {key:'accommodation',label:'Accommodation'},{key:'transport',label:'Transport'},
  {key:'food',label:'Food & dining'},{key:'entry_fees',label:'Entry fees'},
  {key:'guides',label:'Guides'},{key:'activities',label:'Activities'},
  {key:'misc',label:'Other'},{key:'contingency',label:'Contingency'}]

export function Planner() {
  const [params] = useSearchParams()
  const auth = useTourismoAuth()
  const [draft,setDraft] = useState<TripDraft>(()=>{
    const old = readDraft()
    const selected = params.get('destination')
    return selected ? {...old,destination_slug:selected}:old
  })
  const [destinations,setDestinations] = useState<Destination[]>([])
  const [preview,setPreview] = useState<TripPreview>(()=>calculateLocalPreview(readDraft()))
  const [status,setStatus] = useState('')
  const [newStop,setNewStop] = useState('')
  const [newDay,setNewDay] = useState(1)
  const [pending,setPending] = useState(()=>sessionStorage.getItem(PENDING_SAVE_KEY)==='yes')
  const [saving,setSaving] = useState(false)
  const [savedId,setSavedId] = useState('')
  const [formError,setFormError] = useState('')
  useEffect(()=>{getDestinations().then(setDestinations).catch(()=>setStatus('Could not load destinations. Check the API connection.'))},[])
  useEffect(()=>{persistDraft(draft);setPreview(calculateLocalPreview(draft))},[draft])
  const update = useCallback((key:keyof TripDraft, value:TripDraft[keyof TripDraft])=>{
    setDraft(old=>({...old, client_draft_id:savedId ? crypto.randomUUID() : old.client_draft_id, [key]:value}))
    if(savedId)setSavedId('')
  },[savedId])
  const updateBudget = (category:BudgetCategory, amount:string) => {
    const minor=toMinor(amount)
    const rest=draft.budget_items.filter(item=>item.category!==category)
    const item={category,description:'',minimum_minor:minor,expected_minor:minor,maximum_minor:minor,is_confirmed:false,source_label:'User-entered estimate'}
    update('budget_items',[...rest,item])
  }
  const addStop = () => {
    if(!newStop.trim())return
    if(draft.itinerary.length>=90){setFormError('Maximum 90 stops');return}
    update('itinerary',[...draft.itinerary,{day:newDay,title:newStop.trim(),note:''}])
    setNewStop('')
  }
  const doPreview=async()=>{
    setStatus('');setFormError('')
    try {setPreview(await previewTrip(draft));setStatus('Budget verified with the Tourismo API. Values are your inputs, not supplier quotations.')}
    catch(e){setFormError(e instanceof Error?e.message:'Unable to preview trip')}
  }
  const requestSave=()=>{
    setSavedId('');setStatus('')
    if(!auth.enabled){setStatus('Cloud saving requires real Google/email authentication. Add Clerk keys in your environment to enable it. Your browser draft remains available.');return}
    if(!auth.signedIn){sessionStorage.setItem(PENDING_SAVE_KEY,'yes');setPending(true);auth.login();return}
    sessionStorage.setItem(PENDING_SAVE_KEY,'yes');setPending(true)
  }
  const confirmSave=async()=>{
    if(!auth.signedIn){requestSave();return}
    setSaving(true);setFormError('')
    try {const token=await auth.token(); if(!token)throw new Error('Your session is unavailable. Please sign in again.')
      const row=await saveTrip(draft,token);setSavedId(row.id)
      sessionStorage.removeItem(PENDING_SAVE_KEY);setPending(false)
      setStatus('Trip saved privately to your account.')
    } catch(e){setFormError(e instanceof Error?e.message:'Could not save trip')}
    finally{setSaving(false)}
  }
  const reset=()=>{clearDraft();setDraft({...structuredClone(emptyDraft),client_draft_id:crypto.randomUUID()});setPending(false);setStatus('Draft cleared on this device.');setSavedId('')}
  return <main className="wrap pt-12">
    <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><span className="small-label">YOUR JOURNEY STARTS HERE</span>
      <h1 className="page-title">Plan the adventure, <em className="text-pine not-italic">your way.</em></h1><p className="lead">An editable guest planner with transparent, user-entered budget estimates.</p></div>
      <div className="flex gap-2 print:hidden flex-wrap"><button className="btn-secondary" onClick={()=>window.print()}><Printer size={17}/> Print</button>
        <button className="btn-secondary" onClick={reset}><RotateCcw size={17}/> Clear draft</button></div></div>
    <div className="mt-9 grid gap-7 lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)] items-start">
      <div className="space-y-6">
        <section className="form-panel"><div className="panel-heading"><Users className="text-pine"/><h2>Your trip details</h2></div>
          <div className="grid gap-4 sm:grid-cols-2"><label className="field"><span>Trip name</span><input value={draft.title} maxLength={160} onChange={e=>update('title',e.target.value)}/></label>
            <label className="field"><span>Destination</span><select value={draft.destination_slug} onChange={e=>update('destination_slug',e.target.value)}>{!destinations.some(d=>d.slug===draft.destination_slug) && <option value={draft.destination_slug}>{draft.destination_slug}</option>}{destinations.map(d=><option value={d.slug} key={d.slug}>{d.title}</option>)}</select></label>
            <label className="field"><span>Arrive</span><input type="date" value={draft.start_date||''} onChange={e=>update('start_date',e.target.value||null)}/></label>
            <label className="field"><span>Depart</span><input type="date" min={draft.start_date||undefined} value={draft.end_date||''} onChange={e=>update('end_date',e.target.value||null)}/></label>
            <label className="field"><span>Adults</span><input type="number" min={1} max={30} value={draft.adults} onChange={e=>update('adults',Math.max(1,Math.min(30,Number(e.target.value)||1)))}/></label>
            <label className="field"><span>Children</span><input type="number" min={0} max={20} value={draft.children_ages.length} onChange={e=>{
              const count=Math.max(0,Math.min(20,Number(e.target.value)||0));update('children_ages',Array.from({length:count},(_,i)=>draft.children_ages[i]??0))}}/></label>
          </div>
          {draft.children_ages.length>0 && <div className="mt-5"><p className="font-semibold mb-2">Children's ages <span className="text-ink/50 text-xs font-normal">(affects later accommodation searches)</span></p>
            <div className="flex flex-wrap gap-3">{draft.children_ages.map((age,i)=><label className="field max-w-[116px]" key={i}><span>Child {i+1}</span>
              <select value={age} onChange={e=>update('children_ages',draft.children_ages.map((a,j)=>i===j?Number(e.target.value):a))}>{Array.from({length:18},(_,y)=><option key={y} value={y}>{y} yrs</option>)}</select>
            </label>)}</div></div>}
          <p className="help mt-4">Traveler counts and ages are not sent to Tourismo until you choose to preview or save. No names or identifying information about children are collected here.</p>
        </section>
        <section className="form-panel"><div className="panel-heading"><CalendarDays className="text-pine"/><h2>Make it memorable</h2></div>
          <div className="flex flex-wrap gap-2"><label className="field w-[100px]"><span>Day</span><input type="number" min={1} max={31} value={newDay} onChange={e=>setNewDay(Math.min(31,Math.max(1,Number(e.target.value)||1)))}/></label>
          <label className="field flex-1 min-w-[180px]"><span>Place or activity</span><input placeholder="e.g. Morning walk" value={newStop} maxLength={160} onChange={e=>setNewStop(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();addStop()}}}/></label>
          <button className="btn-primary self-end h-[47px]" onClick={addStop}><Plus size={16}/> Add</button></div>
          {draft.itinerary.length? <ol className="mt-6 space-y-3">{draft.itinerary.map((s,i)=><li key={i} className="flex items-center justify-between gap-3 rounded-xl bg-[#f2f8f5] p-3"><span><b className="text-pine">Day {s.day}</b> · {s.title}</span>
            <button aria-label={`Remove ${s.title}`} className="text-red-600 p-2" onClick={()=>update('itinerary',draft.itinerary.filter((_,j)=>i!==j))}><Trash2 size={17}/></button></li>)}</ol>
          : <p className="help mt-5">Start with a destination and add activities. These are your own ideas, not verified opening hours or estimated routes.</p>}
        </section>
        <section className="form-panel"><div className="panel-heading"><span className="text-pine text-2xl font-bold">රු</span><h2>Your budget breakdown</h2></div>
          <p className="help mb-5">Enter your own assumptions in Sri Lankan rupees. A single amount means minimum = expected = maximum; richer ranges and sourced quotations arrive in a later budgeting phase.</p>
          <div className="grid gap-4 sm:grid-cols-2">{categories.map(c=><label key={c.key} className="field"><span>{c.label} (LKR)</span>
            <input type="number" min={0} max={100000000} step="0.01" placeholder="0" value={draft.budget_items.find(item=>item.category===c.key)?.expected_minor !== undefined ? draft.budget_items.find(item=>item.category===c.key)!.expected_minor/100 : ''}
              onChange={e=>updateBudget(c.key,e.target.value)}/></label>)}</div>
          <div className="grid sm:grid-cols-2 gap-4 mt-5"><label className="field"><span>Total budget limit (LKR)</span><input type="number" min={0} placeholder="Optional" value={draft.budget_limit_minor===null?'':draft.budget_limit_minor/100} onChange={e=>update('budget_limit_minor',e.target.value===''?null:toMinor(e.target.value))}/></label>
            <label className="flex items-center gap-3 mt-7"><input type="checkbox" checked={draft.budget_flexible} onChange={e=>update('budget_flexible',e.target.checked)} className="accent-pine w-5 h-5"/><span className="text-sm font-semibold">My budget is flexible</span></label></div>
          <button onClick={()=>void doPreview()} className="btn-secondary mt-5"><Check size={17}/> Validate my budget with API</button>
        </section>
      </div>
      <aside className="lg:sticky lg:top-6 space-y-5">
        <section className="summary-panel"><div className="text-white/80 text-sm font-semibold">YOUR ESTIMATED TRIP COST</div>
          <div className="text-white text-3xl sm:text-4xl font-extrabold mt-3">{lkr(preview.expected_minor)}</div>
          <div className="mt-4 border-t border-white/20 pt-4 space-y-2 text-sm text-white/80"><div className="flex justify-between"><span>Travelers</span><strong>{draft.adults+draft.children_ages.length}</strong></div>
            <div className="flex justify-between"><span>Per traveler</span><strong>{lkr(Math.round(preview.expected_minor/(draft.adults+draft.children_ages.length)))}</strong></div>
            <div className="flex justify-between"><span>Highest input estimate</span><strong>{lkr(preview.maximum_minor)}</strong></div>
            <div className="flex justify-between"><span>Budget limit</span><strong>{draft.budget_limit_minor===null?'Not set':lkr(draft.budget_limit_minor)}</strong></div></div>
          {draft.budget_limit_minor!==null && <div className={`mt-5 p-3 rounded-lg text-sm ${preview.exceeds_limit?'bg-amber-100 text-amber-950':'bg-white/15 text-white'}`}>
            {preview.exceeds_limit?'Maximum estimate exceeds your budget limit. Review assumptions.':'Your highest estimate is within your entered budget.'}</div>}
          <div className="mt-6 flex flex-col gap-2 print:hidden"><button className="cta-button justify-center" onClick={requestSave}><CloudUpload size={18}/> Save across devices <ArrowRight size={17}/></button>
            {pending && <div className="rounded-xl bg-white text-ink p-4 space-y-3"><b>Confirm cloud save</b><p className="text-sm text-ink/65">This creates a private copy of your browser draft in your account. It does not book anything.</p>
              <button disabled={saving||!auth.signedIn} className="btn-primary w-full justify-center" onClick={()=>void confirmSave()}>{saving?'Saving…':auth.signedIn?'Confirm save':'Sign in to confirm'}</button>
              <button className="text-sm text-pine underline" onClick={()=>{sessionStorage.removeItem(PENDING_SAVE_KEY);setPending(false)}}>Not now — keep my draft</button></div>}
          </div><div className="mt-4 text-xs text-white/75 leading-5">User-entered amounts only. No invented hotel or transport quotes, no tourist checkout.</div>
        </section>
        {savedId && <div role="status" className="success-banner"><Check size={20}/> <div>Cloud saved successfully. <Link to="/saved" className="font-bold underline">View saved trips</Link></div></div>}
        {status && <div role="status" className="info-banner text-sm"><CircleHelp className="shrink-0" size={18}/>{status}</div>}
        {formError && <div role="alert" className="error-banner">{formError}</div>}
        <div className="bg-white p-5 rounded-2xl border border-ink/10"><h3 className="font-bold">Guest privacy</h3><p className="text-sm text-ink/60 leading-6 mt-2">Drafts use temporary browser session storage ({DRAFT_KEY}). They can disappear when the session is cleared. Cloud saving is private and requires verified login.</p></div>
      </aside>
    </div>
  </main>
}
