import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { ItineraryMap } from './ItineraryMap'
import { BudgetEditor } from './BudgetEditor'
import { invalidBudgetItems } from '../lib/budget'
import { appendMappedStop, moveStopWithinDay } from '../lib/itinerary'
import { ArrowRight, CalendarDays, Check, CircleHelp, CloudUpload, Plus, Printer, RotateCcw, Trash2, Users } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { ApiError, type Destination, type TripDraft, type TripPreview, getDestinations, resolveItineraryPlaces, previewTrip, saveTrip, savedTrip, updateSavedTrip } from '../lib/api'
import { DRAFT_KEY, PENDING_SAVE_KEY, calculateLocalPreview, clearDraft, emptyDraft, lkr, persistDraft, readDraft, toMinor } from '../lib/draft'

export function Planner() {
  const [params,setParams] = useSearchParams()
  const auth = useTourismoAuth()
  const editTripId = params.get('edit_trip')
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
  const [mapDay,setMapDay] = useState(0)
  const [pending,setPending] = useState(()=>sessionStorage.getItem(PENDING_SAVE_KEY)==='yes')
  const [saving,setSaving] = useState(false)
  const [savedId,setSavedId] = useState('')
  const [formError,setFormError] = useState('')
  const [editTarget,setEditTarget] = useState<{id:string;version:number}|null>(null)
  const [loadingSaved,setLoadingSaved] = useState(false)
  const [conflict,setConflict] = useState(false)
  const [dirty,setDirty] = useState(false)
  const tokenRef=useRef(auth.token)
  tokenRef.current=auth.token
  useEffect(()=>{getDestinations().then(setDestinations).catch(()=>setStatus('Could not load destinations. Check the API connection.'))},[])
  // Cloud-owned saved trips are never copied into unauthenticated session drafts.
  useEffect(()=>{if(!editTarget && !editTripId)persistDraft(draft);setPreview(calculateLocalPreview(draft))},[draft,editTarget,editTripId])
  useEffect(()=>{
    if (!editTripId) return
    if (!auth.signedIn) {
      setEditTarget(null);setDraft(structuredClone(emptyDraft));setLoadingSaved(false)
      return
    }
    let active=true
    setLoadingSaved(true);setFormError('');setConflict(false)
    void tokenRef.current().then(token=>{
      if(!token) throw new Error('Sign in to edit this saved trip.')
      return savedTrip(editTripId,token)
    }).then(row=>{
      if(!active)return
      setDraft(row.draft);setEditTarget({id:row.id,version:row.version});setSavedId('');setDirty(false)
      setPending(false);sessionStorage.removeItem(PENDING_SAVE_KEY)
      setStatus(`Editing a private saved trip (version ${row.version}). Changes are not automatically saved.`)
    }).catch(e=>{if(active){setEditTarget(null);setFormError(e instanceof Error?e.message:'Unable to load saved trip')}})
      .finally(()=>{if(active)setLoadingSaved(false)})
    return()=>{active=false}
  },[editTripId,auth.signedIn])
  const addPlace = params.get('add_place')
  useEffect(() => {
    if (!addPlace || (editTripId && editTarget?.id!==editTripId)) return
    let active = true
    void resolveItineraryPlaces([addPlace]).then(places => {
      if (!active) return
      const place = places.find(p => p.id === addPlace)
      if (!place) {setFormError('This place is not publicly mapped now. Choose another place from the map.');return}
      setDraft(current => {
        const itinerary=appendMappedStop(current.itinerary,place,newDay)
        if (itinerary===current.itinerary) return current
        return {...current, itinerary}
      })
      setSavedId('');setDirty(true)
      setStatus(`Added ${place.title} to Day ${newDay}. Review the day and save your trip when ready.`)
    }).catch(() => {if(active)setFormError('Unable to confirm this place on the public map.')})
      .finally(() => {if(active)setParams(old => {const next=new URLSearchParams(old);next.delete('add_place');return next},{replace:true})})
    return () => {active=false}
  // The import uses the selected day when the URL is first opened.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addPlace,setParams,editTripId,editTarget?.id])

  const update = useCallback((key:keyof TripDraft, value:TripDraft[keyof TripDraft])=>{
    setDraft(old=>({...old,[key]:value}))
    setSavedId('')
    setConflict(false);setDirty(true)
  },[])
  const moveWithinDay = (index:number, direction:-1|1) =>
    update('itinerary',moveStopWithinDay(draft.itinerary,index,direction))
  const addStop = () => {
    if(!newStop.trim())return
    if(draft.itinerary.length>=90){setFormError('Maximum 90 stops');return}
    update('itinerary',[...draft.itinerary,{day:newDay,title:newStop.trim(),note:''}])
    setNewStop('')
  }
  const doPreview=async()=>{
    setStatus('');setFormError('')
    if(invalidBudgetItems(draft.budget_items).length){setFormError('Correct the minimum/expected/maximum budget ranges before validating.');return}
    try {setPreview(await previewTrip(draft));setStatus('Budget verified with the Tourismo API. Values are your inputs, not supplier quotations.')}
    catch(e){setFormError(e instanceof Error?e.message:'Unable to preview trip')}
  }
  const requestSave=()=>{
    setSavedId('');setStatus('')
    if(invalidBudgetItems(draft.budget_items).length){setFormError('Correct the budget ranges before saving.');return}
    if(!auth.enabled){setStatus('Cloud saving requires real Google/email authentication. Add Clerk keys in your environment to enable it. Your browser draft remains available.');return}
    if(!auth.signedIn){sessionStorage.setItem(PENDING_SAVE_KEY,'yes');setPending(true);auth.login();return}
    sessionStorage.setItem(PENDING_SAVE_KEY,'yes');setPending(true)
  }
  const confirmSave=async()=>{
    if(!auth.signedIn){requestSave();return}
    if(invalidBudgetItems(draft.budget_items).length){setFormError('Correct the budget ranges before saving.');return}
    setSaving(true);setFormError('')
    try {const token=await auth.token(); if(!token)throw new Error('Your session is unavailable. Please sign in again.')
      const snapshot=JSON.stringify(draft)
      const row=editTarget
        ? await updateSavedTrip(editTarget.id,editTarget.version,draft,token)
        : await saveTrip(draft,token)
      setEditTarget({id:row.id,version:row.version});setSavedId(row.id);setConflict(false)
      setDirty(false)
      setDraft(current=>JSON.stringify(current)===snapshot ? row.draft : current)
      sessionStorage.removeItem(PENDING_SAVE_KEY);setPending(false)
      setStatus(`Saved privately (version ${row.version}). Changes made after saving must be saved again.`)
    } catch(e){
      if(e instanceof ApiError && e.status===409) {
        setConflict(true);setFormError('This trip changed in another tab or device. Your edits remain here. Open the latest saved version separately or save your draft as a new trip.')
      } else setFormError(e instanceof Error?e.message:'Could not save trip')
    }
    finally{setSaving(false)}
  }
  const reset=()=>{
    clearDraft();setEditTarget(null);setConflict(false);setDirty(false)
    setParams(old=>{const next=new URLSearchParams(old);next.delete('edit_trip');next.delete('add_place');return next},{replace:true})
    setDraft({...structuredClone(emptyDraft),client_draft_id:crypto.randomUUID()});setPending(false)
    setStatus('Local draft cleared. Your cloud-saved trips were not deleted.');setSavedId('')
  }
  const makeCopy=()=>{
    setDraft(current=>({...current,client_draft_id:crypto.randomUUID()}))
    setEditTarget(null);setSavedId('');setConflict(false);setPending(false);setDirty(true)
    setParams(old=>{const next=new URLSearchParams(old);next.delete('edit_trip');return next},{replace:true})
    setStatus('Independent draft copy ready. Use Save across devices to create a new saved trip.')
  }
  const allowNavigate=(event:MouseEvent<HTMLAnchorElement>)=>{
    if(editTarget && dirty && !window.confirm('This trip has unsaved changes. Save them first, or continue and discard the unsaved changes.'))event.preventDefault()
  }
  if(editTripId && (!auth.signedIn || !editTarget || editTarget.id!==editTripId)) {
    return <main className="wrap pt-12 min-h-[55vh]">
      <h1 className="page-title">Edit saved trip</h1>
      <p className="help mt-5">{loadingSaved?'Loading your private trip…':auth.signedIn?(formError||'Loading your trip…'):'Sign in to load your own saved trip.'}</p>
      {!auth.signedIn && auth.enabled && <button className="btn-primary mt-4" onClick={auth.login}>Sign in</button>}
      <Link className="btn-secondary mt-4" to="/saved">Return to saved trips</Link>
    </main>
  }
  return <main className="wrap pt-12">
    <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between"><div><span className="small-label">YOUR JOURNEY STARTS HERE</span>
      <h1 className="page-title">Plan the adventure, <em className="text-pine not-italic">your way.</em></h1><p className="lead">An editable guest planner with transparent, user-entered budget estimates.</p></div>
      <div className="flex gap-2 print:hidden flex-wrap">{editTarget && <button className="btn-secondary" onClick={makeCopy}>Save as a new trip</button>}<button className="btn-secondary" onClick={()=>window.print()}><Printer size={17}/> Print</button>
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
          <div className="mt-4 flex flex-wrap gap-3 items-center text-sm">
            <Link className="text-pine font-semibold underline" onClick={allowNavigate} to={editTarget?`/map?edit_trip=${encodeURIComponent(editTarget.id)}`:"/map"}>Add places from the map</Link>
            <Link className="text-pine font-semibold underline" onClick={allowNavigate} to={editTarget?`/nearby?edit_trip=${encodeURIComponent(editTarget.id)}`:"/nearby"}>Find places nearby</Link>
            <label className="field ml-auto"><span>Map view</span><select value={mapDay} onChange={e=>setMapDay(Number(e.target.value))}>
              <option value={0}>All days</option>
              {Array.from(new Set(draft.itinerary.map(s=>s.day))).sort((a,b)=>a-b).map(day=><option key={day} value={day}>Day {day}</option>)}
            </select></label>
          </div>
          {draft.itinerary.length ? <ol className="mt-6 space-y-3">{draft.itinerary
            .map((stop,index)=>({stop,index})).sort((a,b)=>a.stop.day-b.stop.day)
            .map(({stop,index})=><li key={index} className="rounded-xl bg-[#f2f8f5] p-3 space-y-3">
              <div className="flex items-start gap-3 justify-between"><div className="min-w-0"><b className="text-pine">Day {stop.day}</b> · {stop.title}
                {stop.place_id && <p className="text-xs text-ink/55 mt-1">Linked public location — rechecked before map display</p>}</div>
                <div className="flex gap-1 shrink-0">
                  <button type="button" aria-label={`Move ${stop.title} earlier`} title="Move earlier on this day" className="btn-secondary px-2" onClick={()=>moveWithinDay(index,-1)}>↑</button>
                  <button type="button" aria-label={`Move ${stop.title} later`} title="Move later on this day" className="btn-secondary px-2" onClick={()=>moveWithinDay(index,1)}>↓</button>
                  <button type="button" aria-label={`Remove ${stop.title}`} className="text-red-600 p-2" onClick={()=>update('itinerary',draft.itinerary.filter((_,j)=>index!==j))}><Trash2 size={17}/></button>
                </div>
              </div>
              <div className="grid sm:grid-cols-[100px_minmax(0,1fr)] gap-3">
                <label className="field"><span>Day</span><input type="number" min={1} max={31} value={stop.day}
                  onChange={e=>update('itinerary',draft.itinerary.map((v,j)=>j===index?{...v,day:Math.min(31,Math.max(1,Number(e.target.value)||1))}:v))}/></label>
                <label className="field"><span>Notes (optional)</span><input maxLength={600} value={stop.note} placeholder="Time, meeting point, accessibility needs…"
                  onChange={e=>update('itinerary',draft.itinerary.map((v,j)=>j===index?{...v,note:e.target.value}:v))}/></label>
              </div>
            </li>)}</ol>
          : <p className="help mt-5">Add your own activities or select public locations from the map. Opening hours and road routes are not guaranteed.</p>}
          <ItineraryMap stops={draft.itinerary} day={mapDay}/>
        </section>
        <section className="form-panel"><div className="panel-heading"><span className="text-pine text-2xl font-bold">රු</span><h2>Your budget breakdown</h2></div>
          <BudgetEditor draft={draft} preview={preview} onChange={items=>update('budget_items',items)}/>
          <div className="grid sm:grid-cols-2 gap-4 mt-5"><label className="field"><span>Total budget limit (LKR)</span><input type="number" min={0} placeholder="Optional" value={draft.budget_limit_minor===null?'':draft.budget_limit_minor/100} onChange={e=>update('budget_limit_minor',e.target.value===''?null:toMinor(e.target.value))}/></label>
            <label className="flex items-center gap-3 mt-7"><input type="checkbox" checked={draft.budget_flexible} onChange={e=>update('budget_flexible',e.target.checked)} className="accent-pine w-5 h-5"/><span className="text-sm font-semibold">My budget is flexible</span></label></div>
          <button onClick={()=>void doPreview()} className="btn-secondary mt-5"><Check size={17}/> Validate my budget with API</button>
        </section>
      </div>
      <aside className="lg:sticky lg:top-6 space-y-5">
        <section className="summary-panel"><div className="text-white/80 text-sm font-semibold">YOUR ESTIMATED TRIP COST</div>
          <div className="text-white text-3xl sm:text-4xl font-extrabold mt-3">{lkr(preview.expected_minor)}</div>
          <div className="mt-4 border-t border-white/20 pt-4 space-y-2 text-sm text-white/80"><div className="flex justify-between"><span>Travelers</span><strong>{draft.adults+draft.children_ages.length}</strong></div>
            <div className="flex justify-between"><span>Per traveler</span><strong>{lkr(preview.per_traveler_expected_minor)}</strong></div>
            <div className="flex justify-between"><span>Highest input estimate</span><strong>{lkr(preview.maximum_minor)}</strong></div>
            <div className="flex justify-between"><span>Budget limit</span><strong>{draft.budget_limit_minor===null?'Not set':lkr(draft.budget_limit_minor)}</strong></div></div>
          {draft.budget_limit_minor!==null && <div className={`mt-5 p-3 rounded-lg text-sm ${preview.exceeds_limit?'bg-amber-100 text-amber-950':'bg-white/15 text-white'}`}>
            {preview.exceeds_limit?'Maximum estimate exceeds your budget limit. Review assumptions.':'Your highest estimate is within your entered budget.'}</div>}
          <div className="mt-6 flex flex-col gap-2 print:hidden"><button className="cta-button justify-center" onClick={requestSave} disabled={saving}><CloudUpload size={18}/> {editTarget?'Save changes to trip':'Save across devices'} <ArrowRight size={17}/></button>
            {pending && <div className="rounded-xl bg-white text-ink p-4 space-y-3"><b>Confirm cloud save</b><p className="text-sm text-ink/65">{editTarget?`Update your private trip from version ${editTarget.version}. If someone else updated it, this save will be rejected.`:'This creates a private copy of your browser draft in your account.'} No bookings or payments.</p>
              <button disabled={saving||!auth.signedIn} className="btn-primary w-full justify-center" onClick={()=>void confirmSave()}>{saving?'Saving…':auth.signedIn?'Confirm save':'Sign in to confirm'}</button>
              <button className="text-sm text-pine underline" onClick={()=>{sessionStorage.removeItem(PENDING_SAVE_KEY);setPending(false)}}>Not now — keep my draft</button></div>}
          </div><div className="mt-4 text-xs text-white/75 leading-5">User-entered amounts only. No invented hotel or transport quotes, no tourist checkout.</div>
        </section>
        {savedId && <div role="status" className="success-banner"><Check size={20}/> <div>Cloud saved successfully. <Link to="/saved" className="font-bold underline">View saved trips</Link></div></div>}
        {conflict && <div className="error-banner space-y-2"><p>Cloud version conflict. Your unsaved local edits are still on this page.</p><Link className="font-semibold underline block" to="/saved" target="_blank" rel="noopener noreferrer">Open latest saved trips in a new tab</Link><button className="btn-secondary" onClick={makeCopy}>Keep my changes as a separate trip</button></div>}
        {status && <div role="status" className="info-banner text-sm"><CircleHelp className="shrink-0" size={18}/>{status}</div>}
        {formError && <div role="alert" className="error-banner">{formError}</div>}
        <div className="bg-white p-5 rounded-2xl border border-ink/10"><h3 className="font-bold">Guest privacy</h3><p className="text-sm text-ink/60 leading-6 mt-2">Guest drafts use temporary browser session storage ({DRAFT_KEY}). Editing a private saved trip requires login and is not copied into the guest draft. Cloud writes require explicit confirmation.</p></div>
      </aside>
    </div>
  </main>
}
