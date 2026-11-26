import type { BudgetCategory, BudgetItem, BudgetSubtotal, CategorySubtotal, DaySubtotal, TripDraft, TripPreview } from './api'

export const budgetCategories: {key:BudgetCategory,label:string}[] = [
  {key:'accommodation',label:'Accommodation'}, {key:'transport',label:'Transport'},
  {key:'food',label:'Food & dining'}, {key:'entry_fees',label:'Entry fees'},
  {key:'guides',label:'Guides'}, {key:'activities',label:'Activities'},
  {key:'misc',label:'Other'}, {key:'contingency',label:'Contingency'}
]

function amounts(): BudgetSubtotal {return {minimum_minor:0,expected_minor:0,maximum_minor:0}}
function add(to:BudgetSubtotal, item:BudgetItem):void {
  to.minimum_minor+=item.minimum_minor
  to.expected_minor+=item.expected_minor
  to.maximum_minor+=item.maximum_minor
}

// Mirror the API integer-minor-unit calculation. No provider prices are injected.
export function calculateBudget(draft:TripDraft):TripPreview {
  const totals=amounts(), unassigned=amounts()
  const byCategory=new Map<BudgetCategory,CategorySubtotal>()
  const byDay=new Map<number,DaySubtotal>()
  for(const item of draft.budget_items) {
    add(totals,item)
    if(!byCategory.has(item.category)) byCategory.set(item.category,{category:item.category,...amounts()})
    add(byCategory.get(item.category)!,item)
    if(item.day == null) add(unassigned,item)
    else {
      if(!byDay.has(item.day)) byDay.set(item.day,{day:item.day,...amounts()})
      add(byDay.get(item.day)!,item)
    }
  }
  const people=draft.adults+draft.children_ages.length
  const limit=draft.budget_limit_minor
  return {...totals,
    remaining_minor:limit===null?null:limit-totals.expected_minor,
    exceeds_limit:limit!==null && totals.maximum_minor>limit,
    currency:'LKR',estimated_not_quoted:true,
    per_traveler_expected_minor:Math.floor((totals.expected_minor+Math.floor(people/2))/people),
    by_category:[...byCategory.values()],
    by_day:[...byDay.values()].sort((a,b)=>a.day-b.day),unassigned}
}

export function invalidBudgetItems(items:BudgetItem[]):number[] {
  return items.flatMap((item,i)=>item.minimum_minor<=item.expected_minor && item.expected_minor<=item.maximum_minor ? [] : [i+1])
}
