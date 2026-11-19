import { ArrowLeft, ArrowRight, BadgeInfo, MapPin } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { request, type Destination } from '../lib/api'

export function DestinationPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [destination, setDestination] = useState<Destination | null>(null)
  const [error, setError] = useState('')
  useEffect(()=>{ let active=true; if(slug)request<Destination>(`/destinations/${slug}`).then(d=>{if(active)setDestination(d)}).catch(()=>{if(active)setError('Destination not found')});return()=>{active=false}},[slug])
  return <main className="wrap min-h-[60vh] pt-12">
    <Link to="/discover" className="inline-flex text-pine font-semibold gap-2 items-center"><ArrowLeft size={17}/> All destinations</Link>
    {error && <p className="mt-7" role="alert">{error}</p>}
    {!error && !destination && <p className="mt-7">Loading destination...</p>}
    {destination && <div className="mt-8 grid gap-12 lg:grid-cols-[1.1fr_.9fr] items-center">
      <div><span className="small-label"><MapPin size={15} className="inline"/> {destination.district}, {destination.province} Province</span>
        <h1 className="page-title mt-4">{destination.title}</h1><p className="lead">{destination.summary}</p>
        <div className="info-banner mt-7"><BadgeInfo size={24} className="shrink-0"/><span>This is a sample place record used to demonstrate Phase 1. Attraction guides, verified businesses, photos, maps and weather are not yet populated.</span></div>
        <button className="btn-primary mt-7" onClick={()=>navigate(`/plan?destination=${encodeURIComponent(destination.slug)}`)}>Plan a trip here <ArrowRight size={18}/></button>
      </div><div className="destination-art destination-one min-h-[330px] rounded-3xl relative"><div className="destination-sun"/><div className="destination-ridge"/><div className="destination-ridge front"/><span className="sample-chip">Illustrative artwork — not a real place photo</span></div>
    </div>}
  </main>
}
