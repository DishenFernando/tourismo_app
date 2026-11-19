export type Destination = {
  slug: string; title: string; district: string; province: string;
  summary: string; content_status: string; is_sample: boolean
}
export type BudgetCategory = 'accommodation'|'transport'|'food'|'entry_fees'|'guides'|'activities'|'misc'|'contingency'
export type BudgetItem = {
  category: BudgetCategory; description: string; minimum_minor: number;
  expected_minor: number; maximum_minor: number; is_confirmed: boolean; source_label: string
}
export type Stop = { day: number; title: string; note: string }
export type TripDraft = {
  client_draft_id: string;
  destination_slug: string; title: string; start_date: string|null; end_date: string|null;
  adults: number; children_ages: number[]; currency: 'LKR'; budget_limit_minor: number|null;
  budget_flexible: boolean; budget_items: BudgetItem[]; itinerary: Stop[]
}
export type TripPreview = {
  minimum_minor: number; expected_minor: number; maximum_minor: number;
  remaining_minor: number|null; exceeds_limit: boolean; currency: string; estimated_not_quoted: boolean
}
export type SavedTrip = { id: string; draft: TripDraft; preview: TripPreview }

export async function request<T>(path: string, options: RequestInit = {}, token?: string|null): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: { ...(options.body ? {'Content-Type': 'application/json'} : {}),
      ...(token ? {Authorization: `Bearer ${token}`} : {}), ...options.headers }
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : message }
    catch { /* transport error without JSON body */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const getDestinations = (query = '') => request<Destination[]>(`/destinations?q=${encodeURIComponent(query)}`)
export const previewTrip = (draft: TripDraft) => request<TripPreview>('/trips/preview', {method:'POST', body:JSON.stringify(draft)})
export const saveTrip = (draft: TripDraft, token: string) => request<SavedTrip>('/trips', {method:'POST', body:JSON.stringify(draft)}, token)
export const savedTrips = (token: string) => request<SavedTrip[]>('/trips', {}, token)
