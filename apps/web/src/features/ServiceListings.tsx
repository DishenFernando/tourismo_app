import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams, useParams } from 'react-router-dom'
import { ArrowRight, Building2, Compass, LocateFixed, Mail, MapPin, Phone, Search, ShieldCheck } from 'lucide-react'
import { publicListing, publicListings, demoCatalogStatus, demoListing, demoListings, familySuitability, getDestinations, type Destination, type FamilyFit, type ServiceListing } from '../lib/api'

const labels:Record<string,string> = {
  accommodation:'Stays',restaurant:'Restaurants',guide:'Local guides',
  transport:'Transport',tour_operator:'Tour operators',activity:'Experiences'
}
const categories=['accommodation','restaurant','guide','transport','tour_operator','activity']
const money=(minor:unknown)=>typeof minor==='number'?`LKR ${(minor/100).toLocaleString('en-LK',{maximumFractionDigits:2})} (indicative)`:'Ask provider for a quote'

export function ServiceListings({demo=false}:{demo?:boolean}) {
  const [params,setParams]=useSearchParams()
  const category=params.get('category')||''
  const q=params.get('q')||''
  const district=params.get('district')||''
  const province=params.get('province')||''
  const destination=params.get('destination')||''
  const [search,setSearch]=useState(q)
  const [adultsInput,setAdultsInput]=useState(params.get('adults')||'')
  const [agesInput,setAgesInput]=useState(params.getAll('child_ages').join(', '))
  const [latInput,setLatInput]=useState(params.get('near_lat')||'')
  const [lonInput,setLonInput]=useState(params.get('near_lon')||'')
  const [radiusInput,setRadiusInput]=useState(params.get('radius_km')||'20')
  const [sortInput,setSortInput]=useState(params.get('sort')||'recent')
  const [formError,setFormError]=useState('')
  const [locationMessage,setLocationMessage]=useState('')
  const [destinations,setDestinations]=useState<Destination[]>([])
  const [items,setItems]=useState<ServiceListing[]>([])
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [demoAvailable,setDemoAvailable]=useState(false)
  const hasCenter=params.has('near_lat')&&params.has('near_lon')
  const offset=Math.max(0,Number(params.get('offset')||0)||0)
  useEffect(()=>{setSearch(q)},[q])
  useEffect(()=>{
    if(!demo)demoCatalogStatus().then(v=>setDemoAvailable(v.enabled)).catch(()=>setDemoAvailable(false))
    getDestinations().then(setDestinations).catch(()=>setDestinations([]))
  },[demo])
  useEffect(()=>{
    let mounted=true;setLoading(true);setError('')
    const options={category,district,q,province,destination,
      ...(params.has('adults')?{adults:Number(params.get('adults'))}:{}),
      child_ages:params.getAll('child_ages').map(Number)}
    const load=demo?demoListings(options):publicListings({
      ...options,
      ...(hasCenter?{
        near_lat:Number(params.get('near_lat')),near_lon:Number(params.get('near_lon')),
        ...(params.has('radius_km')?{radius_km:Number(params.get('radius_km'))}:{}),
        sort:params.get('sort')==='distance'?'distance' as const:'recent' as const
      }:{}),
      limit:24,offset
    })
    load.then(list=>{if(mounted)setItems(list)})
      .catch(e=>{if(mounted)setError(e instanceof Error?e.message:'Unable to load listings')})
      .finally(()=>{if(mounted)setLoading(false)})
    return()=>{mounted=false}
  },[category,district,q,province,destination,params,demo,hasCenter,offset])
  function changeField(key:string,value:string){
    const next=new URLSearchParams(params);next.delete('offset')
    if(value)next.set(key,value);else next.delete(key)
    if(key==='category'&&value!=='accommodation'){
      next.delete('adults');next.delete('child_ages');setAdultsInput('');setAgesInput('')
    }
    setParams(next)
  }
  function submitFilters(e:FormEvent){
    e.preventDefault();setFormError('')
    const next=new URLSearchParams(params);next.delete('offset')
    if(search.trim())next.set('q',search.trim());else next.delete('q')
    next.delete('adults');next.delete('child_ages')
    if(category==='accommodation'&&adultsInput){
      const adults=Number(adultsInput)
      if(!Number.isInteger(adults)||adults<1||adults>30){setFormError('Adults must be between 1 and 30.');return}
      const ages=agesInput.trim()?agesInput.split(',').map(v=>Number(v.trim())):[]
      if(ages.length>30||ages.some(a=>!Number.isInteger(a)||a<0||a>17)){
        setFormError('Use comma-separated child ages from 0 to 17 (up to 30).');return
      }
      next.set('adults',String(adults));ages.forEach(a=>next.append('child_ages',String(a)))
    }
    next.delete('near_lat');next.delete('near_lon');next.delete('radius_km');next.delete('sort')
    if(!demo&&(latInput.trim()||lonInput.trim())){
      const lat=Number(latInput),lon=Number(lonInput),radius=Number(radiusInput)
      if(!latInput.trim()||!lonInput.trim()||!Number.isFinite(lat)||!Number.isFinite(lon)||lat<-90||lat>90||lon<-180||lon>180){
        setFormError('Provide valid latitude and longitude together.');return
      }
      if(!Number.isFinite(radius)||radius<=0||radius>100){setFormError('Radius must be greater than 0 and up to 100 km.');return}
      next.set('near_lat',String(lat));next.set('near_lon',String(lon))
      next.set('radius_km',String(radius));next.set('sort',sortInput==='distance'?'distance':'recent')
    }
    setParams(next)
  }
  function useMyLocation(){
    if(!navigator.geolocation){setLocationMessage('This browser does not support location access.');return}
    setLocationMessage('Requesting location permission…')
    navigator.geolocation.getCurrentPosition(
      pos=>{setLatInput(pos.coords.latitude.toFixed(6));setLonInput(pos.coords.longitude.toFixed(6));setLocationMessage('Location added to form. Press Search to use it.')},
      ()=>setLocationMessage('Location was unavailable or permission was denied. You can enter coordinates manually.'),
      {enableHighAccuracy:false,timeout:10000,maximumAge:0}
    )
  }
  return <main className="wrap pt-14 pb-20 min-h-[70vh]">
    <span className="small-label">{demo?'DEVELOPMENT PREVIEW · FICTIONAL DATA':'LOCAL TOURISM PROVIDERS'}</span>
    <h1 className="page-title">{demo?'Tourismo sample business catalog':'Find tourism services for your trip'}</h1>
    {demo?<div className="error-banner mt-5" role="note"><strong>DEMO DATA ONLY.</strong> These businesses, people, locations, prices and offers are invented examples. They have not been verified, are not published offers, and cannot be booked or contacted. <Link to="/listings" className="underline font-bold">View the real verified directory</Link>.</div>:<p className="lead">Search approved provider listings by destination, family needs, or map radius. Location distances are straight-line estimates, not travel times. Confirm all prices and availability directly with providers.</p>}
    {!demo&&demoAvailable&&<div className="info-banner mt-5">Testing Tourismo? <Link className="underline font-bold" to="/demo/listings">Explore clearly marked fictional sample businesses</Link> separately from approved public providers.</div>}
    <form className="form-panel mt-8 space-y-5" onSubmit={submitFilters}>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 items-end">
        <label className="field">Search services<input value={search} maxLength={100} placeholder="Provider or location" onChange={e=>setSearch(e.target.value)}/></label>
        <label className="field">Service category<select value={category} onChange={e=>changeField('category',e.target.value)}><option value="">All categories</option>{categories.map(c=><option key={c} value={c}>{labels[c]}</option>)}</select></label>
        <label className="field">Destination<select value={destination} onChange={e=>changeField('destination',e.target.value)}><option value="">Any destination</option>{destinations.map(d=><option key={d.slug} value={d.slug}>{d.title} · {d.district}</option>)}</select></label>
        <label className="field">Province<select value={province} onChange={e=>changeField('province',e.target.value)}><option value="">All provinces</option>{['Central','Eastern','North Central','Northern','North Western','Sabaragamuwa','Southern','Uva','Western'].map(p=><option value={p} key={p}>{p}</option>)}</select></label>
        <label className="field">District<input value={district} maxLength={120} placeholder="e.g. Kandy" onChange={e=>changeField('district',e.target.value)}/></label>
      </div>
      {category==='accommodation'&&<fieldset className="border-t border-ink/10 pt-4"><legend className="font-bold text-sm">Family suitability · optional</legend><div className="grid sm:grid-cols-2 gap-3 mt-2"><label className="field">Adults<input type="number" min="1" max="30" value={adultsInput} onChange={e=>setAdultsInput(e.target.value)} placeholder="e.g. 2"/></label><label className="field">Children's ages<input value={agesInput} onChange={e=>setAgesInput(e.target.value)} placeholder="e.g. 5, 12" disabled={!adultsInput}/></label></div><p className="text-xs text-ink/60 mt-2">Filters on recorded room capacity and child-age rules; no availability guarantee.</p></fieldset>}
      {!demo&&<>
        <fieldset className="border-t border-ink/10 pt-4"><legend className="font-bold text-sm">Near a location · optional radius search</legend><div className="grid sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_1fr_auto] gap-3 items-end mt-2">
          <label className="field">Latitude<input type="number" step="any" min="-90" max="90" value={latInput} onChange={e=>setLatInput(e.target.value)} placeholder="6.9271"/></label>
          <label className="field">Longitude<input type="number" step="any" min="-180" max="180" value={lonInput} onChange={e=>setLonInput(e.target.value)} placeholder="79.8612"/></label>
          <label className="field">Radius (km)<input type="number" step="any" min="0.1" max="100" value={radiusInput} onChange={e=>setRadiusInput(e.target.value)}/></label>
          <label className="field">Sort<select value={sortInput} onChange={e=>setSortInput(e.target.value)}><option value="recent">Recently published</option><option value="distance">Closest first</option></select></label>
          <button className="btn-secondary justify-center" type="button" onClick={useMyLocation}><LocateFixed size={16}/> Use my location</button>
        </div><p className="text-xs text-ink/60 mt-2">Only listings with provider-supplied, sourced coordinates can appear in radius results. Location is sent only when you press Search.</p>{locationMessage&&<p role="status" className="text-sm mt-2">{locationMessage}</p>}
        </fieldset>
      </>}
      {formError&&<p role="alert" className="error-banner">{formError}</p>}
      <div className="flex flex-wrap items-center gap-3"><button type="submit" className="btn-primary justify-center"><Search size={17}/> Search services</button><button type="button" className="btn-secondary" onClick={()=>{setSearch('');setAdultsInput('');setAgesInput('');setLatInput('');setLonInput('');setRadiusInput('20');setSortInput('recent');setFormError('');setParams(new URLSearchParams())}}>Clear filters</button></div>
    </form>
    {hasCenter&&!demo&&<p className="mt-4 text-sm text-ink/60">Showing listings with sourced coordinates within {params.get('radius_km')||'any'} km of the selected center · distance is straight-line, not a route.</p>}
    {destination&&<p className="mt-2 text-sm text-ink/60">Destination matching is regional (district or declared provider service area), not confirmed proximity to an attraction.</p>}
    {loading&&<p role="status" className="mt-10">{demo?'Loading fictional example services…':'Searching verified local providers…'}</p>}
    {error&&<p role="alert" className="error-banner mt-7">{error}</p>}
    {!loading&&!error&&<><div className="flex items-center justify-between mt-9"><h2 className="text-2xl font-bold">Available listings</h2><span className="text-ink/60 text-sm">{items.length} on this page</span></div>
      {items.length===0?<section className="empty-state mt-6"><Building2 size={36} className="text-pine"/><h3 className="text-xl font-bold mt-3">No matching services yet</h3><p className="mt-2 text-ink/60">{demo?'No sample records found. Run the development demo SQL seed first.':'Try a larger region or remove family/radius filters. Only currently approved providers can appear here.'}</p><Link to="/discover" className="btn-secondary mt-5">Explore destinations <ArrowRight size={17}/></Link></section>:
        <div className="grid gap-6 mt-6 sm:grid-cols-2 xl:grid-cols-3">{items.map(item=><Link key={item.id} to={`${demo?'/demo':''}/listings/${item.slug}`} className="destination-card group overflow-hidden">
          <div className="relative h-52 bg-[#dfebe5] flex items-center justify-center">{item.photos[0]?<img src={item.photos[0].image_url} alt={item.photos[0].alt_text} loading="lazy" referrerPolicy="no-referrer" className="h-full w-full object-cover"/>:<Compass className="text-pine/40" size={60}/>}<span className="sample-chip">{labels[item.category]}</span></div>
          <div className="p-5"><p className="text-xs font-bold text-pine flex items-center gap-1"><MapPin size={13}/>{item.district}, {item.province}</p><h3 className="text-xl font-bold mt-2">{item.title}</h3>{demo&&<span className="text-xs font-extrabold text-rose-700">FICTIONAL · NOT VERIFIED</span>}{typeof item.distance_km==='number'&&<p className="text-xs font-bold text-pine mt-1">≈ {item.distance_km.toFixed(1)} km straight-line</p>}<p className="mt-2 text-sm text-ink/70">{item.summary}</p><p className="mt-4 text-xs text-ink/60">{item.photos[0]?`Photo: ${item.photos[0].credit} · ${item.photos[0].license_name}`:'No verified photo yet'}</p><p className="mt-3 text-sm text-pine font-bold">{demo?'View sample details':'View provider'} <ArrowRight size={15} className="inline"/></p></div>
        </Link>)}</div>}
      {!demo&&<div className="flex gap-3 mt-8">{offset>0&&<button type="button" className="btn-secondary" onClick={()=>{const next=new URLSearchParams(params);if(offset<=24)next.delete('offset');else next.set('offset',String(offset-24));setParams(next)}}>Previous page</button>}{items.length===24&&<button type="button" className="btn-secondary" onClick={()=>{const next=new URLSearchParams(params);next.set('offset',String(offset+24));setParams(next)}}>Next page</button>}</div>}
    </>}
  </main>
}

export function ServiceListingPage({demo=false}:{demo?:boolean}) {
  const {slug=''}=useParams()
  const [adults,setAdults]=useState(2)
  const [agesInput,setAgesInput]=useState('')
  const [fit,setFit]=useState<FamilyFit|null>(null)
  const [fitError,setFitError]=useState('')
  const [item,setItem]=useState<ServiceListing|null>(null)
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(true)
  useEffect(()=>{let active=true;setLoading(true);setError('');setFit(null);(demo?demoListing:publicListing)(slug).then(v=>{if(active)setItem(v)}).catch(e=>{if(active)setError(e instanceof Error?e.message:'Listing not available')}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[slug,demo])
  if(loading)return <main className="wrap py-16" role="status">Loading provider details…</main>
  if(error||!item)return <main className="wrap py-16"><h1 className="page-title">Service not available</h1><p role="alert" className="mt-3">{error||'This listing is no longer public.'}</p><Link className="btn-secondary mt-6" to={demo?"/demo/listings":"/listings"}>Browse services</Link></main>
  const d=item.details as Record<string,unknown>
  const array=(key:string):Record<string,unknown>[]=>Array.isArray(d[key])?d[key] as Record<string,unknown>[]:[]
  const tags=(key:string):string[]=>Array.isArray(d[key])?d[key] as string[]:[]
  return <main className="wrap py-14 min-h-[65vh]">
    <Link to={demo?"/demo/listings":"/listings"} className="text-pine underline text-sm">{demo?"Back to fictional demo":"All services"}</Link>
    <p className="small-label mt-6">{labels[item.category]} · {item.district}, {item.province}</p><h1 className="page-title">{item.title}</h1>
    <p className="lead">{item.summary}</p>
    {demo?<div className="error-banner mt-6" role="note"><strong>FICTIONAL DEMO — NOT VERIFIED OR PUBLISHED.</strong> This is a sample design preview. Prices, services and locations are illustrative and no actual business or booking exists.</div>:<div className="info-banner mt-6"><ShieldCheck size={19}/> Published listing from an approved business. This does not guarantee safety, quality, availability, price or booking. Confirm details directly with the provider.</div>}
    {item.photos.length>0&&<div className="grid md:grid-cols-2 gap-4 mt-7">{item.photos.map(photo=><figure key={photo.id} className="overflow-hidden rounded-2xl border border-ink/10 bg-white"><img src={photo.image_url} alt={photo.alt_text} referrerPolicy="no-referrer" loading="lazy" className="w-full h-64 object-cover"/><figcaption className="text-xs text-ink/60 p-3">{photo.credit} · {photo.license_name} · <a className="underline" href={photo.source_url} target="_blank" rel="noopener noreferrer">Image source</a> · <a className="underline" href={photo.license_url} target="_blank" rel="noopener noreferrer">License</a></figcaption></figure>)}</div>}
    {item.latitude!==null&&item.longitude!==null&&item.latitude!==undefined&&item.longitude!==undefined&&<section className="form-panel mt-7 space-y-2"><h2 className="text-xl font-bold">Location reference</h2><p className="text-sm">{item.location_note||'Vendor-supplied reference point. This may not identify a visitor entrance.'}</p><a href={`https://www.openstreetmap.org/?mlat=${item.latitude}&mlon=${item.longitude}#map=15/${item.latitude}/${item.longitude}`} rel="noopener noreferrer" target="_blank" className="btn-secondary inline-flex"><MapPin size={16}/> View approximate location</a>{item.location_source_url&&<a className="text-sm underline block" href={item.location_source_url} target="_blank" rel="noopener noreferrer">Coordinate source supplied by provider</a>}<p className="text-xs text-ink/60">Coordinate accuracy, route and public access have not been independently confirmed.</p></section>}
    {item.category==='accommodation'&&<section className="form-panel mt-7 space-y-4"><h2 className="text-xl font-bold">Family room suitability</h2><p className="text-sm text-ink/60">Check vendor-entered per-room capacity and child-age conditions. This does not check available rooms or calculate a booking price.</p>
      <form className="grid sm:grid-cols-[150px_1fr_auto] gap-3 items-end" onSubmit={async(e:FormEvent)=>{e.preventDefault();setFitError('');setFit(null);const ages=agesInput.trim()?agesInput.split(',').map(x=>Number(x.trim())):[];if(ages.length>30||ages.some(a=>!Number.isInteger(a)||a<0||a>17)){setFitError('Enter comma-separated child ages from 0 to 17 (maximum 30).');return}try{if(demo){const rooms=Array.isArray(d.room_types)?d.room_types as Record<string,unknown>[]:[];const results=rooms.map(room=>{const min=typeof room.min_child_age==='number'?room.min_child_age:0;const max=typeof room.max_child_age==='number'?room.max_child_age:17;const total=room.max_total_guests;return {room_name:String(room.name),may_fit:adults<=Number(room.max_adults)&&ages.length<=Number(room.max_children)&&ages.every(a=>a>=min&&a<=max)&&(typeof total!=='number'||adults+ages.length<=total),age_policy_specified:typeof room.min_child_age==='number'||typeof room.max_child_age==='number',max_adults:Number(room.max_adults),max_children:Number(room.max_children)}});setFit({adults,child_ages:ages,rooms:results,any_room_may_fit:results.some(r=>r.may_fit),disclaimer:'FICTIONAL DEMO: This is sample room-capacity logic only, not availability or a price offer.'})}else setFit(await familySuitability(slug,adults,ages))}catch(err){setFitError(err instanceof Error?err.message:'Unable to evaluate family fit')}}}>
        <label className="field">Adults<input type="number" min="1" max="30" required value={adults} onChange={e=>setAdults(Number(e.target.value))}/></label><label className="field">Children’s ages (comma-separated)<input placeholder="4, 8, 12" value={agesInput} onChange={e=>setAgesInput(e.target.value)}/></label><button type="submit" className="btn-primary justify-center">Check room fit</button>
      </form>{fitError&&<p role="alert" className="error-banner">{fitError}</p>}{fit&&<div role="status" className="rounded-xl bg-[#eef8f2] p-4 space-y-2"><b>{fit.any_room_may_fit?'Some room types may fit your group':'No room type meets the recorded limits'}</b>{fit.rooms.map((room,i)=><p key={i} className="text-sm">{room.may_fit?'✓':'×'} {room.room_name}: max {room.max_adults} adults, {room.max_children} children {room.age_policy_specified?'· child age rules provided':'· child age policy not specified'}</p>)}<p className="text-xs text-ink/60">{fit.disclaimer}</p></div>}</section>}
    <div className="grid lg:grid-cols-[1.6fr_1fr] gap-6 mt-9 items-start"><section className="form-panel space-y-5"><h2 className="text-2xl font-bold">About this service</h2><p className="whitespace-pre-line leading-7 text-ink/80">{item.description}</p>
      {item.category==='accommodation'&&<div><h3 className="font-bold text-lg">Room types</h3><div className="space-y-3 mt-3">{array('room_types').map((r,i)=><div key={i} className="rounded-xl border p-3"><b>{String(r.name)}</b><p className="text-sm">Up to {String(r.max_adults)} adults and {String(r.max_children)} children · {String(r.number_of_rooms)} unit(s){(r.min_child_age!==null&&r.min_child_age!==undefined||r.max_child_age!==null&&r.max_child_age!==undefined)&&` · child ages ${String(r.min_child_age??0)}–${String(r.max_child_age??17)}`}{r.max_total_guests!=null&&` · maximum ${String(r.max_total_guests)} total guests`}</p><p className="text-sm text-pine">{money(r.indicative_nightly_lkr_minor)} / room / night</p></div>)}</div><p className="text-sm mt-3">Amenities: {tags('amenities').join(', ')||'Ask provider'}</p><p className="text-sm mt-2">{String(d.house_rules||'')}</p></div>}
      {item.category==='restaurant'&&<div><h3 className="font-bold">Cuisines</h3><p>{tags('cuisines').join(', ')}</p><p className="text-sm mt-2">Dietary options: {tags('dietary_options').join(', ')||'Ask provider'}</p><h3 className="font-bold mt-4">Menu highlights</h3>{array('menu_items').map((r,i)=><p key={i} className="mt-2 text-sm">{String(r.name)} · {money(r.indicative_price_lkr_minor)}</p>)}<p className="text-sm mt-2">{String(d.opening_notes||'Hours: confirm with provider')}</p></div>}
      {item.category==='transport'&&<div><h3 className="font-bold">Vehicles</h3>{array('vehicle_types').map((r,i)=><p key={i} className="mt-2">{String(r.name)} · {String(r.passenger_seats)} seats · {String(r.luggage_bags)} luggage bags · {money(r.indicative_day_lkr_minor)} / day</p>)}<p className="mt-3">Areas: {tags('service_areas').join(', ')}</p><p className="mt-2 text-sm">{String(d.transfer_notes||'')}</p></div>}
      {item.category==='guide'&&<div><p>Languages: {tags('languages').join(', ')}</p><p>Areas: {tags('service_areas').join(', ')}</p><p className="mt-2">{String(d.qualification_notes||'')}</p><p className="text-pine mt-2">{money(d.indicative_daily_lkr_minor)} / day</p></div>}
      {['tour_operator','activity'].includes(item.category)&&<div><p>Experiences: {tags('experience_types').join(', ')}</p><p>Areas: {tags('service_areas').join(', ')}</p><p className="mt-2">{String(d.duration_notes||'')}</p><p className="text-pine mt-2">{money(d.indicative_person_lkr_minor)} / person</p></div>}
    </section><aside className="form-panel"><h2 className="font-extrabold text-xl">{demo?'Fictional preview only':'Contact this provider'}</h2><p className="text-sm text-ink/60 mt-2">{demo?'No contact details or bookings are available for invented demo businesses.':'Contact is handled outside Tourismo. No in-app booking, checkout or reservation is created.'}</p>
      {!demo&&item.public_email&&<a className="btn-primary mt-5 w-full justify-center break-all" href={`mailto:${item.public_email}`}><Mail size={16}/> Email provider</a>}
      {!demo&&item.public_phone&&<a className="btn-secondary mt-3 w-full justify-center" href={`tel:${item.public_phone.replace(/[^+\d]/g,'')}`}><Phone size={16}/> {item.public_phone}</a>}
      <p className="text-xs text-ink/60 mt-5">Prices and capacities are vendor-entered indicative information. Check child-age policies and all charges before making arrangements.</p>
    </aside></div>
  </main>
}
