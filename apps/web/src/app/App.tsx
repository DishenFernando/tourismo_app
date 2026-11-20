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
import { ListingManagement, AdminListingReviews } from '../features/ListingManagement'

export default function App() {
  return <BrowserRouter><div className="min-h-screen bg-cream text-ink flex flex-col"><Header/>
    <div className="grow"><Routes>
      <Route path="/" element={<Home/>}/><Route path="/discover" element={<Discover/>}/>
      <Route path="/destinations/:slug" element={<DestinationPage/>}/>
      <Route path="/plan" element={<Planner/>}/><Route path="/saved" element={<Saved/>}/>
      <Route path="/account" element={<Account/>}/><Route path="/admin" element={<Admin/>}/>
      <Route path="/listings" element={<ServiceListings/>}/><Route path="/listings/:slug" element={<ServiceListingPage/>}/>
      <Route path="/demo/listings" element={<ServiceListings demo/>}/><Route path="/demo/listings/:slug" element={<ServiceListingPage demo/>}/>
      <Route path="/vendors" element={<Vendors/>}/><Route path="/vendor/listings" element={<ListingManagement/>}/><Route path="/admin/listings" element={<AdminListingReviews/>}/><Route path="/admin/vendors" element={<VendorReviews/>}/>
      <Route path="*" element={<main className="wrap pt-20 min-h-[55vh]"><h1 className="page-title">Page not found</h1><p className="mt-4">Try our <a href="/discover" className="text-pine underline">destination explorer</a>.</p></main>}/>
    </Routes></div><Footer/></div></BrowserRouter>
}
