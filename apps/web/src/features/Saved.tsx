import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bookmark, LockKeyhole, ArrowRight } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { type SavedTrip, savedTrips } from '../lib/api'
import { lkr } from '../lib/draft'

export function Saved() {
  const auth = useTourismoAuth()
  const [rows,setRows] = useState<SavedTrip[]>([])
  const [error,setError] = useState('')
  const [loading,setLoading] = useState(false)
  useEffect(()=>{if (!auth.signedIn)return;let active=true;auth.token().then(token=>{
    if(!token)throw new Error('Session is unavailable');setLoading(true);return savedTrips(token)
  }).then(data=>{if(active)setRows(data)}).catch(e=>{if(active)setError(e instanceof Error?e.message:'Unable to load trips')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[auth.signedIn,auth.token])
  return <main className="wrap pt-14 min-h-[65vh]"><span className="small-label">YOUR PERSONAL SPACE</span><h1 className="page-title">Saved adventures</h1>
    {!auth.enabled && <div className="empty-state"><LockKeyhole className="text-pine" size={38}/><h2 className="text-2xl font-bold mt-3">Cloud saving isn't configured yet</h2><p className="text-ink/60 mt-2">Configure Clerk Google/email login to activate cross-device saved trips. Your guest draft still works.</p><Link className="btn-primary mt-5" to="/plan">Go to trip planner <ArrowRight size={17}/></Link></div>}
    {auth.enabled&&!auth.signedIn&&<div className="empty-state"><LockKeyhole size={35} className="text-pine"/><h2 className="text-2xl font-bold mt-3">Your saved plans are private</h2><p className="text-ink/60 mt-2">Sign in with Google or verified email to view your own trips.</p><button className="btn-primary mt-5" onClick={auth.login}>Log in to see trips</button></div>}
    {auth.signedIn&&<div className="mt-9">{error&&<p role="alert" className="error-banner">{error}</p>}{loading&&<p>Loading saved trips…</p>}{!loading&&!error&&!rows.length&&<div className="empty-state"><Bookmark className="text-pine" size={38}/><h2 className="text-xl font-bold mt-3">No cloud trips yet</h2><p>Create a guest itinerary, then choose Save across devices.</p><Link className="btn-primary mt-4" to="/plan">Plan a trip</Link></div>}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{rows.map(row=><div key={row.id} className="feature-card"><span className="small-label">PRIVATE PLAN</span><h2 className="text-xl font-bold mt-3">{row.draft.title}</h2><p className="text-sm text-ink/60 mt-2">{row.draft.destination_slug} · {row.draft.adults+row.draft.children_ages.length} travelers</p><p className="mt-5 font-bold text-pine">{lkr(row.preview.expected_minor)} estimated</p><p className="text-xs text-ink/45 mt-3">Read-only cloud archive in this foundation release. Editing and sync enhancements are scheduled for Phase 6.</p></div>)}</div></div>}
  </main>
}
