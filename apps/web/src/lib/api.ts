export type DestinationPhoto = {image_url:string; file_page_url:string; photographer:string; license_name:string; license_url:string; alt_text:string; media_kind?:'commons_photo'|'owned_photo'|'ai_illustration'}
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
