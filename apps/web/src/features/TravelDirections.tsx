import {useEffect, useState} from 'react'
import {CarFront, Footprints, BusFront, Bike, Compass, LocateFixed, ExternalLink} from 'lucide-react'
import {request} from '../lib/api'

type Kind = 'destination'|'service'
type Mode = 'driving'|'walking'|'transit'|'bicycling'
type Coordinates = {latitude:number;longitude:number}
type Target = Coordinates & {kind:Kind;slug:string;title:string;accuracy_note:string;source_url:string|null;is_sample:boolean}
type RouteEstimate = {straight_line_km:number;road_distance_km:number|null;estimated_minutes:number|null;
  estimate_source:string|null;estimate_status:string;checked_at:string;disclaimer:string;mode:Mode}

const modes: {key:Mode;label:string;icon:typeof CarFront}[] = [
  {key:'driving',label:'Drive',icon:CarFront},
  {key:'transit',label:'Bus or train',icon:BusFront},
  {key:'walking',label:'Walk',icon:Footprints},
  {key:'bicycling',label:'Cycle',icon:Bike},
]
function straightKm(a:Coordinates,b:Coordinates){
  const rad=(n:number)=>n*Math.PI/180
  const dLat=rad(b.latitude-a.latitude),dLon=rad(b.longitude-a.longitude)
  const h=Math.sin(dLat/2)**2+Math.cos(rad(a.latitude))*Math.cos(rad(b.latitude))*Math.sin(dLon/2)**2
  return 6371.0088*2*Math.asin(Math.min(1,Math.sqrt(h)))
}
function googleDirections(destination:Coordinates,mode:Mode,origin:Coordinates|null){
  const u=new URL('https://www.google.com/maps/dir/')
  u.searchParams.set('api','1')
  u.searchParams.set('destination',`${destination.latitude},${destination.longitude}`)
  u.searchParams.set('travelmode',mode)
  if(origin)u.searchParams.set('origin',`${origin.latitude},${origin.longitude}`)
  return u.toString()
}

export function TravelDirections({kind,slug}:{kind:Kind;slug:string}){
  const [target,setTarget]=useState<Target|null>(null)
  const [unavailable,setUnavailable]=useState(false)
  const [origin,setOrigin]=useState<Coordinates|null>(null)
  const [mode,setMode]=useState<Mode>('driving')
  const [estimate,setEstimate]=useState<RouteEstimate|null>(null)
  const [message,setMessage]=useState('')
  const [busy,setBusy]=useState(false)
  useEffect(()=>{
    let active=true
    setOrigin(null);setTarget(null);setUnavailable(false);setMessage('');setEstimate(null)
    void request<Target>(`/navigation/targets/${kind}/${encodeURIComponent(slug)}`)
      .then(p=>{if(active)setTarget(p)}).catch(()=>{if(active)setUnavailable(true)})
    return()=>{active=false}
  },[kind,slug])

  function locate(){
    if(!navigator.geolocation){setMessage('This device cannot share a location. Use Google Maps to choose a starting point.');return}
    setBusy(true);setMessage('Getting your location…')
    navigator.geolocation.getCurrentPosition(
      p=>{setOrigin({latitude:p.coords.latitude,longitude:p.coords.longitude});setMessage('Location ready. Tourismo does not save it.');setBusy(false);setEstimate(null)},
      ()=>{setMessage('Location access was not available. You can still open directions and choose your start point in Google Maps.');setBusy(false)},
      {enableHighAccuracy:false,timeout:10000,maximumAge:30000})
  }

  async function getRouteEstimate(){
    if(!origin||!target)return
    setBusy(true);setMessage('Checking with the route provider…');setEstimate(null)
    try{
      const data=await request<RouteEstimate>('/navigation/estimate',{
        method:'POST',body:JSON.stringify({kind,slug,origin_latitude:origin.latitude,origin_longitude:origin.longitude,mode})
      })
      setEstimate(data)
      setMessage(data.estimated_minutes===null?'A verified route estimate was unavailable for this mode. Open Google Maps to explore current routes.':'Route estimate loaded. Actual travel may differ.')
    }catch {setMessage('No route estimate available now. You can still use Google Maps directions.')}
    finally{setBusy(false)}
  }
  if(unavailable)return <section className="form-panel mt-7" aria-label="Directions"><h2 className="text-xl font-bold">Getting there</h2>
    <p className="text-sm mt-2 text-ink/70">A precise location is not yet available for this place. Ask the provider for an entrance or use the map search.</p></section>
  return <section className="form-panel mt-7 space-y-4" aria-label="Getting there and travel directions">
    <div className="flex items-center gap-2"><Compass size={21} className="text-pine"/><h2 className="text-xl font-bold">How to get there</h2></div>
    {!target ? <p role="status" className="text-sm">Looking up a sourced location…</p> : <>
      <p className="text-sm text-ink/70">{target.accuracy_note} {target.is_sample?'This destination still requires editorial review.':''}</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Travel mode">
        {modes.map(m=><button key={m.key} type="button" aria-pressed={mode===m.key}
          className={`${mode===m.key?'btn-primary':'btn-secondary'} min-h-11 text-sm`}
          onClick={()=>{setMode(m.key);setEstimate(null);setMessage('')}}><m.icon size={17}/>{m.label}</button>)}
      </div>
      <button className="btn-secondary min-h-11" type="button" onClick={locate} disabled={busy}><LocateFixed size={17}/>{origin?'Update my location':'Use my location'}</button>
      {origin&&<p className="text-sm text-pine font-semibold">About {straightKm(origin,target).toFixed(1)} km away (straight-line, not road distance)</p>}
      {message&&<p role="status" className="text-sm text-ink/75">{message}</p>}
      <div className="flex flex-wrap gap-3 items-center">
        <a className="btn-primary min-h-11" href={googleDirections(target,mode,origin)} target="_blank" rel="noopener noreferrer">
          <ExternalLink size={17}/> Open {mode==='transit'?'bus/train':'travel'} directions in Google Maps
        </a>
        {origin&&<button type="button" className="btn-secondary min-h-11" onClick={()=>void getRouteEstimate()} disabled={busy}>
          {busy?'Checking route…':'Check route distance & time'}</button>}
      </div>
      {estimate?.estimated_minutes!=null&&estimate.road_distance_km!==null&&<div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4" aria-live="polite">
        <p className="font-bold">{estimate.road_distance_km.toFixed(1)} km by route · about {estimate.estimated_minutes} minutes</p>
        <p className="text-xs mt-1 text-ink/70">Estimate via {estimate.estimate_source}, checked {new Date(estimate.checked_at).toLocaleTimeString()}. Not guaranteed; traffic, service changes and route access may affect travel.</p>
      </div>}
      <p className="text-xs text-ink/65">Sharing your location is optional. It is not stored by Tourismo. Checking an in-app ETA sends coordinates to the routing provider; opening Google Maps uses Google's privacy policy. Transit lines, schedules and fares are only shown when available from the provider. Confirm boarding points and services locally.</p>
    </>}
  </section>
}
