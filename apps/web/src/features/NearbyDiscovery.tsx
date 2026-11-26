import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { Compass, LocateFixed, MapPin, Search, ShieldCheck } from 'lucide-react'
import {
  getMapConfig, getMapPoints, getNearbyPlaces, planPlaceLink,
  type MapConfig, type MapPoint, type NearbyFilters, type NearbyPoint, type NearbyResult,
} from '../lib/api'

const colors: Record<MapPoint['kind'], string> = {
  destination: '#0b766d', attraction: '#c97a24', service: '#3164a4',
}
const kindNames: Record<MapPoint['kind'], string> = {
  destination: 'Destination', attraction: 'Attraction', service: 'Tourism service',
}
const categories = [
  ['accommodation', 'Accommodation'], ['restaurant', 'Restaurants'],
  ['guide', 'Local guides'], ['transport', 'Transport'],
  ['tour_operator', 'Tour operators'], ['activity', 'Activities'],
  ['heritage', 'Heritage attractions'], ['nature', 'Nature attractions'],
  ['landmark', 'Landmarks'], ['beach', 'Beaches'], ['wildlife', 'Wildlife'],
  ['culture', 'Cultural attractions'], ['adventure', 'Adventure attractions'],
] as const

type SearchControls = {
  radius_km: number; kind: NearbyFilters['kind']; category: string; q: string
}
const defaultControls: SearchControls = {radius_km: 25, kind: 'all', category: '', q: ''}

function MapFocus({latitude, longitude, selected}: {latitude:number; longitude:number; selected: NearbyPoint | null}) {
  const map = useMap()
  const focusedLat = selected?.latitude ?? latitude
  const focusedLon = selected?.longitude ?? longitude
  useEffect(() => {
    map.setView([focusedLat, focusedLon], Math.max(map.getZoom(), 10), {animate: true})
  }, [map, focusedLat, focusedLon])
  return null
}

