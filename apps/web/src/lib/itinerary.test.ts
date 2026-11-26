import { describe, expect, it } from 'vitest'
import { appendMappedStop, moveStopWithinDay } from './itinerary'
import type { Stop, MapPoint } from './api'

const point:MapPoint={
  id:'attraction:00000000-0000-0000-0000-000000000001',kind:'attraction',title:'Temple of the Tooth',
  latitude:7.294,longitude:80.641,category:'heritage',district:'Kandy',detail_path:'/destinations/kandy',
  is_sample:false,business_verified:false,location_note:'Approximate',source_url:null,
}

describe('Phase 5.3 guest itinerary',()=>{
  it('adds a public place with a stable reference, without persisting coordinates or provider metadata',()=>{
    const result=appendMappedStop([],point,2)
    expect(result).toEqual([{day:2,title:point.title,note:'',place_id:point.id}])
    expect(JSON.stringify(result)).not.toContain('latitude')
  })
  it('deduplicates a place within one day but permits revisiting on another day',()=>{
    const first=appendMappedStop([],point,1)
    expect(appendMappedStop(first,point,1)).toBe(first)
    expect(appendMappedStop(first,point,2)).toHaveLength(2)
  })
  it('preserves the ninety-stop limit',()=>{
    const stops=Array.from({length:90},(_,i)=>({day:1,title:`Stop ${i}`,note:''}))
    expect(appendMappedStop(stops,point,1)).toBe(stops)
  })
  it('moves stops within their own day, not across days',()=>{
    const stops:Stop[]=[{day:1,title:'A',note:''},{day:2,title:'B',note:''},{day:1,title:'C',note:''}]
    expect(moveStopWithinDay(stops,0,1).map(s=>s.title)).toEqual(['C','B','A'])
    expect(moveStopWithinDay(stops,1,1)).toBe(stops)
    expect(stops[0].title).toBe('A')
  })
})
