import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Header } from '../components/Header'
import { Footer } from '../components/Footer'
import { Home } from '../features/Home'
import { Discover } from '../features/Discover'
import { DestinationPage } from '../features/Destination'
import { Planner } from '../features/Planner'
import { Saved } from '../features/Saved'

export default function App() {
  return <BrowserRouter><div className="min-h-screen bg-cream text-ink flex flex-col"><Header/>
    <div className="grow"><Routes>
      <Route path="/" element={<Home/>}/><Route path="/discover" element={<Discover/>}/>
      <Route path="/destinations/:slug" element={<DestinationPage/>}/>
      <Route path="/plan" element={<Planner/>}/><Route path="/saved" element={<Saved/>}/>
      <Route path="*" element={<main className="wrap pt-20 min-h-[55vh]"><h1 className="page-title">Page not found</h1><p className="mt-4">Try our <a href="/discover" className="text-pine underline">destination explorer</a>.</p></main>}/>
    </Routes></div><Footer/></div></BrowserRouter>
}
