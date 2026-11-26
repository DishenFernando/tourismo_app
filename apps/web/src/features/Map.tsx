import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { divIcon } from 'leaflet'
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import { Filter, LocateFixed, MapPin, ShieldCheck } from 'lucide-react'
import type { MapPoint, MapConfig, ResolvedLocation } from '../lib/api'
import { getViewportPoints, getMapConfig, resolveLocationLink, planPlaceLink } from '../lib/api'
import { clipToIsland, clusterMapPoints, ISLAND_BOUNDS, type ViewportBounds } from '../lib/mapViewport'
import { useTourismoAuth } from '../app/Auth'

const islandCenter:[number,number] = [7.80,80.73]
const pinColor:Record<MapPoint['kind'],string>={destination:'#0b766d',attraction:'#c97a24',service:'#3164a4'}
const typeLabel:Record<MapPoint['kind'],string>={destination:'Destination',attraction:'Attraction',service:'Tourism service'}
const placeLink=(point:MapPoint)=>point.detail_path
const nearbyLink=(point:MapPoint,editTripId?:string|null)=>{
  const path=point.kind==='destination'?`/nearby?destination=${encodeURIComponent(point.detail_path.split('/').pop()||'')}`:`/nearby?point=${encodeURIComponent(point.id)}`
  return `${path}${editTripId?`&edit_trip=${encodeURIComponent(editTripId)}`:''}`
}

function FocusOnSelection({point,userCenter}:{point:MapPoint|null;userCenter:[number,number]|null}) {
  const map=useMap()
  useEffect(()=>{
    if(point) map.setView([point.latitude,point.longitude],Math.max(11,map.getZoom()),{animate:true})
    else if(userCenter) map.setView(userCenter,Math.max(11,map.getZoom()),{animate:true})
  },[map,point,userCenter])
  return null
}

function ViewportObserver({onView}:{onView:(bounds:ViewportBounds|null,zoom:number)=>void}) {
  const map=useMapEvents({moveend:sync,zoomend:sync})
  function sync(){
    const b=map.getBounds()
    onView(clipToIsland({south:b.getSouth(),west:b.getWest(),north:b.getNorth(),east:b.getEast()}),map.getZoom())
  }
  useEffect(()=>{sync()},[map]) // Initial map center/viewport.
  return null
}

function PointPins({places,zoom,selectedId,onSelect,editTripId}:{places:MapPoint[];zoom:number;selectedId:string|null;onSelect:(id:string)=>void;editTripId:string|null}) {
  const map=useMap()
  const clusters=useMemo(()=>clusterMapPoints(places,zoom),[places,zoom])
  return <>{clusters.map(cluster=>cluster.points.length>1 ?
    <Marker key={cluster.key} position={[cluster.latitude,cluster.longitude]}
      icon={divIcon({className:'tourismo-cluster',html:`<span>${cluster.points.length}</span>`,iconSize:[38,38],iconAnchor:[19,19]})}
      eventHandlers={{click:()=>{if(map.getZoom()<17)map.setView([cluster.latitude,cluster.longitude],Math.min(17,map.getZoom()+2),{animate:true})}}}>
      <Popup><div className="space-y-2"><strong>{cluster.points.length} places together</strong>
        <p className="text-xs">Zoom in or choose a place from the results list. Pins are only a visual group.</p>
        {cluster.points.slice(0,6).map(p=><div key={p.id}><Link to={p.detail_path} className="underline">{p.title}</Link></div>)}
        {cluster.points.length>6&&<p className="text-xs">Plus {cluster.points.length-6} more in the results list.</p>}
      </div></Popup>
    </Marker> : cluster.points.map(p=>
    <CircleMarker key={p.id} center={[p.latitude,p.longitude]} radius={p.id===selectedId?12:9}
      pathOptions={{color:'#fff',weight:2,fillColor:pinColor[p.kind],fillOpacity:0.95}}
      eventHandlers={{click:()=>onSelect(p.id)}}>
      <Popup><div className="space-y-2 min-w-[180px]">
        <strong>{p.title}</strong><div>{typeLabel[p.kind]} · {p.district}</div>
        {p.business_verified&&<div>✓ Verified business</div>}
        {p.is_sample&&<div>Editorial sample — needs review</div>}
        <p className="text-xs">{p.location_note}</p>
        {p.source_url?.startsWith('https://')&&<a className="block underline" href={p.source_url} target="_blank" rel="noopener noreferrer">Coordinate source</a>}
        <Link to={placeLink(p)} className="font-semibold underline block">View details</Link>
        <Link to={nearbyLink(p,editTripId)} className="block underline">Explore nearby</Link>
        <Link to={planPlaceLink(p.id,editTripId)} className="block font-semibold underline">Add to trip</Link>
      </div></Popup>
    </CircleMarker>))}</>
}

