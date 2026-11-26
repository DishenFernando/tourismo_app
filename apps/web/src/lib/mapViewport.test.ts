import { describe, expect, it } from 'vitest'
import { clusterMapPoints, clipToIsland } from './mapViewport'
import type { MapPoint } from './api'

const make=(i:number):MapPoint=>({id:`destination:${i}`,kind:'destination',title:`Test ${i}`,
  latitude:7.29+i*0.00001,longitude:80.63+i*0.00001,category:'destination',
  district:'Kandy',detail_path:'/destinations/test',is_sample:false,
  business_verified:false,source_url:null,location_note:'Synthetic test point'})

describe('Phase 5.4 viewport and map marker grouping',()=>{
  it('groups 120 nearby synthetic test points at island zoom without data loss',()=>{
    const pins=Array.from({length:120},(_,i)=>make(i))
    const clusters=clusterMapPoints(pins,8)
    expect(clusters.length).toBeLessThan(120)
    expect(clusters.flatMap(c=>c.points).map(p=>p.id).sort()).toEqual(pins.map(p=>p.id).sort())
  })
  it('renders singles at close zoom to preserve per-pin selection',()=>{
    expect(clusterMapPoints([make(0),make(1)],17)).toHaveLength(2)
  })
  it('does not invent points for invalid latitudes',()=>{
    expect(clusterMapPoints([{...make(1),latitude:NaN}],8)).toHaveLength(0)
  })
  it('bounds requests to Sri Lanka and handles map panning outside it',()=>{
    expect(clipToIsland({south:6,west:80,north:8,east:82})).toEqual({south:6,west:80,north:8,east:82})
    expect(clipToIsland({south:-40,west:-50,north:80,east:170})).toEqual({south:5.5,west:79.4,north:10.1,east:82.1})
    expect(clipToIsland({south:35,west:110,north:36,east:111})).toBeNull()
  })
})
