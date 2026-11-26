export type DestinationPhoto = {image_url:string; file_page_url:string; photographer:string; license_name:string; license_url:string; alt_text:string; media_kind?:'commons_photo'|'owned_photo'|'ai_illustration'}
export type Destination = {
  slug: string; title: string; district: string; province: string;
  summary: string; content_status: string; is_sample: boolean; photo: DestinationPhoto|null; location_source_url?:string|null
}
export type BudgetCategory = 'accommodation'|'transport'|'food'|'entry_fees'|'guides'|'activities'|'misc'|'contingency'
export type BudgetItem = {
  category: BudgetCategory; description: string; minimum_minor: number;
  expected_minor: number; maximum_minor: number; is_confirmed: boolean; source_label: string; day?: number|null
}
export type Stop = { day: number; title: string; note: string; place_id?: string|null }
export type TripDraft = {
  client_draft_id: string;
  destination_slug: string; title: string; start_date: string|null; end_date: string|null;
  adults: number; children_ages: number[]; currency: 'LKR'; budget_limit_minor: number|null;
  budget_flexible: boolean; budget_items: BudgetItem[]; itinerary: Stop[]
}
export type BudgetSubtotal = {minimum_minor:number; expected_minor:number; maximum_minor:number}
export type CategorySubtotal = BudgetSubtotal & {category:BudgetCategory}
export type DaySubtotal = BudgetSubtotal & {day:number}
export type TripPreview = {
  minimum_minor: number; expected_minor: number; maximum_minor: number;
  remaining_minor: number|null; exceeds_limit: boolean; currency: string; estimated_not_quoted: boolean;
  per_traveler_expected_minor: number; by_category:CategorySubtotal[]; by_day:DaySubtotal[]; unassigned:BudgetSubtotal
}
export type SavedTrip = { id: string; version: number; draft: TripDraft; preview: TripPreview }

export class ApiError extends Error {
  constructor(message:string, public readonly status:number) {super(message);this.name='ApiError'}
}

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
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}

