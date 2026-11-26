import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bookmark, LockKeyhole, ArrowRight } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { type SavedTrip, savedTrips, deleteSavedTrip } from '../lib/api'
import { lkr } from '../lib/draft'
import { ItineraryMap } from './ItineraryMap'

export function Saved() {
  const auth = useTourismoAuth()
  const [rows,setRows] = useState<SavedTrip[]>([])
  const [openId,setOpenId] = useState('')
  const [error,setError] = useState('')
  const [loading,setLoading] = useState(false)
  useEffect(()=>{
    // Never display a prior session's private saved-trip snapshot while refreshing auth.
    setRows([]);setOpenId('');setError('')
    if (!auth.signedIn) {setLoading(false);return}
    let active=true
    setLoading(true)
    auth.token().then(token=>{
      if(!token)throw new Error('Session is unavailable')
      return savedTrips(token)
    }).then(data=>{if(active)setRows(data)})
      .catch(e=>{if(active)setError(e instanceof Error?e.message:'Unable to load trips')})
      .finally(()=>{if(active)setLoading(false)})
    return()=>{active=false}
  },[auth.signedIn,auth.token])
  const selected = rows.find(row=>row.id===openId)
  const remove=async(row:SavedTrip)=>{
    if(!window.confirm(`Permanently delete your saved trip “${row.draft.title}”? This cannot be undone.`)) return
    setError('')
    try {
      const token=await auth.token();if(!token)throw new Error('Sign in again to delete this trip.')
      await deleteSavedTrip(row.id,token)
      setRows(existing=>existing.filter(item=>item.id!==row.id))
      setOpenId(current=>current===row.id?'':current)
    } catch(e) {setError(e instanceof Error?e.message:'Unable to delete trip')}
  }
  return <main className="wrap pt-14 min-h-[65vh]"><span className="small-label">YOUR PERSONAL SPACE</span><h1 className="page-title">Saved adventures</h1>
    {!auth.enabled && <div className="empty-state"><LockKeyhole className="text-pine" size={38}/><h2 className="text-2xl font-bold mt-3">Cloud saving isn't configured yet</h2><p className="text-ink/60 mt-2">Configure Clerk Google/email login to activate cross-device saved trips. Your guest draft still works.</p><Link className="btn-primary mt-5" to="/plan">Go to trip planner <ArrowRight size={17}/></Link></div>}
    {auth.enabled&&!auth.signedIn&&<div className="empty-state"><LockKeyhole size={35} className="text-pine"/><h2 className="text-2xl font-bold mt-3">Your saved plans are private</h2><p className="text-ink/60 mt-2">Sign in with Google or verified email to view your own trips.</p><button className="btn-primary mt-5" onClick={auth.login}>Log in to see trips</button></div>}
    {auth.signedIn&&<div className="mt-9">{error&&<p role="alert" className="error-banner">{error}</p>}{loading&&<p>Loading saved trips…</p>}{!loading&&!error&&!rows.length&&<div className="empty-state"><Bookmark className="text-pine" size={38}/><h2 className="text-xl font-bold mt-3">No cloud trips yet</h2><p>Create a guest itinerary, then choose Save across devices.</p><Link className="btn-primary mt-4" to="/plan">Plan a trip</Link></div>}
      {!loading && !error && <><div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{rows.map(row=><div key={row.id} className="feature-card"><span className="small-label">PRIVATE PLAN</span><h2 className="text-xl font-bold mt-3">{row.draft.title}</h2><p className="text-sm text-ink/60 mt-2">{row.draft.destination_slug} · {row.draft.adults+row.draft.children_ages.length} travelers</p><p className="mt-5 font-bold text-pine">{lkr(row.preview.expected_minor)} estimated</p>
          <button type="button" className="btn-secondary mt-4" onClick={()=>setOpenId(current=>current===row.id?'':row.id)} aria-expanded={openId===row.id}>{openId===row.id?'Close':'View'} saved itinerary ({row.draft.itinerary.length} stops)</button>
          <div className="flex flex-wrap gap-2 mt-3"><Link className="btn-primary" to={`/plan?edit_trip=${encodeURIComponent(row.id)}`}>Edit this trip <ArrowRight size={16}/></Link><button className="btn-secondary text-red-700" type="button" onClick={()=>void remove(row)}>Delete</button></div>
          <p className="text-xs text-ink/45 mt-3">Version {row.version} · Private. Only you can update this trip; concurrent changes are checked.</p></div>)}</div>
        {selected && <section className="mt-7" aria-label="Selected saved itinerary">
          <div className="form-panel"><h2 className="text-xl font-bold">{selected.draft.title} — saved itinerary</h2>
            <ol className="list-decimal pl-5 mt-3 text-sm space-y-1">{selected.draft.itinerary.map((stop,i)=><li key={i}>Day {stop.day}: {stop.title}{stop.note && ` — ${stop.note}`}</li>)}</ol></div>
          <div className="form-panel mt-4"><h3 className="font-bold">Budget overview · LKR</h3>
            <p className="text-sm text-ink/65 mt-2">Expected group total: <b>{lkr(selected.preview.expected_minor)}</b> · Per traveler: <b>{lkr(selected.preview.per_traveler_expected_minor)}</b></p>
            <div className="grid sm:grid-cols-2 gap-4 mt-4">
              <div><h4 className="font-semibold">Daily expected expenses</h4>
                <ul className="text-sm mt-2 space-y-1">{selected.preview.by_day.map(day=><li key={day.day}>Day {day.day}: {lkr(day.expected_minor)}</li>)}</ul>
                {selected.preview.unassigned.expected_minor>0 && <p className="text-sm mt-2">Whole trip: {lkr(selected.preview.unassigned.expected_minor)}</p>}
              </div>
              <div><h4 className="font-semibold">Budget range</h4>
                <p className="text-sm mt-2">{lkr(selected.preview.minimum_minor)} – {lkr(selected.preview.maximum_minor)}</p>
                <p className="help mt-2">User-entered estimates; no verified provider quotes or bookings.</p>
              </div>
            </div>
          </div>
          <ItineraryMap stops={selected.draft.itinerary} day={0}/>
        </section>}
      </>}
    </div>}
  </main>
}
