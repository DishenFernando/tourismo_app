import { describe, expect, it } from 'vitest'
import { listingReadiness, validateListingStep } from './listingWizard'
import type { ListingWrite } from './api'

const sample: ListingWrite = {
  title: 'Mountain View Family Room',
  summary: 'Family-friendly rooms near the hill-country railway station.',
  description: 'A family accommodation listing with private rooms and optional breakfast. Confirm all details and rates with the provider directly.',
  public_email: null, public_phone: null,
  latitude: null, longitude: null, location_source_url: null, location_note: null,
  details: {room_types: [{name: 'Family room', max_adults: 2, max_children: 2, number_of_rooms: 1, min_child_age: 4, max_child_age: 15}]},
}

describe('Phase 4.5 guided listing steps', () => {
  it('validates only the active step, allowing contact-free draft previews', () => {
    expect(validateListingStep(0,'accommodation',sample)).toBeNull()
    expect(validateListingStep(1,'accommodation',sample)).toBeNull()
    expect(validateListingStep(2,'accommodation',sample)).toBeNull()
    expect(listingReadiness('accommodation',sample)).toContain(
      'A public contact is required before requesting publication (not to save a draft).')
  })
  it('checks child-age policies without weakening backend restrictions', () => {
    const invalid = {...sample, details: {room_types: [
      {name:'Family room',max_adults:2,max_children:1,number_of_rooms:1,min_child_age:15,max_child_age:5}
    ]}}
    expect(validateListingStep(1,'accommodation',invalid)).toMatch(/child-age range/)
  })
  it('checks contact and sourced coordinates together', () => {
    expect(validateListingStep(2,'accommodation',{...sample,latitude:7.29})).toMatch(/together/)
    expect(validateListingStep(2,'accommodation',{...sample,latitude:7.29,longitude:80.64,
      location_source_url:'http://example.org/spot'})).toMatch(/HTTPS/)
  })
  it('checks all category-specific required information', () => {
    const data = [
      ['restaurant',{cuisines:[]}],['guide',{languages:['English'],service_areas:[]}],
      ['transport',{vehicle_types:[]}],['tour_operator',{experience_types:['walk'],service_areas:[]}],
      ['activity',{experience_types:['walk'],service_areas:[]}],
    ] as const
    for (const [category,details] of data) {
      expect(validateListingStep(1,category,{...sample,details})).not.toBeNull()
    }
  })
  it('prevents blank or too-short introductions and descriptions', () => {
    expect(validateListingStep(0,'restaurant',{...sample,title:'  '})).toMatch(/title/)
    expect(validateListingStep(0,'restaurant',{...sample,summary:'Short'})).toMatch(/introduction/)
    expect(validateListingStep(2,'restaurant',{...sample,description:'Short'})).toMatch(/Describe/)
  })
})
