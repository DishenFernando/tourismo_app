import {describe,it,expect} from 'vitest'
import {calculateBudget,invalidBudgetItems} from './budget'
import type {TripDraft} from './api'

const example:TripDraft = {
  client_draft_id:'00000000-0000-0000-0000-000000000001',destination_slug:'kandy',title:'Kandy',
  start_date:null,end_date:null,adults:2,children_ages:[8],currency:'LKR',budget_limit_minor:30000,
  budget_flexible:false,itinerary:[],budget_items:[
    {category:'food',description:'Lunch',day:1,minimum_minor:1000,expected_minor:2000,maximum_minor:4000,is_confirmed:false,source_label:'Estimate'},
    {category:'food',description:'Dinner',day:1,minimum_minor:2000,expected_minor:3000,maximum_minor:6000,is_confirmed:true,source_label:'Estimate'},
    {category:'transport',description:'Taxi',day:2,minimum_minor:5000,expected_minor:8000,maximum_minor:13000,is_confirmed:false,source_label:'Estimate'},
    {category:'misc',description:'Whole trip',minimum_minor:100,expected_minor:200,maximum_minor:300,is_confirmed:false,source_label:'Estimate'},
  ]
}

describe('Phase 6 trip budgeting',()=>{
  it('matches API integer sub-totals and preserves unassigned costs',()=>{
    const p=calculateBudget(example)
    expect([p.minimum_minor,p.expected_minor,p.maximum_minor]).toEqual([8100,13200,23300])
    expect(p.by_day.map(day=>[day.day,day.expected_minor])).toEqual([[1,5000],[2,8000]])
    expect(p.by_category.map(cat=>[cat.category,cat.expected_minor])).toEqual([['food',5000],['transport',8000],['misc',200]])
    expect(p.unassigned.expected_minor).toBe(200)
    expect(p.per_traveler_expected_minor).toBe(4400)
    expect(p.remaining_minor).toBe(16800)
  })
  it('detects invalid expense ranges without silently rewriting data',()=>{
    expect(invalidBudgetItems([{...example.budget_items[0],minimum_minor:4000}])).toEqual([1])
    expect(invalidBudgetItems(example.budget_items)).toEqual([])
  })
  it('accepts legacy expenses that have no day',()=>{
    const p=calculateBudget({...example,budget_items:[{...example.budget_items[0],day:undefined}]})
    expect(p.by_day).toEqual([])
    expect(p.unassigned.expected_minor).toBe(2000)
  })
  it('marks max-cost budget-limit overrun, even when expected stays under limit',()=>{
    const p=calculateBudget({...example,budget_limit_minor:20000})
    expect(p.exceeds_limit).toBe(true)
    expect(p.remaining_minor).toBe(6800)
  })
})
