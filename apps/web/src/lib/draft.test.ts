import { describe, expect, it } from 'vitest'
import { calculateLocalPreview, emptyDraft, toMinor } from './draft'

describe('guest budgeting', () => {
  it('converts rupees to exact minor units', () => expect(toMinor('1050.25')).toBe(105025))
  it('sums user-entered ranges without fabricated vendor prices', () => {
    const preview = calculateLocalPreview({ ...emptyDraft, budget_limit_minor: 450000,
      budget_items: [{category:'food', description:'', minimum_minor:100000, expected_minor:300000, maximum_minor:500000,
        is_confirmed:false, source_label:'User-entered estimate'}] })
    expect(preview.expected_minor).toBe(300000)
    expect(preview.exceeds_limit).toBe(true)
    expect(preview.remaining_minor).toBe(150000)
  })
})
