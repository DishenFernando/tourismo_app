import { Plus, Trash2 } from 'lucide-react'
import type { BudgetCategory, BudgetItem, TripDraft, TripPreview } from '../lib/api'
import { budgetCategories, invalidBudgetItems } from '../lib/budget'
import { lkr, toMinor } from '../lib/draft'

type BudgetAmount = 'minimum_minor'|'expected_minor'|'maximum_minor'
const moneyFields: {key:BudgetAmount,label:string}[] = [
  {key:'minimum_minor',label:'Minimum (LKR)'},
  {key:'expected_minor',label:'Expected (LKR)'},
  {key:'maximum_minor',label:'Maximum (LKR)'}
]

export function BudgetEditor({draft,preview,onChange}:{draft:TripDraft;preview:TripPreview;onChange:(value:BudgetItem[])=>void}) {
  const invalid=invalidBudgetItems(draft.budget_items)
  const edit=(index:number,fields:Partial<BudgetItem>)=>onChange(draft.budget_items.map((item,i)=>i===index?{...item,...fields}:item))
  const add=()=>{
    if(draft.budget_items.length>=80)return
    onChange([...draft.budget_items,{
      category:'food',description:'',minimum_minor:0,expected_minor:0,maximum_minor:0,
      is_confirmed:false,source_label:'User-entered estimate',day:null
    }])
  }
  return <div className="space-y-5">
    <p className="help">Plan costs for individual days or keep them unassigned. All values are your own estimates in LKR, not live supplier quotations. Use separate lines for hotel nights, meals, activities or transport.</p>
    <div className="space-y-3">
      {draft.budget_items.map((item,index)=><div key={index} className="rounded-xl bg-[#f2f8f5] p-4 space-y-3">
        <div className="flex gap-3 items-end justify-between flex-wrap">
          <label className="field flex-1 min-w-[160px]"><span>Category</span><select value={item.category} onChange={e=>edit(index,{category:e.target.value as BudgetCategory})}>
            {budgetCategories.map(c=><option value={c.key} key={c.key}>{c.label}</option>)}
          </select></label>
          <label className="field min-w-[125px]"><span>Assigned day</span><select value={item.day ?? 0} onChange={e=>edit(index,{day:Number(e.target.value)||null})}>
            <option value={0}>Whole trip</option>
            {Array.from({length:31},(_,i)=>i+1).map(day=><option key={day} value={day}>Day {day}</option>)}
          </select></label>
          <button type="button" className="text-red-700 p-2" aria-label={`Remove budget line ${index+1}`} onClick={()=>onChange(draft.budget_items.filter((_,i)=>i!==index))}><Trash2 size={19}/></button>
        </div>
        <label className="field"><span>What is this for?</span><input maxLength={160} placeholder="e.g. Two hotel nights, lunch, entrance tickets" value={item.description} onChange={e=>edit(index,{description:e.target.value})}/></label>
        <div className="grid gap-3 sm:grid-cols-3">{moneyFields.map(field=><label key={field.key} className="field"><span>{field.label}</span>
          <input type="number" min={0} max={100000000} step="0.01" value={item[field.key]/100}
            onChange={e=>edit(index,{...item,[field.key]:toMinor(e.target.value)})}/>
        </label>)}</div>
        <button type="button" className="text-sm underline text-pine" onClick={()=>edit(index,{minimum_minor:item.expected_minor,maximum_minor:item.expected_minor})}>Use expected amount for all three values</button>
        {invalid.includes(index+1) && <p role="alert" className="text-sm text-red-700">Minimum must be less than or equal to expected, and expected must not exceed maximum.</p>}
        <div className="grid gap-3 sm:grid-cols-2 items-end">
          <label className="field"><span>Basis of estimate</span><input maxLength={160} value={item.source_label} placeholder="Your estimate / supplier quotation" onChange={e=>edit(index,{source_label:e.target.value})}/></label>
          <label className="flex gap-2 items-center text-sm pb-3"><input type="checkbox" checked={item.is_confirmed} onChange={e=>edit(index,{is_confirmed:e.target.checked})}/><span>I have personally confirmed this estimate</span></label>
        </div>
      </div>)}
    </div>
    <button className="btn-secondary" type="button" disabled={draft.budget_items.length>=80} onClick={add}><Plus size={17}/> Add expense line ({draft.budget_items.length}/80)</button>
    <div className="grid gap-4 md:grid-cols-2">
      <section className="rounded-xl bg-[#f2f8f5] p-4"><h3 className="font-bold">By day</h3>
        {preview.by_day.length ? <ul className="text-sm mt-3 space-y-2">{preview.by_day.map(day=><li key={day.day} className="flex justify-between gap-3"><span>Day {day.day}</span><b>{lkr(day.expected_minor)}</b></li>)}</ul>
          : <p className="help mt-2">Assign an expense to a day to see a daily total.</p>}
        {preview.unassigned.expected_minor>0 && <p className="flex justify-between gap-3 text-sm mt-3 border-t border-ink/10 pt-2"><span>Whole trip / unassigned</span><b>{lkr(preview.unassigned.expected_minor)}</b></p>}
      </section>
      <section className="rounded-xl bg-[#f2f8f5] p-4"><h3 className="font-bold">By category</h3>
        {preview.by_category.length ? <ul className="text-sm mt-3 space-y-2">{preview.by_category.map(item=><li key={item.category} className="flex justify-between gap-3"><span>{budgetCategories.find(c=>c.key===item.category)?.label||item.category}</span><b>{lkr(item.expected_minor)}</b></li>)}</ul>
          : <p className="help mt-2">Add an expense to see category totals.</p>}
      </section>
    </div>
  </div>
}