export const getDestinations = (query = '') => request<Destination[]>(`/destinations?q=${encodeURIComponent(query)}`)
export const previewTrip = (draft: TripDraft) => request<TripPreview>('/trips/preview', {method:'POST', body:JSON.stringify(draft)})
export const saveTrip = (draft: TripDraft, token: string) => request<SavedTrip>('/trips', {method:'POST', body:JSON.stringify(draft)}, token)
export const savedTrips = (token: string) => request<SavedTrip[]>('/trips', {}, token)
export const savedTrip = (id:string, token:string) => request<SavedTrip>(`/trips/${encodeURIComponent(id)}`, {}, token)
export const deleteSavedTrip = async (id:string, token:string):Promise<void> => {
  const response=await fetch(`/api/v1/trips/${encodeURIComponent(id)}`,{method:'DELETE',headers:{Authorization:`Bearer ${token}`}})
  if(!response.ok)throw new ApiError('Unable to delete trip',response.status)
}
export const updateSavedTrip = (id:string, expectedVersion:number, draft:TripDraft, token:string) =>
  request<SavedTrip>(`/trips/${encodeURIComponent(id)}`,
    {method:'PATCH', body:JSON.stringify({expected_version:expectedVersion, draft})}, token)

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
export type LocationInput = {latitude?:number|null;longitude?:number|null;location_source_url?:string|null}
export type DestinationCreate = {slug:string;title:string;district:string;province:string;summary:string} & LocationInput
export type DestinationLocation = {latitude:number|null;longitude:number|null;location_source_url:string|null;content_status:string}
export const getAdminDestinationLocation = (slug:string, token:string) => request<DestinationLocation>(`/admin/destinations/${encodeURIComponent(slug)}/location`,{},token)
export const updateAdminDestinationLocation = (slug:string, body:LocationInput, token:string) => request<{status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/location`,{method:'PATCH',body:JSON.stringify(body)},token)
export const updateAdminPoiLocation = (slug:string, poiSlug:string, body:LocationInput, token:string) => request<{status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/pois/${encodeURIComponent(poiSlug)}/location`,{method:'PATCH',body:JSON.stringify(body)},token)
export const createAdminDestination = (body:DestinationCreate, token:string) => request<Destination>('/admin/destinations',{method:'POST',body:JSON.stringify(body)},token)
export const saveAdminGuide = (slug:string, body:Omit<AdminGuide,'content_status'>, token:string) => request<{status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/guide`,{method:'PUT',body:JSON.stringify(body)},token)
export const createAdminPoi = (slug:string, body:Record<string,string|number|null>, token:string) => request<{slug:string}>(`/admin/destinations/${encodeURIComponent(slug)}/pois`,{method:'POST',body:JSON.stringify(body)},token)
export const publishAdminDestination = (slug:string, token:string) => request<{content_status:string}>(`/admin/destinations/${encodeURIComponent(slug)}/publish`,{method:'POST'},token)
export const attachAdminPhoto = (slug:string, body:Record<string,string>, token:string) => request<{image_url:string}>(`/admin/destinations/${encodeURIComponent(slug)}/photos`,{method:'POST',body:JSON.stringify(body)},token)

export async function uploadAdminDestinationImage(slug:string, file:File, kind:'owned_photo'|'ai_illustration', creator:string, altText:string, token:string):Promise<{image_url:string;media_kind:string}> {
  const form = new FormData()
  form.append('file', file)
  form.append('kind', kind)
  form.append('creator', creator)
  form.append('alt_text', altText)
  form.append('rights_confirmed', 'true')
  const response = await fetch(`/api/v1/admin/destinations/${encodeURIComponent(slug)}/photos/upload`, {
    method:'POST', headers:{Authorization:`Bearer ${token}`}, body:form
  })
  if (!response.ok) {
    let detail = `Upload failed (${response.status})`
    try {const payload = await response.json(); if (typeof payload.detail === 'string') detail = payload.detail} catch { /* non-JSON error */ }
    throw new Error(detail)
  }
  return response.json()
}

export type AdminPoi = {slug:string;title:string;content_status:string;has_source:boolean;latitude:number|null;longitude:number|null;location_source_url?:string|null}
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
export type VendorState = 'draft'|'submitted'|'changes_requested'|'approved'|'rejected'|'expired_license'
export type VendorOrganization = {
  id:string; owner_id:string; category:VendorCategory; business_name:string;
  registration_no:string|null; contact_email:string; contact_phone:string|null;
  province:string|null; district:string|null; operating_address:string|null; license_no:string|null;
  verification_state:VendorState; reviewed_at:string|null; review_feedback:string|null; created_at:string|null;
  has_public_listing:boolean; subscription_trial_started:boolean
}
export type VendorApplication = {
  category:VendorCategory; business_name:string; registration_no:string|null;
  contact_email:string; contact_phone:string|null; province:string|null; district:string|null;
  operating_address:string|null; license_no:string|null
}
export type VendorEvidence = {
  id:string; evidence_type:'business_registration'|'tourism_license'|'professional_license'|'other_permit';
  issuer:string; reference_number:string; expires_on:string|null
}
export type VendorMember = {id:string; user_id:string; role:'owner'|'manager'|'staff'; state:'pending'|'active'|'revoked'}
export type VendorCheck = {decision:string;reason:string;source_url:string|null;checked_at:string|null}
export type VendorCase = {organization:VendorOrganization; evidence:VendorEvidence[]; history:VendorCheck[]; documents:VendorDocument[]}
export type VendorInvitation = {id:string;organization_id:string;role:string;state:string}
export const vendorOrganizations = (token:string)=>request<VendorOrganization[]>('/vendor/organizations',{},token)
export const createVendorOrganization = (body:VendorApplication,token:string)=>request<VendorOrganization>('/vendor/organizations',{method:'POST',body:JSON.stringify(body)},token)
export const editVendorOrganization = (id:string,body:Partial<Omit<VendorApplication,'category'>>,token:string)=>request<VendorOrganization>(`/vendor/organizations/${id}`,{method:'PATCH',body:JSON.stringify(body)},token)
export const vendorEvidence = (id:string,token:string)=>request<VendorEvidence[]>(`/vendor/organizations/${id}/evidence`,{},token)
export const addVendorEvidence = (id:string,body:Omit<VendorEvidence,'id'>,token:string)=>request<VendorEvidence>(`/vendor/organizations/${id}/evidence`,{method:'POST',body:JSON.stringify(body)},token)
export const submitVendorOrganization = (id:string,token:string)=>request<VendorOrganization>(`/vendor/organizations/${id}/submit`,{method:'POST'},token)
export const vendorMembers = (id:string,token:string)=>request<VendorMember[]>(`/vendor/organizations/${id}/members`,{},token)
export const inviteVendorMemberByEmail = (id:string,email:string,role:'manager'|'staff',token:string)=>request<{id:string;state:string}>(`/vendor/organizations/${id}/members/by-email`,{method:'POST',body:JSON.stringify({email,role})},token)
export const inviteVendorMember = (id:string,user_id:string,role:'manager'|'staff',token:string)=>request<{id:string;state:string}>(`/vendor/organizations/${id}/members`,{method:'POST',body:JSON.stringify({user_id,role})},token)
export const vendorInvitations = (token:string)=>request<VendorInvitation[]>('/vendor/invitations',{},token)
export const acceptVendorInvitation = (id:string,token:string)=>request<{state:string}>(`/vendor/invitations/${id}/accept`,{method:'POST'},token)
export const vendorReviewQueue = (token:string,state:VendorState='submitted')=>request<VendorOrganization[]>(`/admin/vendor-verifications?state=${state}`,{},token)
export const vendorReviewCase = (id:string,token:string)=>request<VendorCase>(`/admin/vendor-verifications/${id}`,{},token)
export const vendorDecision = (id:string,decision:'approved'|'rejected'|'changes_requested',reason:string,source_url:string|null,token:string)=>request<VendorOrganization>(`/admin/vendor-verifications/${id}/decision`,{method:'POST',body:JSON.stringify({decision,reason,source_url})},token)


// Phase 3.2 - private attachments. Never expose a public direct file URL.
export type VendorDocument = {
  id:string; evidence_id:string; name:string; media_type:string; size_bytes:number;
  scan_state:'pending_scan'|'clean'|'infected'; uploaded_at:string|null; downloadable:boolean
}
export type VendorCompliance = {verification_state:VendorState;expired_evidence_ids:string[];verification_current:boolean;renewal_required:boolean}
export const vendorDocuments=(orgId:string,token:string)=>request<VendorDocument[]>(`/vendor/organizations/${orgId}/documents`,{},token)
export const vendorCompliance=(orgId:string,token:string)=>request<VendorCompliance>(`/vendor/organizations/${orgId}/compliance`,{},token)
export const startVendorRenewal=(orgId:string,token:string)=>request<VendorOrganization>(`/vendor/organizations/${orgId}/start-renewal`,{method:'POST'},token)
export async function uploadServiceListingPhoto(orgId:string,listingId:string,file:File,creator:string,altText:string,token:string):Promise<ListingPhotoWrite> {
  const form=new FormData()
  form.append('file',file);form.append('creator',creator);form.append('alt_text',altText);form.append('rights_confirmed','true')
  const res=await fetch(`/api/v1/vendor/organizations/${orgId}/listings/${listingId}/photos/upload`,{
    method:'POST',headers:{Authorization:`Bearer ${token}`},body:form
  })
  if(!res.ok){const body=await res.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:`Upload failed (${res.status})`)}
  return res.json()
}

export async function uploadVendorDocument(orgId:string,evidenceId:string,file:File,token:string):Promise<VendorDocument> {
  const form = new FormData();form.append('evidence_id',evidenceId);form.append('file',file)
  const response=await fetch(`/api/v1/vendor/organizations/${orgId}/documents`,{
    method:'POST',headers:{Authorization:`Bearer ${token}`},body:form
  })
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:`Upload failed (${response.status})`)}
  return response.json() as Promise<VendorDocument>
}
export const deleteVendorDocument=(orgId:string,docId:string,token:string)=>
  fetch(`/api/v1/vendor/organizations/${orgId}/documents/${docId}`,{
    method:'DELETE',headers:{Authorization:`Bearer ${token}`}
  }).then(async response=>{if(!response.ok)throw new Error(`Delete failed (${response.status})`)})
export async function downloadVendorDocument(orgId:string,docId:string,token:string,admin=false):Promise<void> {
  const prefix=admin?'/admin/vendor-verifications/':'/vendor/organizations/'
  const response=await fetch(`/api/v1${prefix}${orgId}/documents/${docId}/download`,{
    headers:{Authorization:`Bearer ${token}`},cache:'no-store'
  })
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:`Download unavailable (${response.status})`)}
  const url=URL.createObjectURL(await response.blob());
  try {const link=document.createElement('a');link.href=url;link.download='tourismo-vendor-evidence';link.click()}
  finally {window.setTimeout(()=>URL.revokeObjectURL(url),10000)}
}

// Phase 4.1 — service discovery is separate from private vendor verification.
export type ListingPhoto = {
  id:string; image_url:string; source_url:string; credit:string;
  license_name:string; license_url:string; alt_text:string
}
export type ListingCategory = VendorCategory
export type ListingStatus = 'draft'|'submitted'|'changes_requested'|'published'|'archived'
export type ServiceListing = {
  id:string; slug:string; category:ListingCategory; title:string; summary:string;
  description:string; province:string; district:string; details:Record<string,unknown>;
  public_email:string|null; public_phone:string|null; photos:ListingPhoto[];
  latitude:number|null; longitude:number|null; location_source_url:string|null; location_note:string|null;
  status:ListingStatus; prices_are_indicative:boolean; booking_available:false;
  business_name?:string|null; business_verified?:boolean;
  organization_id?:string; review_feedback?:string|null; published_at?:string|null;
  revision?:ListingRevision|null;
  is_demo?:boolean; demo_disclaimer?:string; distance_km?:number
}
export type ListingWrite = Pick<ServiceListing,'title'|'summary'|'description'|'public_email'|'public_phone'|'details'> & {
  latitude?:number|null; longitude?:number|null; location_source_url?:string|null; location_note?:string|null
}
export type ListingRevisionWrite = ListingWrite & {photos?:ListingPhotoWrite[]}
export type ListingRevision = {
  id:string; listing_id:string; status:'draft'|'submitted'|'changes_requested'|'approved';
  snapshot:ListingRevisionWrite; review_feedback:string|null; created_at:string|null;
  live_title?:string; organization_id?:string
}
export type FamilyFit = {adults:number;child_ages:number[];any_room_may_fit:boolean;
  rooms:{room_name:string;may_fit:boolean;age_policy_specified:boolean;max_adults:number;max_children:number}[];disclaimer:string}

export type ListingPhotoWrite = Omit<ListingPhoto,'id'>
export type PublicListingFilters = {
  category?:string; province?:string; district?:string; destination?:string; q?:string;
  adults?:number; child_ages?:number[]; near_lat?:number; near_lon?:number;
  radius_km?:number; sort?:'recent'|'distance'; limit?:number; offset?:number;
}
export const publicListings=(options:PublicListingFilters={})=>{
  const p=new URLSearchParams()
  Object.entries(options).forEach(([k,v])=>{
    if(Array.isArray(v))v.forEach(age=>p.append(k,String(age)))
    else if(v!==undefined&&v!==null&&v!=='')p.set(k,String(v))
  })
  return request<ServiceListing[]>(`/listings?${p.toString()}`)
}
export const publicListing=(slug:string)=>request<ServiceListing>(`/listings/${encodeURIComponent(slug)}`)
// These endpoints are permanently disabled outside a development environment.
export const demoCatalogStatus=()=>request<{enabled:boolean}>('/demo/status')
export const demoListings=(options:Pick<PublicListingFilters,'category'|'province'|'district'|'destination'|'q'|'adults'|'child_ages'>={})=>{
  const p=new URLSearchParams()
  Object.entries(options).forEach(([k,v])=>{
    if(Array.isArray(v))v.forEach(age=>p.append(k,String(age)))
    else if(v!==undefined&&v!==null&&v!=='')p.set(k,String(v))
  })
  return request<ServiceListing[]>(`/demo/listings?${p.toString()}`)
}
export const demoListing=(slug:string)=>request<ServiceListing>(`/demo/listings/${encodeURIComponent(slug)}`)
export const myServiceListings=(orgId:string,token:string)=>request<ServiceListing[]>(`/vendor/organizations/${orgId}/listings`,{},token)
export const quickStartServiceListing=(orgId:string,title:string,token:string)=>request<ServiceListing>(`/vendor/organizations/${orgId}/listings/quick-start`,{method:'POST',body:JSON.stringify({title})},token)
export const createServiceListing=(orgId:string,body:ListingWrite,token:string)=>request<ServiceListing>(`/vendor/organizations/${orgId}/listings`,{method:'POST',body:JSON.stringify(body)},token)
export const updateServiceListing=(orgId:string,id:string,body:ListingWrite,token:string)=>request<ServiceListing>(`/vendor/organizations/${orgId}/listings/${id}`,{method:'PUT',body:JSON.stringify(body)},token)
export const addServicePhoto=(orgId:string,id:string,body:ListingPhotoWrite,token:string)=>request<ListingPhoto>(`/vendor/organizations/${orgId}/listings/${id}/photos`,{method:'POST',body:JSON.stringify(body)},token)
export const removeServicePhoto=(orgId:string,id:string,photoId:string,token:string)=>request<{removed:boolean}>(`/vendor/organizations/${orgId}/listings/${id}/photos/${photoId}`,{method:'DELETE'},token)
export const submitServiceListing=(orgId:string,id:string,token:string)=>request<ServiceListing>(`/vendor/organizations/${orgId}/listings/${id}/submit`,{method:'POST'},token)
export const archiveServiceListing=(orgId:string,id:string,token:string)=>request<ServiceListing>(`/vendor/organizations/${orgId}/listings/${id}/archive`,{method:'POST'},token)
export const listingReviewQueue=(token:string,status:'submitted'|'published'|'changes_requested'='submitted')=>request<ServiceListing[]>(`/admin/listings?status=${status}`,{},token)
export const decideServiceListing=(id:string,decision:'published'|'changes_requested',reason:string,token:string)=>request<ServiceListing>(`/admin/listings/${id}/decision`,{method:'POST',body:JSON.stringify({decision,reason})},token)

// Phase 4.2: safe published-listing revisions and non-booking family guidance.
export const familySuitability=(slug:string,adults:number,ages:number[])=>{
  const params=new URLSearchParams({adults:String(adults)});
  ages.forEach(a=>params.append('child_ages',String(a)));
  return request<FamilyFit>(`/listings/${encodeURIComponent(slug)}/family-fit?${params}`)
}
export const saveListingRevision=(orgId:string,id:string,body:ListingRevisionWrite,token:string)=>
  request<ListingRevision>(`/vendor/organizations/${orgId}/listings/${id}/revisions`,{method:'POST',body:JSON.stringify(body)},token)
export const submitListingRevision=(orgId:string,id:string,token:string)=>
  request<ListingRevision>(`/vendor/organizations/${orgId}/listings/${id}/revisions/submit`,{method:'POST'},token)
export const submittedListingRevisions=(token:string)=>
  request<ListingRevision[]>('/admin/listings/revisions',{},token)
export const decideListingRevision=(id:string,decision:'approved'|'changes_requested',reason:string,token:string)=>
  request<ListingRevision>(`/admin/listings/revisions/${id}/decision`,{method:'POST',body:JSON.stringify({decision,reason})},token)

// Phase 5.1: Source-recorded map points only. Anonymous read-only APIs.
export type MapPoint = {
  id:string; kind:'destination'|'attraction'|'service'; title:string;
  latitude:number; longitude:number; category:string; district:string;
  detail_path:string; is_sample:boolean; business_verified:boolean;
  location_note:string; source_url:string|null
}
export type MapConfig = {tile_url:string|null;attribution:string;demo_mode:boolean}
export const getMapPoints = () => request<MapPoint[]>('/map/points')
export type ViewportBounds = {south:number;west:number;north:number;east:number}
export type ViewportResult = {points:MapPoint[];has_more:boolean;limit:number}
export const getViewportPoints = (bounds:ViewportBounds, kind:'all'|MapPoint['kind']='all', signal?:AbortSignal) => {
  const query=new URLSearchParams()
  for(const key of ['south','west','north','east'] as const)query.set(key,String(bounds[key]))
  query.set('kind',kind);query.set('limit','180')
  return request<ViewportResult>(`/map/viewport?${query}`,{signal})
}
export const getMapConfig = () => request<MapConfig>('/map/config')
export const resolveItineraryPlaces = (placeIds:string[]) => request<MapPoint[]>('/map/itinerary-places', {method:'POST', body:JSON.stringify({place_ids:placeIds})})
export const planPlaceLink = (placeId:string, editTripId?:string|null) =>
  `/plan?add_place=${encodeURIComponent(placeId)}${editTripId?`&edit_trip=${encodeURIComponent(editTripId)}`:''}`

export type GeoAuditIssue = {kind:MapPoint['kind'];label:string;detail_path:string;district:string;latitude:number|null;longitude:number|null;reason:string}
export type GeoAuditReport = {scanned:number;mapped:number;sourced_mapped:number;missing_coordinates:number;missing_location_source:number;outside_review_bounds:number;shared_coordinate_groups:number;issues:GeoAuditIssue[];issues_limited:boolean;scan_limited:boolean;note:string}
export const getGeoQualityReport = (token:string) => request<GeoAuditReport>('/admin/geo-quality',{},token)

// Phase 5.1 location-link import. Server follows only allowlisted HTTPS short redirects.
export type ResolvedLocation = {latitude:number;longitude:number;source_url:string;provider:string;precision:'pin'|'map_center';message:string}
export const resolveLocationLink = (url:string,token:string) => request<ResolvedLocation>('/map/resolve-location',{method:'POST',body:JSON.stringify({url})},token)


// Phase 5.2: anonymous, bounded PostGIS straight-line discovery.
export type NearbyPoint = MapPoint & {distance_km:number}
export type NearbyResult = {
  center:{title:string;latitude:number;longitude:number;kind:'destination'|'selected_location';destination_slug:string|null};
  radius_km:number;points:NearbyPoint[];has_more:boolean;distance_note:string
}
export type NearbyFilters = {
  destination?:string;near_lat?:number;near_lon?:number;
  radius_km:number;kind:'all'|'destination'|'attraction'|'service';category?:string;q?:string
}
export const getNearbyPlaces = (filters:NearbyFilters):Promise<NearbyResult> => {
  const params = new URLSearchParams()
  if(filters.destination) params.set('destination',filters.destination)
  else if(filters.near_lat!==undefined && filters.near_lon!==undefined){
    params.set('near_lat',String(filters.near_lat));params.set('near_lon',String(filters.near_lon))
  }
  params.set('radius_km',String(filters.radius_km))
  params.set('kind',filters.kind)
  if(filters.category) params.set('category',filters.category)
  if(filters.q?.trim()) params.set('q',filters.q.trim())
  return request<NearbyResult>(`/map/nearby?${params.toString()}`)
}

// Phase 7: customer feedback is independent of vendor verification and listing publication review.
export type CustomerReview = {
  id:string; rating:number; title:string; body:string; author_label:string; images:string[];
  visit_verified:false; created_at:string|null;
  response:{body:string;responded_at:string|null}|null
}
export type CustomerReviewSummary = {
  listing_slug:string; count:number; average_rating:number|null;
  visit_verified:false; reviews:CustomerReview[]
}
export type MyCustomerReview = {
  id:string;rating:number;title:string;body:string;
  state:'pending'|'published'|'changes_requested'|'hidden';moderation_note:string|null;images:string[]
}
export type ReviewWrite = {rating:number;title:string;body:string;images?:string[]}
export type ReportReason = 'spam'|'abuse'|'privacy'|'misleading'|'other'
export const publicCustomerReviews=(slug:string,offset=0)=>
  request<CustomerReviewSummary>(`/reviews/listings/${encodeURIComponent(slug)}?offset=${offset}&limit=5`)
export const myCustomerReview=(slug:string,token:string)=>
  request<{review:MyCustomerReview|null}>(`/reviews/listings/${encodeURIComponent(slug)}/mine`,{},token)
export const submitCustomerReview=(slug:string,body:ReviewWrite,token:string)=>
  request<{review:MyCustomerReview;message:string}>(`/reviews/listings/${encodeURIComponent(slug)}`,
    {method:'POST',body:JSON.stringify(body)},token)
export const reportCustomerReview=(id:string,reason:ReportReason,explanation:string,token:string)=>
  request<{reported:boolean;message:string}>(`/reviews/${encodeURIComponent(id)}/reports`,
    {method:'POST',body:JSON.stringify({reason,explanation})},token)
export type ProviderCustomerReview = {
  review:CustomerReview;listing_title:string;listing_slug:string;
  response_draft:{body:string;state:string;moderation_note:string|null}|null
}
export const providerCustomerReviews=(orgId:string,token:string)=>
  request<ProviderCustomerReview[]>(`/vendor/organizations/${orgId}/customer-reviews`,{},token)
export const submitProviderResponse=(orgId:string,reviewId:string,body:string,token:string)=>
  request<{state:string;message:string}>(`/vendor/organizations/${orgId}/customer-reviews/${reviewId}/response`,
    {method:'POST',body:JSON.stringify({body})},token)
export type ReviewModerationItem = MyCustomerReview & {
  listing_id:string;listing_slug:string|null;listing_title:string|null;created_at:string|null
}
export type ReplyModerationItem = {
  review_id:string;body:string;state:string;moderation_note:string|null;
  listing_title:string;review_title:string;review_state:string
}
export type CustomerReportItem = {
  id:string;review_id:string;reason:ReportReason;explanation:string;state:string;
  review_title:string;review_state:string;listing_title:string
}
export type ReviewDecision = 'published'|'changes_requested'|'hidden'
export const customerReviewQueue=(token:string,state='pending')=>
  request<ReviewModerationItem[]>(`/admin/customer-reviews?state=${encodeURIComponent(state)}`,{},token)
export const customerReplyQueue=(token:string,state='pending')=>
  request<ReplyModerationItem[]>(`/admin/customer-reviews/replies?state=${encodeURIComponent(state)}`,{},token)
export const customerReportQueue=(token:string,state='open')=>
  request<CustomerReportItem[]>(`/admin/customer-reviews/reports?state=${encodeURIComponent(state)}`,{},token)
export const moderateCustomerReview=(id:string,decision:ReviewDecision,reason:string,token:string)=>
  request<{state:string}>(`/admin/customer-reviews/${id}/decision`,
    {method:'POST',body:JSON.stringify({decision,reason})},token)
export const moderateProviderResponse=(id:string,decision:ReviewDecision,reason:string,token:string)=>
  request<{state:string}>(`/admin/customer-reviews/replies/${id}/decision`,
    {method:'POST',body:JSON.stringify({decision,reason})},token)
export const moderateCustomerReport=(id:string,decision:'dismissed'|'hide_review',reason:string,token:string)=>
  request<{state:string}>(`/admin/customer-reviews/reports/${id}/decision`,
    {method:'POST',body:JSON.stringify({decision,reason})},token)

// Phase 8: private tourist-provider information requests. No booking or payment states.
export type EnquiryState='open'|'answered'|'closed'|'withdrawn'|'blocked'
export type EnquirySummary={id:string;listing_slug:string;listing_title:string;subject:string;state:EnquiryState;created_at:string|null;updated_at:string|null}
export type EnquiryMessage={id:string;sender:'traveler'|'vendor';body:string;created_at:string|null}
export type EnquiryThread=EnquirySummary&{messages:EnquiryMessage[];has_more:boolean}
export type EnquiryReportReason='spam'|'abuse'|'privacy'|'misleading'|'other'
export type EnquiryAbuseReport={id:string;enquiry_id:string;listing_title:string;subject:string;reason:EnquiryReportReason;explanation:string;state:string;thread_state:EnquiryState}
export const createEnquiry=(slug:string,subject:string,message:string,token:string)=>
  request<{enquiry:EnquirySummary;message:string}>(`/enquiries/listings/${encodeURIComponent(slug)}`,
    {method:'POST',body:JSON.stringify({subject,message})},token)
export const myEnquiries=(token:string)=>request<EnquirySummary[]>('/enquiries',{},token)
export const myEnquiry=(id:string,token:string,offset=0)=>
  request<EnquiryThread>(`/enquiries/${encodeURIComponent(id)}?offset=${offset}`,{},token)
export const postTravelerMessage=(id:string,body:string,token:string)=>
  request<{sent:boolean;state:EnquiryState}>(`/enquiries/${encodeURIComponent(id)}/messages`,{method:'POST',body:JSON.stringify({body})},token)
export const withdrawEnquiry=(id:string,token:string)=>
  request<{state:EnquiryState}>(`/enquiries/${encodeURIComponent(id)}/withdraw`,{method:'POST'},token)
export const vendorEnquiries=(orgId:string,token:string)=>
  request<EnquirySummary[]>(`/vendor/organizations/${encodeURIComponent(orgId)}/enquiries`,{},token)
export const vendorEnquiry=(orgId:string,id:string,token:string,offset=0)=>
  request<EnquiryThread>(`/vendor/organizations/${encodeURIComponent(orgId)}/enquiries/${encodeURIComponent(id)}?offset=${offset}`,{},token)
export const postVendorMessage=(orgId:string,id:string,body:string,token:string)=>
  request<{sent:boolean;state:EnquiryState}>(`/vendor/organizations/${encodeURIComponent(orgId)}/enquiries/${encodeURIComponent(id)}/messages`,
    {method:'POST',body:JSON.stringify({body})},token)
export const closeVendorEnquiry=(orgId:string,id:string,token:string)=>
  request<{state:EnquiryState}>(`/vendor/organizations/${encodeURIComponent(orgId)}/enquiries/${encodeURIComponent(id)}/close`,{method:'POST'},token)
export const reportEnquiry=(id:string,reason:EnquiryReportReason,explanation:string,token:string)=>
  request<{reported:boolean;message:string}>(`/enquiries/${encodeURIComponent(id)}/reports`,
    {method:'POST',body:JSON.stringify({reason,explanation})},token)
export const enquiryAbuseReports=(token:string,state:'open'|'dismissed'|'actioned'='open')=>
  request<EnquiryAbuseReport[]>(`/admin/enquiry-reports?state=${state}`,{},token)
export const moderateEnquiryReport=(id:string,decision:'dismissed'|'block_thread',reason:string,token:string)=>
  request<{state:string;thread_state:EnquiryState}>(`/admin/enquiry-reports/${encodeURIComponent(id)}/decision`,
    {method:'POST',body:JSON.stringify({decision,reason})},token)

export const reportedEnquiryThread=(reportId:string,token:string,offset=0)=>
  request<EnquiryThread>(`/admin/enquiry-reports/${encodeURIComponent(reportId)}/thread?offset=${offset}`,{},token)


// Phase 7.1: multiple reviews, photo gallery and editing one specific review.
export const myCustomerReviews=(slug:string,token:string)=>
  request<{reviews:MyCustomerReview[];review:MyCustomerReview|null;remaining:number}>(
    `/reviews/listings/${encodeURIComponent(slug)}/mine`,{},token)
export const editCustomerReview=(id:string,body:ReviewWrite,token:string)=>
  request<{review:MyCustomerReview;message:string}>(`/reviews/${encodeURIComponent(id)}`,
    {method:'PATCH',body:JSON.stringify(body)},token)


// Phase 9C: per-account inbox + one-to-many release announcements (in-app only).
export type NotificationItem={id:string;kind:string;title:string;body:string;target_url:string;
  created_at:string|null;read:boolean;announcement:boolean}
export type NotificationInbox={items:NotificationItem[];unread_count:number;has_more:boolean}
export type AnnouncementWrite={release_key:string;title:string;body:string;target_url:string;expires_in_days:number}
export const allNotifications=(token:string,offset=0)=>
  request<NotificationInbox>(`/notifications?offset=${offset}&limit=30`,{},token)
export const unreadNotificationCount=(token:string)=>
  request<{unread_count:number}>('/notifications/unread-count',{},token)
export const markNotificationRead=(id:string,token:string)=>
  request<{read:boolean}>(`/notifications/${encodeURIComponent(id)}/read`,{method:'POST'},token)
export const markAllNotificationsRead=(token:string)=>
  request<{unread_count:number}>('/notifications/read-all',{method:'POST'},token)
export const publishReleaseAnnouncement=(body:AnnouncementWrite,token:string)=>
  request<{id:string;published:boolean}>('/admin/announcements',{method:'POST',body:JSON.stringify(body)},token)
export const removeCustomerReview=(id:string,reason:string,token:string)=>
  request<{state:string;removed:boolean}>(`/admin/customer-reviews/${encodeURIComponent(id)}/remove`,
    {method:'POST',body:JSON.stringify({reason})},token)

// Phase 10B: signed-in email preferences. Email is optional, server configured.
export type EmailPreferences = {activity_enabled:boolean; releases_enabled:boolean; verified_email_available:boolean; delivery_configured:boolean}
export const emailPreferences=(token:string)=>request<EmailPreferences>('/notifications/email-preferences',{},token)
export const setEmailPreferences=(values:Pick<EmailPreferences,'activity_enabled'|'releases_enabled'>,token:string)=>
  request<EmailPreferences>('/notifications/email-preferences',{method:'PATCH',body:JSON.stringify(values)},token)
