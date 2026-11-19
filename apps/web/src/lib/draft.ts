import type { TripDraft, TripPreview } from './api'

export const DRAFT_KEY = 'tourismo.temporary-draft.v1'
export const PENDING_SAVE_KEY = 'tourismo.pending-save-confirmation.v1'

export const emptyDraft: TripDraft = {
  client_draft_id: crypto.randomUUID(), destination_slug: 'nuwara-eliya', title: 'My Sri Lanka adventure',
  start_date: null, end_date: null, adults: 2, children_ages: [],
  currency: 'LKR', budget_limit_minor: null, budget_flexible: false,
  budget_items: [], itinerary: []
}

export function readDraft(): TripDraft {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY)
    if (raw) return { ...emptyDraft, ...JSON.parse(raw) as TripDraft }
  } catch { /* private-browser storage may be blocked */ }
  return structuredClone(emptyDraft)
}
export function persistDraft(draft: TripDraft): void {
  try { sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft)) } catch { /* degraded session storage */ }
}
export function clearDraft(): void {
  try { sessionStorage.removeItem(DRAFT_KEY); sessionStorage.removeItem(PENDING_SAVE_KEY) }
  catch { /* degraded session storage */ }
}
export function calculateLocalPreview(draft: TripDraft): TripPreview {
  const minimum_minor = draft.budget_items.reduce((sum, item) => sum + item.minimum_minor, 0)
  const expected_minor = draft.budget_items.reduce((sum, item) => sum + item.expected_minor, 0)
  const maximum_minor = draft.budget_items.reduce((sum, item) => sum + item.maximum_minor, 0)
  return { minimum_minor, expected_minor, maximum_minor,
    remaining_minor: draft.budget_limit_minor === null ? null : draft.budget_limit_minor-expected_minor,
    exceeds_limit: draft.budget_limit_minor !== null && maximum_minor > draft.budget_limit_minor,
    currency:'LKR', estimated_not_quoted: true }
}
export const lkr = (minor:number) => new Intl.NumberFormat('en-LK', {style:'currency', currency:'LKR', maximumFractionDigits:0}).format(minor/100)
export const toMinor = (rupees: string | number): number => Math.round(Math.max(0, Number(rupees)||0) * 100)
