import {Notifications} from '../features/Notifications'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Header } from '../components/Header'
import { Footer } from '../components/Footer'
import { Home } from '../features/Home'
import { Discover } from '../features/Discover'
import { DestinationPage } from '../features/Destination'
import { Planner } from '../features/Planner'
import { Saved } from '../features/Saved'
import { Account } from '../features/Account'
import { Admin } from '../features/Admin'
import { Vendors } from '../features/Vendors'
import { VendorReviews } from '../features/VendorReviews'
import { ServiceListings, ServiceListingPage } from '../features/ServiceListings'
import { ExplorerMap } from '../features/Map'
import { GeoQuality } from '../features/GeoQuality'
import { NearbyDiscovery } from '../features/NearbyDiscovery'
import { ListingManagement, AdminListingReviews } from '../features/ListingManagement'
import { ProviderFeedback } from '../features/ProviderFeedback'
import { ReviewModeration } from '../features/ReviewModeration'
import { Enquiries } from '../features/Enquiries'
import { EnquiryReportModeration } from '../features/EnquiryReportModeration'

import {LocaleProvider} from '../i18n/LocaleProvider'
import {SkipToContent, LocaleToolbar, RouteMetadata} from '../features/SiteChrome'
import {AccessibilityPage} from '../features/AccessibilityPage'

import {TranslationWorkbench} from '../features/TranslationWorkbench'

export default function App() {
  return <BrowserRouter><LocaleProvider><div className="min-h-screen bg-cream text-ink flex flex-col"><SkipToContent/><Header/><LocaleToolbar/><RouteMetadata/>
    <div className="grow"><div id="tourismo-content" tabIndex={-1}><Routes>
      <Route path="/" element={<Home/>}/><Route path="/discover" element={<Discover/>}/>
      <Route path="/destinations/:slug" element={<DestinationPage/>}/>
      <Route path="/plan" element={<Planner/>}/><Route path="/saved" element={<Saved/>}/>
      <Route path="/map" element={<ExplorerMap/>}/><Route path="/admin/geo-quality" element={<GeoQuality/>}/><Route path="/nearby" element={<NearbyDiscovery/>}/><Route path="/account" element={<Account/>}/><Route path="/admin" element={<Admin/>}/>
      <Route path="/listings" element={<ServiceListings/>}/><Route path="/listings/:slug" element={<ServiceListingPage/>}/>
      <Route path="/demo/listings" element={<ServiceListings demo/>}/><Route path="/demo/listings/:slug" element={<ServiceListingPage demo/>}/>
      <Route path="/enquiries" element={<Enquiries/>}/><Route path="/vendor/enquiries" element={<Enquiries vendor/>}/><Route path="/admin/enquiry-reports" element={<EnquiryReportModeration/>}/>
      <Route path="/vendors" element={<Vendors/>}/><Route path="/vendor/feedback" element={<ProviderFeedback/>}/><Route path="/admin/customer-reviews" element={<ReviewModeration/>}/><Route path="/vendor/listings" element={<ListingManagement/>}/><Route path="/admin/listings" element={<AdminListingReviews/>}/><Route path="/admin/vendors" element={<VendorReviews/>}/>
      <Route path="/accessibility" element={<AccessibilityPage/>}/>
      <Route path="/notifications" element={<Notifications/>}/>
      <Route path="/admin/translation-workbench" element={<TranslationWorkbench/>}/>
      <Route path="*" element={<main className="wrap pt-20 min-h-[55vh]"><h1 className="page-title">Page not found</h1><p className="mt-4">Try our <a href="/discover" className="text-pine underline">destination explorer</a>.</p></main>}/>
    </Routes></div></div><Footer/></div></LocaleProvider></BrowserRouter>
}
