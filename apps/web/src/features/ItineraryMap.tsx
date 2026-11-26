import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import { LatLngBounds } from 'leaflet'
import { getMapConfig, resolveItineraryPlaces, type MapConfig, type MapPoint, type Stop } from '../lib/api'

const dayColor = ['#0b766d', '#3164a4', '#c97a24', '#9659a6', '#ae5b4a']

type MappedStop = {stop:Stop; index:number; place:MapPoint}

function FitStops({positions}:{positions:[number,number][]}) {
  const map = useMap()
  const key = positions.map(p => p.join(',')).join(';')
  useEffect(() => {
    if (!positions.length) return
    if (positions.length === 1) map.setView(positions[0], 12)
    else {
      const bounds = new LatLngBounds(positions[0], positions[0])
      for (const position of positions.slice(1)) bounds.extend(position)
      map.fitBounds(bounds, {padding:[35,35], maxZoom:13})
    }
  // Refit only when the selected points change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key])
  return null
}

export function ItineraryMap({stops, day}:{stops:Stop[];day:number}) {
  const [config,setConfig] = useState<MapConfig|null>(null)
  const [points,setPoints] = useState<MapPoint[]>([])
  const [loading,setLoading] = useState(false)
  const [error,setError] = useState('')
  const ids = useMemo(() => Array.from(new Set(stops.map(s=>s.place_id).filter((v):v is string=>!!v))), [stops])
  const idsKey = ids.join('|')

  useEffect(() => {
    let active = true
    getMapConfig().then(value=>{if(active)setConfig(value)}).catch(()=>{})
    return () => {active=false}
  }, [])
  useEffect(() => {
    let active = true
    if (!idsKey) {setPoints([]);setError('');setLoading(false);return}
    setLoading(true)
    setError('')
    void resolveItineraryPlaces(idsKey.split('|'))
      .then(value=>{if(active)setPoints(value)})
      .catch(()=>{if(active){setPoints([]);setError('Unable to load public map locations. Text stops are still available.')}})
      .finally(()=>{if(active)setLoading(false)})
    return () => {active=false}
  }, [idsKey])

  const byId = useMemo(()=>new Map(points.map(p=>[p.id,p])),[points])
  const mapped:MappedStop[] = stops.map((stop,index)=>({stop,index,place:byId.get(stop.place_id||'')}))
    .filter((item):item is MappedStop=>!!item.place && (day===0||item.stop.day===day))
  const positions:[number,number][] = mapped.map(({place})=>[place.latitude,place.longitude])
  const connections = new Map<number,[number,number][]>()
  for (const item of mapped) connections.set(item.stop.day,[...(connections.get(item.stop.day)||[]),[item.place.latitude,item.place.longitude]])
  const unavailable = stops.filter(stop=>stop.place_id && !byId.has(stop.place_id)).length

  return <section className="form-panel mt-6" aria-label="Trip itinerary map">
    <h3 className="text-xl font-bold">Your itinerary on the map</h3>
    <p className="help mt-2">Pins show only currently published locations. Lines show the sequence of your stops, not verified road routes, travel times, or accessible entrances.</p>
    {loading && <p role="status" className="text-sm mt-3">Checking public location references…</p>}
    {error && <p role="alert" className="error-banner mt-3">{error}</p>}
    {!!unavailable && !loading && !error && <p role="status" className="text-amber-800 text-sm mt-3">{unavailable} linked stop(s) are no longer publicly mapped. Their notes remain in your draft, but no pin or provider link is shown.</p>}
    {mapped.length && config?.tile_url ? <div className="mt-4 rounded-xl overflow-hidden border border-ink/10">
      <MapContainer center={positions[0]} zoom={11} scrollWheelZoom className="h-[350px] md:h-[450px] w-full" style={{zIndex:0}}>
        <TileLayer url={config.tile_url} attribution={config.attribution} maxZoom={19}/>
        <FitStops positions={positions}/>
        {Array.from(connections.entries()).map(([group,coords])=>coords.length>1 &&
          <Polyline key={group} positions={coords} pathOptions={{color:dayColor[(group-1)%dayColor.length],weight:3,dashArray:'6 6'}}/>)}
        {mapped.map(({stop,index,place})=><CircleMarker key={`${index}:${place.id}`} center={[place.latitude,place.longitude]} radius={9}
          pathOptions={{color:'#fff',weight:2,fillColor:dayColor[(stop.day-1)%dayColor.length],fillOpacity:1}}>
          <Popup><div className="space-y-1 min-w-[160px]"><b>Day {stop.day}: {stop.title}</b>
            <p>{place.kind} · {place.district}</p>
            {place.business_verified && <p>Verified business</p>}
            {place.is_sample && <p>Editorial sample</p>}
            <p className="text-xs">{place.location_note}</p>
            <Link to={place.detail_path} className="underline block">View current details</Link>
            <a className="underline block" target="_blank" rel="noopener noreferrer"
              href={`https://www.google.com/maps/dir/?api=1&destination=${place.latitude}%2C${place.longitude}`}>Open external directions</a>
          </div></Popup>
        </CircleMarker>)}
      </MapContainer>
    </div> : <p className="text-sm text-ink/65 mt-4">{mapped.length ? 'Map tiles are unavailable. The itinerary stop list is still usable.' : stops.some(stop=>stop.place_id) ? 'No publicly mapped stops appear on this selected day.' : 'Add a location from the Tourismo map or Nearby Discovery to see itinerary pins.'}</p>}
  </section>
}
