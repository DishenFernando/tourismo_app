/** Tourismo Phase 5.4: deterministic, dependency-free viewport/grid clustering.
 * Only screen-facing visualization; never manufactures or changes coordinates.
 */
import type { MapPoint } from './api'

export type ViewportBounds = { south:number; west:number; north:number; east:number }
export type PinCluster = { key:string; latitude:number; longitude:number; points:MapPoint[] }
export const ISLAND_BOUNDS: ViewportBounds = {south:5.5,west:79.4,north:10.1,east:82.1}

export function clipToIsland(bounds:ViewportBounds):ViewportBounds|null{
  const clipped={south:Math.max(bounds.south,ISLAND_BOUNDS.south),
    west:Math.max(bounds.west,ISLAND_BOUNDS.west),
    north:Math.min(bounds.north,ISLAND_BOUNDS.north),
    east:Math.min(bounds.east,ISLAND_BOUNDS.east)}
  if(!Object.values(clipped).every(Number.isFinite) || clipped.south>=clipped.north || clipped.west>=clipped.east)return null
  return clipped
}

/** World-pixel coordinates for a Web Mercator tile map at zoom level z. */
function pixel(lat:number,lon:number,zoom:number){
  const latitude=Math.min(85.05112878,Math.max(-85.05112878,lat))
  const sine=Math.sin(latitude*Math.PI/180)
  const scale=256*2**Math.min(19,Math.max(0,Math.floor(zoom)))
  return {x:(lon+180)/360*scale,
    y:(0.5-Math.log((1+sine)/(1-sine))/(4*Math.PI))*scale}
}

/** At close zoom levels individual overlapping markers remain selectable via the list. */
export function clusterMapPoints(points:MapPoint[],zoom:number,cellPixels=54):PinCluster[]{
  if(!Number.isFinite(zoom) || !Number.isFinite(cellPixels) || cellPixels<1)return []
  if(zoom>=17)return points.map(p=>({key:p.id,latitude:p.latitude,longitude:p.longitude,points:[p]}))
  const cells=new Map<string,MapPoint[]>()
  for(const point of points){
    if(!Number.isFinite(point.latitude)||!Number.isFinite(point.longitude))continue
    const p=pixel(point.latitude,point.longitude,zoom)
    const key=`${Math.floor(p.x/cellPixels)}:${Math.floor(p.y/cellPixels)}`
    const cell=cells.get(key)||[]
    cell.push(point)
    cells.set(key,cell)
  }
  return [...cells.entries()].map(([key,items])=>({
    key,points:items,latitude:items.reduce((n,p)=>n+p.latitude,0)/items.length,
    longitude:items.reduce((n,p)=>n+p.longitude,0)/items.length
  }))
}
