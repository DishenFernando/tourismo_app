import type { MapPoint, Stop } from './api'

/** Preserve stable IDs, but never copy coordinates or unreviewed URLs into a private trip. */
export function appendMappedStop(stops:Stop[], place:MapPoint, day:number):Stop[] {
  if (stops.some(stop=>stop.day===day && stop.place_id===place.id) || stops.length>=90) return stops
  return [...stops,{day,title:place.title.slice(0,160),note:'',place_id:place.id}]
}

/** Order is the persisted JSONB array; move only within the same day's stops. */
export function moveStopWithinDay(stops:Stop[], index:number, direction:-1|1):Stop[] {
  const targetDay = stops[index]?.day
  if (targetDay===undefined) return stops
  const indices=stops.map((stop,i)=>stop.day===targetDay?i:-1).filter(i=>i>=0)
  const current=indices.indexOf(index)
  const target=indices[current+direction]
  if (target===undefined) return stops
  const result=[...stops]
  ;[result[index],result[target]]=[result[target],result[index]]
  return result
}
