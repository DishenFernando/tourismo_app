import type { ListingWrite, VendorCategory } from './api'

/** UI guidance only. The authenticated backend remains the final authority. */
export const listingSteps = [
  {title: 'Introduction', subtitle: 'What do you offer?'},
  {title: 'Service details', subtitle: 'Only fields for your business type'},
  {title: 'Contact & location', subtitle: 'Choose what visitors can see'},
  {title: 'Preview & save', subtitle: 'Review before saving privately'},
] as const

const rows = (value: unknown): Record<string, unknown>[] => Array.isArray(value)
  ? value.filter((item): item is Record<string,unknown> => item !== null && typeof item === 'object' && !Array.isArray(item)) : []
const tags = (value: unknown): string[] => Array.isArray(value)
  ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : []
const within = (value: unknown, min: number, max: number): boolean =>
  typeof value === 'number' && Number.isInteger(value) && value >= min && value <= max
const priceOkay = (value: unknown): boolean => value === null || value === undefined || within(value, 0, 100_000_000)

export function validateListingStep(step: number, category: VendorCategory, form: ListingWrite): string | null {
  if (step === 0) {
    if (form.title.trim().length < 3 || form.title.length > 160) return 'Add a title of 3–160 characters.'
    if (form.summary.trim().length < 25 || form.summary.length > 350) return 'Write a short introduction of 25–350 characters.'
    return null
  }
  if (step === 1) {
    const details = form.details
    if (category === 'accommodation') {
      const rooms = rows(details.room_types)
      if (rooms.length < 1 || rooms.length > 25) return 'Add at least one room type (maximum 25).'
      for (const room of rooms) {
        if (String(room.name ?? '').trim().length < 2 || !within(room.max_adults, 1, 30)
          || !within(room.max_children, 0, 30) || !within(room.number_of_rooms, 1, 2000)
          || !priceOkay(room.indicative_nightly_lkr_minor)) return 'Check each room name, occupancy, room count and indicative rate.'
        const minAge = room.min_child_age, maxAge = room.max_child_age, total = room.max_total_guests
        if ((minAge != null && !within(minAge, 0, 17)) || (maxAge != null && !within(maxAge, 0, 17))
          || (minAge != null && maxAge != null && Number(minAge) > Number(maxAge))
          || (total != null && (!within(total, 1, 60) || Number(total) > Number(room.max_adults) + Number(room.max_children)))) {
          return 'Check the child-age range and the total guest limit for each room.'
        }
      }
    } else if (category === 'restaurant') {
      if (tags(details.cuisines).length < 1) return 'Choose at least one cuisine type.'
      if (rows(details.menu_items).some(item => String(item.name ?? '').trim().length < 2 || !priceOkay(item.indicative_price_lkr_minor)))
        return 'Check each menu name and its optional indicative price.'
    } else if (category === 'guide') {
      if (!tags(details.languages).length || !tags(details.service_areas).length) return 'Add languages and areas served.'
      if (!priceOkay(details.indicative_daily_lkr_minor)) return 'Enter a valid optional guide rate.'
    } else if (category === 'transport') {
      const vehicles = rows(details.vehicle_types)
      if (!vehicles.length) return 'Add at least one vehicle type.'
      if (vehicles.some(item => String(item.name ?? '').trim().length < 2 || !within(item.passenger_seats, 1, 100)
        || !within(item.luggage_bags, 0, 100) || !priceOkay(item.indicative_day_lkr_minor)))
        return 'Check vehicle names, seats, luggage capacity and optional rates.'
    } else {
      if (!tags(details.experience_types).length || !tags(details.service_areas).length) return 'Add experiences and areas served.'
      if (details.minimum_age != null && !within(details.minimum_age, 0, 100)) return 'Enter a valid minimum participant age.'
      if (!priceOkay(details.indicative_person_lkr_minor)) return 'Enter a valid optional activity rate.'
    }
    return null
  }
  if (step === 2) {
    if (form.description.trim().length < 60 || form.description.length > 3500) return 'Describe the service in at least 60 characters (maximum 3500).'
    if (form.public_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.public_email)) return 'Check the optional public contact email.'
    if (form.public_phone && (!/^[+0-9 ()-]{7,40}$/.test(form.public_phone))) return 'Check the optional public phone number.'
    const hasLat = form.latitude != null, hasLon = form.longitude != null, hasUrl = Boolean(form.location_source_url)
    if (hasLat !== hasLon || hasLat !== hasUrl) return 'Map coordinates and an HTTPS source link must be supplied together, or all left empty.'
    if (hasLat && (Math.abs(Number(form.latitude)) > 90 || Math.abs(Number(form.longitude)) > 180
      || !Number.isFinite(form.latitude) || !Number.isFinite(form.longitude))) return 'Check the latitude and longitude.'
    if (hasUrl) {
      try {
        const url = new URL(form.location_source_url ?? '')
        if (url.protocol !== 'https:' || url.username || url.password || url.port && url.port !== '443'
          || /^(localhost|127\.0\.0\.1|\[::1\])$/i.test(url.hostname)
          || /\.(local|internal)$/i.test(url.hostname)) return 'Use a public HTTPS location-source URL.'
      } catch { return 'Enter a valid HTTPS location-source URL.' }
    }
    return null
  }
  return null
}

export function listingReadiness(category: VendorCategory, form: ListingWrite): string[] {
  const issues = [0,1,2].map(step => validateListingStep(step,category,form)).filter((v):v is string => Boolean(v))
  if (!form.public_email && !form.public_phone) issues.push('A public contact is required before requesting publication (not to save a draft).')
  return issues
}