export function ExplorerMap(){
  const [params]=useSearchParams()
  const editTripId=params.get('edit_trip')
  const [points,setPoints]=useState<MapPoint[]>([])
  const [config,setConfig]=useState<MapConfig|null>(null)
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [hasMore,setHasMore]=useState(false)
  const [kind,setKind]=useState<'all'|MapPoint['kind']>('all')
  const [search,setSearch]=useState(params.get('q')||'')
  const [selectedId,setSelectedId]=useState<string|null>(null)
  const [userCenter,setUserCenter]=useState<[number,number]|null>(null)
  const [locationMessage,setLocationMessage]=useState('')
  const [viewport,setViewport]=useState<ViewportBounds|null>(ISLAND_BOUNDS)
  const [zoom,setZoom]=useState(8)

  useEffect(()=>{
    let active=true
    void getMapConfig().then(result=>{if(active)setConfig(result)})
      .catch(e=>{if(active)setError(e instanceof Error?e.message:'Unable to configure map')})
    return()=>{active=false}
  },[])
  const onView=useCallback((bounds:ViewportBounds|null,nextZoom:number)=>{
    setZoom(nextZoom)
    setViewport(previous=>JSON.stringify(previous)===JSON.stringify(bounds)?previous:bounds)
  },[])
  // Debounce pan/zoom requests and abort stale fetches. No browser-location access
  // happens unless the visitor explicitly selects "Use my location".
  useEffect(()=>{
    if(!viewport){setPoints([]);setHasMore(false);setLoading(false);setError('');return}
    const controller=new AbortController()
    const timeout=window.setTimeout(()=>{
      setLoading(true);setError('')
      void getViewportPoints(viewport,kind,controller.signal)
        .then(result=>{if(!controller.signal.aborted){setPoints(result.points);setHasMore(result.has_more)}})
        .catch(e=>{if(!controller.signal.aborted)setError(e instanceof Error?e.message:'Unable to load mapped places')})
        .finally(()=>{if(!controller.signal.aborted)setLoading(false)})
    },180)
    return()=>{window.clearTimeout(timeout);controller.abort()}
  },[viewport,kind])

  const text=search.trim().toLowerCase()
  const visible=useMemo(()=>points.filter(p=>!text||
    `${p.title} ${p.district} ${p.category}`.toLowerCase().includes(text)),[points,text])
  const selected=visible.find(p=>p.id===selectedId)||null
  const useLocation=()=>{
    setLocationMessage('')
    if(!navigator.geolocation){setLocationMessage('This browser does not support location access.');return}
    navigator.geolocation.getCurrentPosition(
      result=>{setSelectedId(null);setUserCenter([result.coords.latitude,result.coords.longitude]);setLocationMessage('Map centered near your location. Tourismo does not store your position.')},
      ()=>setLocationMessage('Location was unavailable or permission was declined. You can browse without it.'),
      {enableHighAccuracy:false,timeout:10000,maximumAge:300000})
  }
  return <main className="wrap py-12 min-h-[75vh]">
    <span className="small-label">DISCOVER SRI LANKA</span>
    <h1 className="page-title">Explore on the map</h1>
    <p className="lead">Find recorded attractions, editorial destinations, and independently reviewed tourism services. Pins indicate sourced locations, not confirmed entrances or bookings.</p>
    <div className="mt-4"><Link className="btn-secondary" to="/nearby">Explore nearby places</Link></div>
    <div className="form-panel mt-7 flex flex-wrap items-end gap-3">
      <label className="field grow min-w-[190px]"><span><Filter size={15} className="inline mr-1"/> Show</span>
        <select value={kind} onChange={e=>{setKind(e.target.value as typeof kind);setSelectedId(null)}}>
          <option value="all">All mapped places</option><option value="destination">Destinations</option>
          <option value="attraction">Attractions</option><option value="service">Approved service listings</option>
        </select>
      </label>
      <label className="field grow min-w-[210px]"><span>Filter the visible map area</span>
        <input maxLength={80} value={search} onChange={e=>{setSearch(e.target.value);setSelectedId(null)}} placeholder="e.g. Kandy, heritage"/>
      </label>
      <button type="button" className="btn-secondary" onClick={useLocation}><LocateFixed size={17}/> Use my location</button>
    </div>
    {locationMessage&&<p role="status" className="text-sm text-ink/70 mt-3">{locationMessage}</p>}
    {loading&&<p role="status" className="mt-6">Loading places in the visible area…</p>}
    {error&&<p role="alert" className="error-banner mt-6">{error}</p>}
    <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-sm text-ink/70">
      <p><strong>{visible.length}</strong> mapped {visible.length===1?'place':'places'} in this view{loading?' (updating…)':''}</p>
      <p>Teal: destinations · Amber: attractions · Blue: tourism services</p>
    </div>
    {hasMore&&<p role="status" className="rounded-xl border border-amber-300 bg-amber-50 p-3 mt-3 text-sm">
      This map area contains more than 180 places. Zoom in to view additional markers. The results are capped for performance; this is not a complete count.
    </p>}
    {!viewport&&<p role="status" className="rounded-xl border p-3 mt-3 text-sm">This view is outside the Sri Lanka map area. Move the map back to see Tourismo locations.</p>}
    <div className="grid lg:grid-cols-[minmax(0,1.65fr)_minmax(290px,0.85fr)] gap-5 mt-4 items-start">
      <section aria-label="Interactive map of Sri Lanka" className="rounded-2xl overflow-hidden border border-ink/10 bg-[#e0eae6] min-w-0">
        {config?.tile_url ? <MapContainer center={islandCenter} zoom={8} scrollWheelZoom={true}
            className="h-[400px] md:h-[570px] w-full" style={{zIndex:0}}>
          <TileLayer url={config.tile_url} attribution={config.attribution} maxZoom={19}/>
          <ViewportObserver onView={onView}/>
          <FocusOnSelection point={selected} userCenter={userCenter}/>
          <PointPins places={visible} zoom={zoom} editTripId={editTripId} selectedId={selectedId} onSelect={id=>{setSelectedId(id);setUserCenter(null)}}/>
        </MapContainer> : <div className="grid min-h-[400px] place-items-center p-8 text-center">
          <div><MapPin size={32} className="mx-auto text-pine"/><h2 className="font-bold text-xl mt-3">Map tiles not configured</h2>
            <p className="text-sm mt-3">For production, configure a licensed HTTPS tile provider. The list remains available without tiles.</p></div>
        </div>}
      </section>
      <aside aria-label="Mapped place results" className="form-panel p-4 max-h-[570px] overflow-y-auto">
        <h2 className="text-xl font-bold">Places in this view</h2>
        <p className="text-xs text-ink/55 mt-2">Pan or zoom to load an area. Marker clusters combine nearby pins; choose a result here to select one place. No fictional demo services.</p>
        {visible.length===0?<p className="text-sm text-ink/70 mt-5">{loading?'Updating locations…':'No recorded coordinates match this view. Browse the '} {!loading&&<Link className="underline text-pine" to="/discover">destination directory</Link>} {!loading&&'for unmapped places.'}</p>:
          <div className="mt-4 space-y-2">{visible.map(p=><div key={p.id} className={`rounded-xl border p-3 ${selectedId===p.id?'border-pine bg-[#eef8f3]':'border-ink/10 bg-white'}`}>
            <button type="button" onClick={()=>{setSelectedId(p.id);setUserCenter(null)}} className="text-left w-full" aria-pressed={selectedId===p.id}>
              <span className="text-xs font-bold uppercase" style={{color:pinColor[p.kind]}}>{typeLabel[p.kind]} · {p.category}</span>
              <span className="block font-extrabold mt-1">{p.title}</span><span className="text-xs text-ink/60">{p.district}</span>
            </button>
            <div className="flex flex-wrap gap-2 mt-2 items-center">
              {p.business_verified&&<span className="text-xs font-semibold text-emerald-800 inline-flex items-center gap-1"><ShieldCheck size={13}/> Verified business</span>}
              {p.is_sample&&<span className="text-xs text-amber-800">Sample</span>}
              {p.source_url?.startsWith('https://')&&<a className="text-xs underline text-pine" href={p.source_url} target="_blank" rel="noopener noreferrer">Source</a>}
              <Link className="text-sm underline text-pine" to={nearbyLink(p,editTripId)}>Nearby</Link><Link className="text-sm underline text-pine" to={planPlaceLink(p.id,editTripId)}>Add to trip</Link><Link className="text-sm underline text-pine font-semibold ml-auto" to={placeLink(p)}>Details</Link>
            </div>
          </div>)}</div>}
      </aside>
    </div>
    <p className="text-xs text-ink/60 mt-5">Results only cover the visible area, with a 180-place limit. Groups are visual clusters, not extra places. Map lines and pins do not represent road distances. Tile requests go directly to the configured provider. Location access requires your permission.</p>
  </main>
}