export function NearbyDiscovery() {
  const [params] = useSearchParams()
  const editTripId = params.get('edit_trip')
  const [available, setAvailable] = useState<MapPoint[]>([])
  const [config, setConfig] = useState<MapConfig | null>(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [initialError, setInitialError] = useState('')
  const [centerId, setCenterId] = useState('')
  const [manualCenter, setManualCenter] = useState<[number, number] | null>(null)
  const [locationMessage, setLocationMessage] = useState('')
  const [controls, setControls] = useState<SearchControls>(defaultControls)
  const [query, setQuery] = useState<NearbyFilters | null>(null)
  const [data, setData] = useState<NearbyResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const requestedDestination = params.get('destination')
  const requestedPoint = params.get('point')

  useEffect(() => {
    let active = true
    Promise.all([getMapPoints(), getMapConfig()])
      .then(([points, mapConfig]) => {
        if (!active) return
        setAvailable(points)
        setConfig(mapConfig)
        const matching = requestedPoint ? points.find(p => p.id === requestedPoint) :
          requestedDestination ? points.find(p => p.kind === 'destination' && p.detail_path === `/destinations/${requestedDestination}`) : null
        const first = matching ?? (!requestedDestination && !requestedPoint ?
          points.find(p => p.kind === 'destination') ?? points[0] : undefined)
        if (first) {
          setCenterId(first.id)
          setQuery(first.kind === 'destination' ?
            {destination: first.detail_path.split('/').pop() ?? '', radius_km: 25, kind: 'all'} :
            {near_lat: first.latitude, near_lon: first.longitude, radius_km: 25, kind: 'all'})
        }
      })
      .catch(e => {if (active) setInitialError(e instanceof Error ? e.message : 'Map locations are unavailable')})
      .finally(() => {if (active) setInitialLoading(false)})
    return () => {active = false}
  }, [requestedDestination, requestedPoint])

  const chosen = available.find(p => p.id === centerId) ?? null
  const center: [number, number] | null = centerId === 'my-location' ? manualCenter :
    chosen ? [chosen.latitude, chosen.longitude] : null
  const selected = useMemo(() => data?.points.find(p => p.id === selectedId) ?? null, [data, selectedId])

  useEffect(() => {
    if (!query) return
    let active = true
    setLoading(true)
    setError('')
    getNearbyPlaces(query)
      .then(result => {if (active) {setData(result); setSelectedId(null)}})
      .catch(e => {if (active) {setData(null);setError(e instanceof Error ? e.message : 'Nearby search unavailable')}})
      .finally(() => {if (active) setLoading(false)})
    return () => {active = false}
  }, [query])

  const buildSearch = (event?: FormEvent) => {
    event?.preventDefault()
    if (!center) return
    const centerParams = chosen?.kind === 'destination' && centerId !== 'my-location' ?
      {destination: chosen.detail_path.split('/').pop() ?? ''} :
      {near_lat: center[0], near_lon: center[1]}
    setQuery({...centerParams, radius_km: controls.radius_km, kind: controls.kind,
      category: controls.category || undefined, q: controls.q.trim() || undefined})
    setSelectedId(null)
  }

  const useMyLocation = () => {
    setLocationMessage('')
    if (!navigator.geolocation) {setLocationMessage('Location access is not supported in this browser.');return}
    navigator.geolocation.getCurrentPosition(
      result => {
        const latitude = result.coords.latitude, longitude = result.coords.longitude
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
          setLocationMessage('The browser did not provide usable coordinates.');return
        }
        setManualCenter([latitude, longitude])
        setCenterId('my-location')
        setSelectedId(null)
        setQuery({near_lat: latitude, near_lon: longitude, radius_km: controls.radius_km,
          kind: controls.kind, category: controls.category || undefined, q: controls.q.trim() || undefined})
        setLocationMessage('Using your location for this search only. Tourismo does not save it to your profile.')
      },
      () => setLocationMessage('Location was declined or unavailable. Select a mapped place instead.'),
      {enableHighAccuracy: false, timeout: 10000, maximumAge: 300000})
  }

  const onCenterChange = (id: string) => {
    setCenterId(id)
    setData(null)
    setQuery(null)
    setSelectedId(null)
    setLocationMessage('Choose your search filters, then press Find nearby.')
  }

  return <main className="wrap py-12 min-h-[75vh]">
    <span className="small-label">PHASE 5.2 · LOCATION DISCOVERY</span>
    <h1 className="page-title mt-2">Find places nearby</h1>
    <p className="lead mt-3">Discover attractions, accommodation, restaurants and other independently published services near a mapped place. Distances are straight-line estimates—not driving distances or travel times.</p>

    <form className="form-panel mt-7 grid gap-4 md:grid-cols-2 lg:grid-cols-4 items-end" onSubmit={buildSearch}>
      <label className="field lg:col-span-2"><span>Search around</span>
        <select value={centerId} onChange={e => onCenterChange(e.target.value)} aria-label="Mapped place to search around">
          <option value="">Select a mapped place</option>
          {manualCenter && <option value="my-location">My location (this session)</option>}
          {available.map(p => <option key={p.id} value={p.id}>{kindNames[p.kind]} · {p.title} ({p.district})</option>)}
        </select>
      </label>
      <label className="field"><span>Within (straight-line distance)</span>
        <select value={controls.radius_km} onChange={e => setControls(c => ({...c, radius_km: Number(e.target.value)}))}>
          {[5, 10, 25, 50, 100].map(r => <option key={r} value={r}>{r} km</option>)}
        </select>
      </label>
      <label className="field"><span>Place type</span>
        <select value={controls.kind} onChange={e => setControls(c => ({...c, kind: e.target.value as NearbyFilters['kind'], category: ''}))}>
          <option value="all">All place types</option><option value="destination">Destinations</option>
          <option value="attraction">Attractions</option><option value="service">Tourism services</option>
        </select>
      </label>
      <label className="field lg:col-span-2"><span>Name or district (optional)</span>
        <input maxLength={80} placeholder="e.g. Kandy, heritage, resort" value={controls.q}
          onChange={e => setControls(c => ({...c, q: e.target.value}))}/>
      </label>
      <label className="field"><span>Category (optional)</span>
        <select value={controls.category} onChange={e => setControls(c => ({...c, category: e.target.value}))}>
          <option value="">All categories</option>
          {controls.kind !== 'attraction' && controls.kind !== 'destination' && categories.slice(0, 6).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
          {controls.kind !== 'service' && controls.kind !== 'destination' && categories.slice(6).map(([code, label]) => <option key={code} value={code}>{label}</option>)}
        </select>
      </label>
      <div className="flex flex-wrap gap-2 items-center">
        <button className="btn-primary" type="submit" disabled={!center || loading}><Search size={17}/> Find nearby</button>
        <button className="btn-secondary" type="button" onClick={useMyLocation}><LocateFixed size={17}/> Use my location</button>
      </div>
    </form>

    {locationMessage && <p role="status" className="mt-3 text-sm text-ink/70">{locationMessage}</p>}
    {initialLoading && <p role="status" className="mt-6">Loading mapped locations…</p>}
    {initialError && <p role="alert" className="error-banner mt-6">{initialError}</p>}
    {!initialLoading && !initialError && !center && <div className="info-banner mt-6">
      <MapPin size={20} className="shrink-0"/> {requestedDestination || requestedPoint ?
        'The requested place does not have a public map location yet. Choose another mapped place above or use your location.' :
        'No published mapped places are available yet. Coordinate data must be added and reviewed before nearby discovery can work.'}
    </div>}
    {loading && <p role="status" className="mt-6">Finding nearby places…</p>}
    {error && <p role="alert" className="error-banner mt-6">{error}</p>}

    {data && !loading && <>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 text-sm text-ink/70">
        <p><strong>{data.points.length}</strong> nearby mapped {data.points.length === 1 ? 'place' : 'places'} within <strong>{data.radius_km} km</strong> of {chosen?.title || data.center.title}</p>
        {data.has_more && <p>Showing the nearest 60 results. Narrow the filters for more.</p>}
      </div>
      <div className="grid lg:grid-cols-[minmax(0,1.55fr)_minmax(290px,0.9fr)] gap-5 mt-4 items-start">
        <section aria-label="Nearby discovery map" className="rounded-2xl overflow-hidden border border-ink/10 bg-[#e0eae6] min-w-0">
          {config?.tile_url ? <MapContainer center={[data.center.latitude, data.center.longitude]} zoom={10} scrollWheelZoom
            className="h-[430px] md:h-[570px] w-full" style={{zIndex: 0}}>
            <TileLayer url={config.tile_url} attribution={config.attribution} maxZoom={19}/>
            <MapFocus latitude={data.center.latitude} longitude={data.center.longitude} selected={selected}/>
            <Circle center={[data.center.latitude, data.center.longitude]} radius={data.radius_km * 1000}
              pathOptions={{color: '#0b766d', weight: 1, fillOpacity: 0.04}}/>
            <CircleMarker center={[data.center.latitude, data.center.longitude]} radius={11}
              pathOptions={{color: '#fff', fillColor: '#174b41', fillOpacity: 1, weight: 2}}>
              <Popup><b>Search center</b><p>{chosen?.title || data.center.title}</p></Popup>
            </CircleMarker>
            {data.points.map(p => <CircleMarker key={p.id} center={[p.latitude, p.longitude]}
              radius={selectedId === p.id ? 12 : 8}
              pathOptions={{color: '#fff', weight: 2, fillColor: colors[p.kind], fillOpacity: 0.95}}
              eventHandlers={{click: () => setSelectedId(p.id)}}>
              <Popup><div className="space-y-2 min-w-[175px]">
                <b>{p.title}</b><p>{kindNames[p.kind]} · {p.distance_km.toFixed(1)} km straight-line</p>
                {p.business_verified && <p>✓ Verified business</p>}
                {p.is_sample && <p>Editorial sample</p>}
                <Link to={p.detail_path} className="underline">View details</Link><Link to={planPlaceLink(p.id,editTripId)} className="block underline">Add to trip</Link>
              </div></Popup>
            </CircleMarker>)}
          </MapContainer> : <div className="min-h-[430px] grid place-items-center text-center p-8">
            <div><MapPin size={28} className="mx-auto text-pine"/><b>Map tiles not configured</b>
              <p className="text-sm mt-2">The nearby place list is still available. Configure licensed production map tiles to enable the map.</p></div>
          </div>}
        </section>
        <aside aria-label="Nearby results" className="form-panel p-4 max-h-[570px] overflow-y-auto">
          <h2 className="text-xl font-bold">Nearest places</h2>
          <p className="text-xs text-ink/60 mt-2">Nearest first · Only locations with coordinates · Demo businesses excluded</p>
          {!data.points.length ? <p className="mt-5 text-sm text-ink/70">No published mapped places match this radius and category. Try a wider distance or another mapped center.</p> :
            <div className="space-y-3 mt-4">{data.points.map(p => <div key={p.id}
              className={`rounded-xl border p-3 ${selectedId === p.id ? 'border-pine bg-[#eef8f3]' : 'border-ink/10 bg-white'}`}>
              <button type="button" onClick={() => setSelectedId(p.id)} className="w-full text-left" aria-pressed={selectedId === p.id}>
                <span className="text-xs font-bold uppercase" style={{color: colors[p.kind]}}>{kindNames[p.kind]} · {p.category.replaceAll('_',' ')}</span>
                <span className="block font-extrabold mt-1">{p.title}</span>
                <span className="text-xs text-ink/60">{p.district} · <strong>{p.distance_km.toFixed(1)} km</strong> straight-line</span>
              </button>
              <div className="flex flex-wrap items-center gap-2 mt-3">
                {p.business_verified && <span className="text-xs text-emerald-800 inline-flex items-center gap-1"><ShieldCheck size={13}/> Verified business</span>}
                {p.is_sample && <span className="text-xs text-amber-800">Editorial sample</span>}
                <Link className="text-sm text-pine underline font-semibold" to={planPlaceLink(p.id,editTripId)}>Add to trip</Link><Link className="ml-auto text-sm text-pine underline font-semibold" to={p.detail_path}>View details</Link>
              </div>
            </div>)}</div>}
        </aside>
      </div>
      <p className="text-xs text-ink/60 mt-5">{data.distance_note} Pins may represent approximate locations, not entrances. No availability, price or opening-hours claims are made by this search.</p>
    </>}
    <div className="mt-7 flex flex-wrap gap-3 items-center">
      <Link to={editTripId?`/map?edit_trip=${encodeURIComponent(editTripId)}`:'/map'} className="btn-secondary"><Compass size={17}/> Explore the full map</Link>
      <Link to="/discover" className="text-pine font-semibold underline">Browse all destinations (including unmapped places)</Link>
    </div>
  </main>
}
