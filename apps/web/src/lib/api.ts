export type DestinationPhoto = {image_url:string; file_page_url:string; photographer:string; license_name:string; license_url:string; alt_text:string}
export type Destination = {
  slug: string; title: string; district: string; province: string;
  summary: string; content_status: string; is_sample: boolean; photo: DestinationPhoto|null
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

export type TourismoProfile = {
  id: string; display_name: string|null; email: string|null; locale: 'en'|'si'|'ta';
  home_region: string|null; bio: string|null; profile_completed: boolean;
  status: string; roles: string[]
}
export type ProfileInput = Pick<TourismoProfile, 'display_name'|'locale'|'home_region'|'bio'>
export const bootstrapProfile = (token:string) => request<TourismoProfile>('/auth/session/bootstrap', {method:'POST'}, token)
export const getProfile = (token:string) => request<TourismoProfile>('/me', {}, token)
export const updateProfile = (values:ProfileInput, token:string) => request<TourismoProfile>('/me', {method:'PATCH',body:JSON.stringify(values)}, token)

export type ContentSource = {
  name: string; url: string|null; license_status: string; verified_at: string|null
}
export type DestinationGuide = {
  destination_slug: string; locale: string; requested_locale: string; fallback_used: boolean;
  overview: string; highlights: string[]; local_tips: string[];
  content_status: string; verified_at: string|null; source: ContentSource|null
}
export type PointOfInterest = {
  slug: string; title: string; category: string; description: string; local_tips: string;
  locale: string; fallback_used: boolean; content_status: string;
  verified_at: string|null; source: ContentSource|null;
  latitude: number|null; longitude: number|null
}
export type ContentLocale = 'en'|'si'|'ta'
export const getDestinationGuide = (slug:string, locale:ContentLocale='en') =>
  request<DestinationGuide>(`/destinations/${encodeURIComponent(slug)}/guide?locale=${locale}`)
export const getDestinationPois = (slug:string, locale:ContentLocale='en') =>
  request<PointOfInterest[]>(`/destinations/${encodeURIComponent(slug)}/pois?locale=${locale}`)
export const getDestinationPhotos = (slug:string) =>
  request<DestinationPhoto[]>(`/destinations/${encodeURIComponent(slug)}/photos`)

export type AdminGuide = {locale:ContentLocale;overview:string;highlights:string[];local_tips:string[];source_name:string;source_url:string;content_status:string}
export const adminDestinations = (token:string) => request<Destination[]>('/admin/destinations',{},token)
export const adminGuide = (slug:string, token:string, locale:ContentLocale='en') => request<AdminGuide>(`/admin/destinations/${encodeURIComponent(slug)}/guide?locale=${locale}`,{},token)
export const createAdminDestination = (body:Record<string,string>, token:string) => request<Destination>('/admin/destinations',{method:'POST',body:JSON.stringify(body)},token)
export const saveAdminGuide = (slug:string, body:Omit<AdminGuide,'content_status'>, token:string) => request<{status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/guide`,{method:'PUT',body:JSON.stringify(body)},token)
export const createAdminPoi = (slug:string, body:Record<string,string|number>, token:string) => request<{slug:string}>(`/admin/destinations/${encodeURIComponent(slug)}/pois`,{method:'POST',body:JSON.stringify(body)},token)
export const publishAdminDestination = (slug:string, token:string) => request<{content_status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/publish`,{method:'POST'},token)
export const attachAdminPhoto = (slug:string, body:Record<string,string>, token:string) => request<{image_url:string}>(`/admin/destinations/${encodeURIComponent(slug)}/photos`,{method:'POST',body:JSON.stringify(body)},token)

export type AdminPoi = {slug:string;title:string;content_status:string;has_source:boolean;latitude:number|null;longitude:number|null}
export const listAdminPois=(slug:string,token:string)=>request<AdminPoi[]>(`/admin/destinations/${encodeURIComponent(slug)}/pois`,{},token)
export const publishAdminPoi=(slug:string,poi:string,token:string)=>request<{content_status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/pois/${encodeURIComponent(poi)}/publish`,{method:'POST'},token)


export type ReviewItem = {kind:'guide'|'poi';destination_slug:string;locale?:ContentLocale;poi_slug?:string;status:string;has_source:boolean}
export const reviewQueue=(token:string)=>request<ReviewItem[]>('/admin/review-queue',{},token)
export const submitAdminGuide=(slug:string,locale:ContentLocale,token:string)=>request<{content_status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/guide/submit?locale=${locale}`,{method:'POST'},token)
export const submitAdminPoi=(slug:string,poi:string,token:string)=>request<{content_status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/pois/${encodeURIComponent(poi)}/submit`,{method:'POST'},token)
export const requestGuideChanges=(slug:string,locale:ContentLocale,reason:string,token:string)=>request<{content_status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/guide/request-changes?locale=${locale}`,{method:'POST',body:JSON.stringify({reason})},token)
export const requestPoiChanges=(slug:string,poi:string,reason:string,token:string)=>request<{content_status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/pois/${encodeURIComponent(poi)}/request-changes`,{method:'POST',body:JSON.stringify({reason})},token)

export const approveAdminGuide=(slug:string,locale:ContentLocale,token:string)=>request<{content_status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/guide/approve?locale=${locale}`,{method:'POST'},token)

export type ContentAuditDestination = {
  slug: string; title: string; status: string; photo_count: number;
  approved_poi_count: number; reviewed_locales: string[]; missing: string[]
}
export type ContentAudit = {
  total: number; published: number; sample: number; needs_attention: number;
  destinations: ContentAuditDestination[]
}
export const getContentAudit = (token:string) => request<ContentAudit>('/admin/content-audit', {}, token)

// Phase 3.1: private business applications. These payloads MUST NOT be used for public listings.
export type VendorCategory = 'accommodation'|'restaurant'|'guide'|'transport'|'tour_operator'|'activity'
export type VendorState = 'draft'|'submitted'|'changes_requested'|'approved'|'rejected'
export type VendorOrganization = {
  id:string; owner_id:string; category:VendorCategory; business_name:string;
  registration_no:string|null; contact_email:string; contact_phone:string|null;
  province:string; district:string; operating_address:string; license_no:string|null;
  verification_state:VendorState; reviewed_at:string|null; review_feedback:string|null; created_at:string|null;
  has_public_listing:boolean; subscription_trial_started:boolean
}
export type VendorApplication = {
  category:VendorCategory; business_name:string; registration_no:string|null;
  contact_email:string; contact_phone:string|null; province:string; district:string;
  operating_address:string; license_no:string|null
}
export type VendorEvidence = {
  id:string; evidence_type:'business_registration'|'tourism_license'|'professional_license'|'other_permit';
  issuer:string; reference_number:string; expires_on:string|null
}
export type VendorMember = {id:string; user_id:string; role:'owner'|'manager'|'staff'; state:'pending'|'active'|'revoked'}
export type VendorCheck = {decision:string;reason:string;source_url:string|null;checked_at:string|null}
export type VendorCase = {organization:VendorOrganization; evidence:VendorEvidence[]; history:VendorCheck[]}
export type VendorInvitation = {id:string;organization_id:string;role:string;state:string}
export const vendorOrganizations = (token:string)=>request<VendorOrganization[]>('/vendor/organizations',{},token)
export const createVendorOrganization = (body:VendorApplication,token:string)=>request<VendorOrganization>('/vendor/organizations',{method:'POST',body:JSON.stringify(body)},token)
export const editVendorOrganization = (id:string,body:Partial<Omit<VendorApplication,'category'>>,token:string)=>request<VendorOrganization>(`/vendor/organizations/${id}`,{method:'PATCH',body:JSON.stringify(body)},token)
export const vendorEvidence = (id:string,token:string)=>request<VendorEvidence[]>(`/vendor/organizations/${id}/evidence`,{},token)
export const addVendorEvidence = (id:string,body:Omit<VendorEvidence,'id'>,token:string)=>request<VendorEvidence>(`/vendor/organizations/${id}/evidence`,{method:'POST',body:JSON.stringify(body)},token)
export const submitVendorOrganization = (id:string,token:string)=>request<VendorOrganization>(`/vendor/organizations/${id}/submit`,{method:'POST'},token)
export const vendorMembers = (id:string,token:string)=>request<VendorMember[]>(`/vendor/organizations/${id}/members`,{},token)
export const inviteVendorMember = (id:string,user_id:string,role:'manager'|'staff',token:string)=>request<{id:string;state:string}>(`/vendor/organizations/${id}/members`,{method:'POST',body:JSON.stringify({user_id,role})},token)
export const vendorInvitations = (token:string)=>request<VendorInvitation[]>('/vendor/invitations',{},token)
export const acceptVendorInvitation = (id:string,token:string)=>request<{state:string}>(`/vendor/invitations/${id}/accept`,{method:'POST'},token)
export const vendorReviewQueue = (token:string,state:VendorState='submitted')=>request<VendorOrganization[]>(`/admin/vendor-verifications?state=${state}`,{},token)
export const vendorReviewCase = (id:string,token:string)=>request<VendorCase>(`/admin/vendor-verifications/${id}`,{},token)
export const vendorDecision = (id:string,decision:'approved'|'rejected'|'changes_requested',reason:string,source_url:string|null,token:string)=>request<VendorOrganization>(`/admin/vendor-verifications/${id}/decision`,{method:'POST',body:JSON.stringify({decision,reason,source_url})},token)