/** Recenter an already-mounted Leaflet map as a link resolves or a value changes. */
function CenterLocationPicker({latitude,longitude}:{latitude:number|null;longitude:number|null}){
  const map=useMap()
  useEffect(()=>{
    if(latitude!==null&&longitude!==null)map.setView([latitude,longitude],Math.max(map.getZoom(),14),{animate:true})
  },[map,latitude,longitude])
  return null
}

function ClickLocation({onPick}:{onPick:(latitude:number,longitude:number)=>void}){
  useMapEvents({click:e=>onPick(Number(e.latlng.lat.toFixed(6)),Number(e.latlng.lng.toFixed(6)))})
  return null
}

function mayAttachMapReference(value:string):boolean{
  try{
    const link=new URL(value)
    const hosts=['google.com','www.google.com','maps.google.com','google.lk','www.google.lk',
      'maps.google.lk','maps.app.goo.gl','goo.gl','openstreetmap.org','www.openstreetmap.org',
      'maps.apple.com','bing.com','www.bing.com']
    return link.protocol==='https:' && hosts.includes(link.hostname.toLowerCase()) && !link.username && !link.password && (!link.port||link.port==='443')
  }catch{return false}
}

type LocationPickerProps={
  latitude:number|null; longitude:number|null;
  onPick:(latitude:number,longitude:number)=>void;
  sourceUrl?:string|null; onSourceChange?:(url:string)=>void;
}

