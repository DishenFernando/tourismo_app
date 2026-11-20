import { ArrowRight, BadgeCheck, BedDouble, BusFront, CircleDollarSign, Compass, MapPinned, Search, ShieldCheck, UtensilsCrossed, WandSparkles } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

const features = [
  { icon:MapPinned, name:'Destinations', description:'Get to know the places that make Sri Lanka unforgettable.', path:'/discover'},
  { icon:BedDouble, name:'Places to stay', description:'Browse independently approved accommodation listings as they become available.', path:'/listings?category=accommodation'},
  { icon:UtensilsCrossed, name:'Food & dining', description:'Explore published dining profiles and indicative menus.', path:'/listings?category=restaurant'},
  { icon:BusFront, name:'Getting around', description:'Discover published transport providers and vehicle types.', path:'/listings?category=transport'},
]
export function Home() {
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  return <>
    <section className="hero relative overflow-hidden">
      <div className="hero-blob hero-blob-a"/><div className="hero-blob hero-blob-b"/>
      <div className="wrap grid items-center gap-10 py-16 pb-20 lg:grid-cols-[1.07fr_.93fr] lg:py-28">
        <div className="relative z-10">
          <div className="eyebrow"><span className="eyebrow-dot"/> YOUR ISLAND. YOUR JOURNEY.</div>
          <h1 className="hero-title">Discover Sri Lanka, <em>your way.</em></h1>
          <p className="mt-6 max-w-xl text-lg leading-8 text-white/85">From misty mountains to golden shores, start exploring, comparing and planning — in one beautiful place.</p>
          <form onSubmit={e=>{e.preventDefault();navigate(`/discover?q=${encodeURIComponent(search.trim())}`)}} className="hero-search mt-9">
            <Search className="text-pine" size={23}/><input aria-label="Search Sri Lankan destinations" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Where in Sri Lanka?" maxLength={100} />
            <button type="submit">Explore <ArrowRight size={18}/></button>
          </form>
          <div className="mt-5 flex flex-wrap items-center gap-5 text-white/80 text-sm"><span className="inline-flex items-center gap-2"><BadgeCheck size={16}/> No account needed</span><span className="inline-flex items-center gap-2"><ShieldCheck size={16}/> Information labeled by source</span></div>
        </div>
        <div className="hero-art relative z-10" aria-label="Illustrated rolling Sri Lankan hills and sun" role="img">
          <div className="sun"/><div className="mountain-back"/><div className="mountain-mid"/><div className="mountain-front"/>
          <div className="hero-card-floating card-top"><MapPinned size={20} className="text-coral"/><span>Where will you go next?</span></div>
          <div className="hero-card-floating card-bottom"><Compass size={21} className="text-pine"/><span>Make memories, not guesswork.</span></div>
          <div className="scenery-caption">THE ADVENTURE BEGINS HERE</div>
        </div>
      </div>
      <svg viewBox="0 0 1440 64" preserveAspectRatio="none" className="absolute bottom-[-1px] left-0 w-full h-12" aria-hidden="true"><path fill="#fcf9f3" d="M0 40Q360 -8 720 44T1440 34V64H0Z"/></svg>
    </section>
    <section className="wrap pt-14">
      <div className="flex flex-wrap gap-4 items-end justify-between"><div><span className="small-label">ONE ISLAND. SO MANY POSSIBILITIES.</span><h2 className="section-title">Everything for a better journey</h2></div>
      <Link to="/discover" className="text-pine font-semibold inline-flex items-center gap-2 hover:underline">Explore destinations <ArrowRight size={17}/></Link></div>
      <div className="grid gap-5 mt-7 sm:grid-cols-2 xl:grid-cols-4">{features.map((f,i)=><Link to={f.path} key={f.name} className="feature-card group">
        <div className={`feature-icon feature-icon-${i}`}><f.icon size={29}/></div><h3 className="mt-5 text-xl font-bold">{f.name}</h3><p className="text-sm text-ink/60 leading-6 mt-2">{f.description}</p><div className="mt-5 flex items-center gap-2 text-pine font-semibold text-sm">Take a look <ArrowRight className="group-hover:translate-x-1 transition-transform" size={16}/></div>
      </Link>)}</div>
    </section>
    <section className="wrap mt-16"><div className="cta-panel grid items-center gap-8 md:grid-cols-[1fr_auto]">
      <div><span className="small-label text-[#d2efe9]">TRAVEL WELL, START SIMPLE</span><h2 className="text-3xl font-extrabold mt-3 text-white">Your trip. Your people. Your budget.</h2>
        <p className="text-white/75 mt-3 max-w-xl">Sketch an itinerary and estimate what you want to spend, even without an account. Your temporary draft stays in this browser session.</p></div>
      <Link to="/plan" className="cta-button"><CircleDollarSign size={19}/> Start my trip <ArrowRight size={18}/></Link>
    </div></section>
    <section className="wrap mt-16 grid gap-6 md:grid-cols-3">{[
      {icon:Compass,title:'Guest first',desc:'Search destinations and create a temporary plan without giving us your email.'},
      {icon:ShieldCheck,title:'Clear about what we know',desc:'Sample content is labeled. Live rates, reviews and availability will only appear when sourced.'},
      {icon:WandSparkles,title:'Built for every traveler',desc:'Group composition, transparent budgeting and three-language support guide our roadmap.'}
    ].map(f=><div key={f.title} className="flex gap-4"><f.icon className="text-pine shrink-0" size={27}/><div><h3 className="font-bold text-lg">{f.title}</h3><p className="text-sm leading-6 text-ink/60 mt-2">{f.desc}</p></div></div>)}</section>
  </>
}
