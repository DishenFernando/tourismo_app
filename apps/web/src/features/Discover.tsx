import { ArrowRight, Compass, MapPin, Search, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getDestinations, type Destination } from '../lib/api'

const illustratedColors = ['one','two','three','four','five']
export function Discover() {
  const [params,setParams] = useSearchParams()
  const q = params.get('q')||''
  const category = params.get('category')||''
  const [term,setTerm] = useState(q)
  const [rows,setRows] = useState<Destination[]>([])
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState('')
  const [province,setProvince] = useState('all')
  useEffect(()=>{setTerm(q)},[q])
  useEffect(()=>{
    let alive = true
    setLoading(true);setError('')
    getDestinations(q).then(data=>{if(alive)setRows(data)}).catch(e=>{if(alive)setError(e instanceof Error?e.message:'Unable to load destinations')}).finally(()=>{if(alive)setLoading(false)})
    return ()=>{alive=false}
  },[q])
  const provinces = [...new Set(rows.map(d=>d.province))].sort()
  const visible = province==='all' ? rows : rows.filter(d=>d.province===province)
  const unsupported = category && category!=='destinations'
  return <main className="wrap pt-14 min-h-[65vh]">
    <span className="small-label">EXPLORE OUR ISLAND</span><h1 className="page-title">Where will curiosity take you?</h1>
    <p className="lead">Explore Sri Lankan destinations as a guest. Editorial content is in preparation and is not presented as independently verified yet.</p>
    <form className="mt-8 flex max-w-2xl overflow-hidden rounded-2xl border border-ink/10 bg-white shadow-card" onSubmit={e=>{e.preventDefault();setParams(term?{q:term}:{})}}>
      <Search className="text-pine ml-4 my-auto shrink-0"/><input className="w-full p-4 outline-none" aria-label="Search destinations" placeholder="Search city, town, or district" value={term} maxLength={100} onChange={e=>setTerm(e.target.value)}/>
      <button className="m-2 btn-primary" type="submit">Search</button>
    </form>
    {unsupported && <div className="info-banner mt-7"><ShieldAlert size={22} className="shrink-0"/><div><b>{category==='stays'?'Accommodation':category==='food'?'Restaurants':category==='transport'?'Transport':'Service-provider'} discovery is scheduled for upcoming phases.</b> We do not display fictional providers or false availability. Browse destinations or plan a trip in the meantime.</div></div>}
    {error && <p role="alert" className="mt-7 text-red-700">{error}. Check that the API and database are running.</p>}
    {loading && <p role="status" className="mt-7">Loading destinations…</p>}
    {!loading && !error && <>
      <div className="mt-10 flex flex-wrap gap-4 items-center justify-between"><h2 className="text-2xl font-bold">{q?'Search results':'Places to explore'}</h2>
        <div className="flex items-center gap-4"><label className="text-sm font-semibold text-ink/70">Province <select className="border rounded-lg bg-white p-2 ml-2" value={province} onChange={e=>setProvince(e.target.value)}><option value="all">All provinces</option>{provinces.map(p=><option key={p} value={p}>{p}</option>)}</select></label><span className="text-sm text-ink/60">{visible.length} destinations</span></div>
      </div>
      {visible.length ? <div className="grid gap-6 mt-5 sm:grid-cols-2 lg:grid-cols-3">{visible.map((d,i)=><Link to={`/destinations/${d.slug}`} key={d.slug} className="destination-card group">
        <div className={`destination-art destination-${illustratedColors[i%5]}`}>
          {d.photo ? <img src={d.photo.image_url} alt={d.photo.alt_text} loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover relative z-[1]" onError={e=>{e.currentTarget.style.display='none'}}/> : <><div className="destination-sun"/><div className="destination-ridge"/><div className="destination-ridge front"/></>}
          <span className="sample-chip">{d.is_sample?'Sample place':'Published guide'}</span>
        </div>
        <div className="p-5"><div className="text-xs text-pine font-bold tracking-widest uppercase flex items-center gap-1"><MapPin size={13}/>{d.district} District</div>
          <h3 className="text-2xl font-bold mt-2">{d.title}</h3>{d.photo && <div className="mt-2 text-xs text-ink/60">Photo: {d.photo.photographer} · {d.photo.license_name}</div>}<p className="text-sm text-ink/55 mt-2">{d.summary}</p><div className="text-pine mt-5 font-semibold text-sm flex gap-2 items-center">Explore place <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform"/></div></div>
      </Link>)}</div> : <div className="empty-state"><Compass size={35} className="text-pine"/><h3 className="text-xl font-bold mt-3">No matching place yet</h3><p className="text-ink/60">Try another town or district. We are expanding curated destination coverage.</p></div>}
    </>}
  </main>
}