/** Import a shared map pin as a *proposal*, then confirm and save it in the parent form. */
export function LocationPicker({latitude,longitude,onPick,sourceUrl,onSourceChange}:LocationPickerProps){
  const auth=useTourismoAuth()
  const [tile,setTile]=useState<MapConfig|null>(null)
  const [open,setOpen]=useState(false)
  const [draftUrl,setDraftUrl]=useState(sourceUrl??'')
  const [proposal,setProposal]=useState<ResolvedLocation|null>(null)
  const [confirmedCenter,setConfirmedCenter]=useState(false)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  useEffect(()=>setDraftUrl(sourceUrl??''),[sourceUrl])
  useEffect(()=>{if(!open)return;let active=true;void getMapConfig().then(v=>{if(active)setTile(v)}).catch(()=>{});return()=>{active=false}},[open])
  const fetchLocation=async()=>{
    setError('');setNotice('');setProposal(null);setConfirmedCenter(false);setBusy(true)
    try{
      const token=await auth.token()
      if(!token)throw new Error('Please sign in before importing a map location.')
      const result=await resolveLocationLink(draftUrl.trim(),token)
      setProposal(result);setOpen(true)
    }catch(e){setError(e instanceof Error?e.message:'Could not resolve this map link.')}
    finally{setBusy(false)}
  }
  const chooseLocation=()=>{
    if(!proposal||!onSourceChange)return
    onPick(proposal.latitude,proposal.longitude)
    onSourceChange(proposal.source_url)
    setProposal(null)
    setConfirmedCenter(false)
  }
  const displayLat=proposal?.latitude??latitude
  const displayLon=proposal?.longitude??longitude
  return <div className="rounded-xl border border-ink/15 bg-[#f4f8f5] p-4 space-y-3">
    <div><p className="font-bold text-sm">Pinpoint this location</p>
      <p className="text-xs text-ink/65 mt-1">A shared map link is usually easier than guessing a point. Check where the pin lands before using it.</p></div>
    {onSourceChange&&<div className="space-y-2">
      <label className="field"><span>Paste Google Maps, OpenStreetMap, Apple Maps or Bing Maps link</span>
        <input type="url" maxLength={2048} value={draftUrl} placeholder="https://maps.app.goo.gl/…"
          onChange={e=>{setDraftUrl(e.target.value);setProposal(null);setConfirmedCenter(false);setError('');setNotice('')}}/></label>
      <div className="flex flex-wrap gap-2 items-center">
        <button className="btn-secondary" type="button" disabled={busy||!draftUrl.trim()} onClick={()=>void fetchLocation()}>
          {busy?'Checking location…':'Find location from link'}
        </button>
        <button className="text-sm underline text-pine" type="button" disabled={!mayAttachMapReference(draftUrl.trim())}
          onClick={()=>{onSourceChange(draftUrl.trim());setProposal(null);setOpen(true);setError('');setNotice('Link attached. Choose and check the point manually before saving.')}}>
          Attach link and choose the pin manually
        </button>
      </div>
      {sourceUrl&&<p className="text-xs text-emerald-800">Saved in form: location link attached. Map coordinates still require checking.</p>}
      {error&&<p role="alert" className="error-banner text-sm">{error}</p>}
      {notice&&<p role="status" className="text-sm text-pine">{notice}</p>}
      {proposal&&<div className="rounded-lg border border-pine/30 p-3 bg-white space-y-2" role="status">
        <p className="text-sm font-bold">{proposal.provider}: {proposal.latitude.toFixed(6)}, {proposal.longitude.toFixed(6)}</p>
        <p className="text-sm">{proposal.message}</p>
        <a className="text-xs underline text-pine" href={proposal.source_url} rel="noopener noreferrer" target="_blank">Check original map link</a>
        {proposal.precision==='map_center'&&<label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={confirmedCenter} onChange={e=>setConfirmedCenter(e.target.checked)}/>
          I checked this approximate map centre against the actual place.
        </label>}
        <button type="button" className="btn-primary" disabled={proposal.precision==='map_center'&&!confirmedCenter} onClick={chooseLocation}>
          Use this location
        </button>
      </div>}
    </div>}
    <button type="button" className="text-sm text-pine underline font-semibold" onClick={()=>setOpen(v=>!v)}>
      {open?'Hide map preview':'Show map preview / adjust manually'}
    </button>
    {open&&<div className="mt-3">
      {tile?.tile_url?<MapContainer center={displayLat!==null&&displayLon!==null?[displayLat,displayLon]:islandCenter}
        zoom={displayLat!==null?14:8} scrollWheelZoom={true} className="h-[275px] w-full rounded-lg" style={{zIndex:0}}>
        <TileLayer url={tile.tile_url} attribution={tile.attribution}/>
        <CenterLocationPicker latitude={displayLat} longitude={displayLon}/>
        <ClickLocation onPick={(lat,lon)=>{setProposal(null);onPick(lat,lon)}}/>
        {displayLat!==null&&displayLon!==null&&<CircleMarker center={[displayLat,displayLon]}
          radius={11} pathOptions={{color:'#fff',weight:3,fillColor:proposal?'#b9701b':'#0b766d',fillOpacity:1}}/>}
      </MapContainer>:<p role="status" className="text-sm">Map tiles unavailable. Enter coordinates manually or confirm them in the linked map.</p>}
      <p className="text-xs text-ink/65 mt-2">Orange: suggested position. Teal: selected position. Click the map to adjust. A map link is evidence of a shared location, not proof of the entrance or public access.</p>
    </div>}
  </div>
}
