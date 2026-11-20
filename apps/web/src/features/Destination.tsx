import { ArrowLeft, ArrowRight, BadgeInfo, BookOpen, Compass, ExternalLink, Landmark, Languages, MapPin, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { getDestinationGuide, getDestinationPois, getDestinationPhotos, request,
  type ContentLocale, type ContentSource, type Destination, type DestinationPhoto, type DestinationGuide, type PointOfInterest } from '../lib/api'

const pilotPlaces = [
  {slug:'kandy',name:'Kandy'}, {slug:'galle',name:'Galle'},
  {slug:'anuradhapura',name:'Anuradhapura'}, {slug:'sigiriya',name:'Sigiriya'},
  {slug:'nuwara-eliya',name:'Nuwara Eliya'},
]

const locales: {code:ContentLocale; label:string}[] = [
  {code:'en',label:'English'}, {code:'si',label:'සිංහල'}, {code:'ta',label:'தமிழ்'},
]

function Attribution({source, sample}:{source:ContentSource|null; sample:boolean}) {
  return <div className="flex flex-wrap gap-3 items-center text-xs text-ink/65 mt-4">
    {sample && <span className="rounded-full border border-amber-300 bg-amber-50 px-3 py-1.5 font-bold text-amber-800">Editorial sample · review pending</span>}
    {source?.url && <a href={source.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-pine underline underline-offset-2">Source: {source.name}<ExternalLink size={12}/></a>}
    {source?.verified_at && <span>Reviewed: {new Date(source.verified_at).toLocaleDateString()}</span>}
  </div>
}

export function DestinationPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const [params,setParams] = useSearchParams()
  const rawLocale = params.get('locale')
  const locale:ContentLocale = rawLocale==='si'||rawLocale==='ta'?rawLocale:'en'
  const [destination, setDestination] = useState<Destination|null>(null)
  const [guide, setGuide] = useState<DestinationGuide|null>(null)
  const [pois, setPois] = useState<PointOfInterest[]>([])
  const [photos, setPhotos] = useState<DestinationPhoto[]>([])
  const [selectedPhoto, setSelectedPhoto] = useState(0)
  const [poiCategory, setPoiCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [contentError, setContentError] = useState('')

  useEffect(()=>{
    let active = true
    setLoading(true); setError(''); setContentError(''); setGuide(null); setPois([]); setPhotos([]); setSelectedPhoto(0); setPoiCategory('all'); setDestination(null)
    if (!slug) {setLoading(false);setError('Destination not found');return}
    const safeSlug = encodeURIComponent(slug)
    request<Destination>(`/destinations/${safeSlug}?locale=${locale}`)
      .then(async d=>{
        if (!active) return
        setDestination(d)
        const results=await Promise.allSettled([getDestinationGuide(slug,locale),getDestinationPois(slug,locale),getDestinationPhotos(slug)])
        if (!active) return
        if (results[0].status==='fulfilled') setGuide(results[0].value)
        else if (!(results[0].reason instanceof Error && results[0].reason.message.includes('404'))) setContentError('Some editorial content could not be loaded.')
        if (results[1].status==='fulfilled') setPois(results[1].value)
        else setContentError('Some editorial content could not be loaded.')
        if (results[2].status==='fulfilled') setPhotos(results[2].value)
        else setContentError('Some photographs could not be loaded.')
      })
      .catch(()=>{if(active)setError('Destination not found or unavailable')})
      .finally(()=>{if(active)setLoading(false)})
    return()=>{active=false}
  },[slug,locale])

  const categories = Array.from(new Set(pois.map(p=>p.category))).sort()
  const visiblePois = poiCategory==='all' ? pois : pois.filter(p=>p.category===poiCategory)

  return <main className="wrap min-h-[60vh] pb-20 pt-12">
    <Link to="/discover" className="inline-flex text-pine font-semibold gap-2 items-center"><ArrowLeft size={17}/> All destinations</Link>
    {error && <p className="error-banner mt-7" role="alert">{error}</p>}
    {loading && <p className="mt-7" role="status">Loading destination…</p>}
    {!loading && destination && <>
      <div className="mt-7 grid gap-9 lg:grid-cols-[1.2fr_.8fr] items-center">
        <div>
          <span className="small-label"><MapPin size={15} className="inline"/> {destination.district} District · {destination.province} Province</span>
          <h1 className="page-title mt-3">{destination.title}</h1>
          <p className="lead">{guide?.overview || destination.summary}</p>
          <div className="flex flex-wrap gap-3 items-center mt-6">
            <button className="btn-primary" onClick={()=>navigate(`/plan?destination=${encodeURIComponent(destination.slug)}`)}>Plan a trip here <ArrowRight size={18}/></button>
            <Link className="btn-secondary" to={`/listings?destination=${encodeURIComponent(destination.slug)}`}>Find services in this region <MapPin size={17}/></Link>
            <label className="flex items-center gap-2 text-sm font-semibold text-ink/70"><Languages size={17}/><span>Content language</span>
              <select className="rounded-lg border border-ink/15 bg-white px-3 py-2" aria-label="Guide language" value={locale}
                onChange={e=>setParams(e.target.value==='en'?{}:{locale:e.target.value})}>
                {locales.map(l=><option key={l.code} value={l.code}>{l.label}</option>)}
              </select>
            </label>
          </div>
          {guide?.fallback_used && <p className="info-banner mt-5 text-sm"><Languages size={20} className="shrink-0"/> The {locale==='si'?'Sinhala':'Tamil'} guide is not yet reviewed. Showing English source content instead.</p>}
          <Attribution source={guide?.source || null} sample={destination.is_sample || guide?.content_status==='sample'}/>
        </div>
        <div>
          <div className="destination-art destination-one min-h-[290px] rounded-3xl relative overflow-hidden">
            {(photos[selectedPhoto] || destination.photo) ? <>
              <img src={(photos[selectedPhoto] || destination.photo)!.image_url} loading="eager" alt={(photos[selectedPhoto] || destination.photo)!.alt_text} referrerPolicy="no-referrer" className="relative z-[1] w-full h-full object-cover" onError={e=>{e.currentTarget.style.display='none'}}/>
              <div className="absolute bottom-0 left-0 right-0 z-[2] bg-[#062735c9] p-3 text-white text-xs">
                {(photos[selectedPhoto] || destination.photo)!.media_kind==='ai_illustration'?<span><b>Illustrative AI-generated image</b> · Generated with {(photos[selectedPhoto] || destination.photo)!.photographer} · Not a documentary photograph of this location</span>:(photos[selectedPhoto] || destination.photo)!.media_kind==='owned_photo'?<span>Photo provided by {(photos[selectedPhoto] || destination.photo)!.photographer} · Rights asserted by uploader (not independently verified)</span>:<span>Photo by {(photos[selectedPhoto] || destination.photo)!.photographer} · <a target="_blank" rel="noopener noreferrer" className="underline" href={(photos[selectedPhoto] || destination.photo)!.file_page_url}>Wikimedia Commons</a> · <a target="_blank" rel="noopener noreferrer" className="underline" href={(photos[selectedPhoto] || destination.photo)!.license_url}>{(photos[selectedPhoto] || destination.photo)!.license_name}</a></span>}
              </div>
            </> : <><div className="destination-sun"/><div className="destination-ridge"/><div className="destination-ridge front"/><span className="sample-chip">Illustration · photograph awaiting review</span></>}
          </div>
          {photos.length > 1 && <div className="mt-3 flex gap-2 flex-wrap" aria-label="Destination photo gallery">{photos.map((photo,index)=><button key={photo.file_page_url} type="button" onClick={()=>setSelectedPhoto(index)} aria-label={`Show photograph ${index+1}: ${photo.alt_text}`} aria-pressed={selectedPhoto===index} className={`h-16 w-20 overflow-hidden rounded-lg border-2 ${selectedPhoto===index?'border-pine':'border-transparent'}`}><img src={photo.image_url} alt="" loading="lazy" referrerPolicy="no-referrer" className="w-full h-full object-cover"/></button>)}</div>}
          {photos.length > 0 && <p className="mt-2 text-xs text-ink/55">{photos.length} images · Credits and AI-image labels are shown for each item. Not all images are documentary photographs.</p>}
        </div>
      </div>

      {contentError && <p role="alert" className="error-banner mt-7">{contentError}</p>}
      <div className="mt-12 grid gap-7 lg:grid-cols-3">
        <section className="form-panel lg:col-span-2" aria-labelledby="highlights-heading">
          <div className="panel-heading"><Landmark size={25} className="text-pine"/><h2 id="highlights-heading">What makes this place special</h2></div>
          {guide?.highlights.length ? <div className="grid gap-3 sm:grid-cols-2">{guide.highlights.map(h=><div key={h} className="flex gap-3 rounded-xl bg-[#f3f8f4] p-4 text-sm font-semibold"><ShieldCheck size={19} className="text-pine shrink-0"/>{h}</div>)}</div>
            : <p className="help">This destination's editorial overview is in preparation. We don't publish unverified recommendations.</p>}
        </section>
        <section className="form-panel" aria-labelledby="tips-heading">
          <div className="panel-heading"><Compass size={24} className="text-pine"/><h2 id="tips-heading">Local tips</h2></div>
          {guide?.local_tips.length ? <ul className="space-y-2 text-sm text-ink/75 list-disc pl-5">{guide.local_tips.map(t=><li key={t}>{t}</li>)}</ul>
            : <p className="help">Seasonal tips, access guidance and verified local recommendations are being prepared.</p>}
        </section>
      </div>

      <section className="mt-12" aria-labelledby="places-heading">
        <div className="flex items-center justify-between gap-4 flex-wrap"><div>
          <span className="small-label">DISCOVER THE AREA</span>
          <h2 id="places-heading" className="section-title">Attractions & places of interest</h2>
        </div><span className="text-sm text-ink/55">{pois.length} referenced {pois.length===1?'place':'places'}</span></div>
        {categories.length > 1 && <div className="mt-4 flex flex-wrap items-center gap-2" aria-label="Filter attractions by type">
          <button type="button" onClick={()=>setPoiCategory('all')} aria-pressed={poiCategory==='all'} className={`rounded-full border px-4 py-2 text-sm font-semibold ${poiCategory==='all'?'bg-pine text-white':'bg-white text-pine'}`}>All ({pois.length})</button>
          {categories.map(c=><button type="button" key={c} onClick={()=>setPoiCategory(c)} aria-pressed={poiCategory===c} className={`rounded-full border px-4 py-2 text-sm font-semibold capitalize ${poiCategory===c?'bg-pine text-white':'bg-white text-pine'}`}>{c.replaceAll('_',' ')} ({pois.filter(p=>p.category===c).length})</button>)}
        </div>}
        {pois.length ? <div className="grid gap-5 mt-6 md:grid-cols-2 lg:grid-cols-3">{visiblePois.map(p=><article key={p.slug} className="form-panel">
          <div className="flex items-center gap-2 text-xs tracking-wide uppercase font-bold text-pine"><BookOpen size={17}/>{p.category.replaceAll('_',' ')}</div>
          <h3 className="text-xl font-bold mt-3">{p.title}</h3>
          <p className="text-sm text-ink/70 leading-relaxed mt-3">{p.description}</p>
          {p.local_tips && <div className="mt-4 rounded-xl bg-[#f3f8f4] p-3 text-sm text-ink/75"><strong className="block text-pine mb-1">Good to know</strong>{p.local_tips}</div>}
          {p.fallback_used && <p className="text-xs text-amber-700 mt-3">English translation shown; requested language pending</p>}
          {p.latitude != null && p.longitude != null && <div className="mt-3"><a className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold text-pine" href={`https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}#map=15/${p.latitude}/${p.longitude}`} target="_blank" rel="noopener noreferrer"><MapPin size={16}/> View reference point on map <ExternalLink size={14}/></a><p className="mt-1 text-xs text-ink/55">Approximate heritage-site reference; not a verified entrance or route.</p></div>}
          <Attribution source={p.source} sample={p.content_status==='sample'}/>
        </article>)}</div> : <div className="empty-state"><MapPin size={35} className="text-pine"/>
          <h3 className="text-lg font-bold">Curated attractions coming soon</h3>
          <p>We have not yet prepared source-backed attractions for this destination. No fictional listings or opening times are shown.</p>
        </div>}
      </section>
      <section className="mt-12 border-t border-ink/10 pt-8" aria-label="Explore our five pilot destination guides">
        <span className="small-label">TOURISMO PILOT GUIDES</span>
        <h2 className="section-title mt-2">Keep exploring Sri Lanka</h2>
        <p className="text-sm text-ink/65 mt-2">Five destinations with additional source-referenced visitor guidance. The content remains editorial sample material until reviewed and approved.</p>
        <div className="mt-5 flex flex-wrap gap-2">{pilotPlaces.filter(p=>p.slug!==slug).map(p=><Link to={`/destinations/${p.slug}`} key={p.slug} className="inline-flex items-center gap-2 rounded-xl border border-ink/15 bg-white px-4 py-3 text-sm font-semibold text-pine hover:bg-[#f3f8f4]">{p.name}<ArrowRight size={15}/></Link>)}</div>
      </section>
      <div className="info-banner mt-10"><BadgeInfo size={22} className="shrink-0"/><p><strong>Content transparency:</strong> Reference links identify the underlying information source, not an official Tourismo endorsement. Sample entries still need human editorial review. Entrance fees, opening times, transport, weather and availability must be confirmed with the relevant provider before travel.</p></div>
    </>}
  </main>
}
