import { Compass, Menu, UserRound, X } from 'lucide-react'
import { NavLink, Link } from 'react-router-dom'
import { useState } from 'react'
import { useTourismoAuth } from '../app/Auth'

const links = [{path:'/', name:'Home'}, {path:'/discover', name:'Discover'}, {path:'/plan',name:'Plan trip'}, {path:'/saved',name:'Saved trips'}]
export function Header() {
  const [opened, setOpened] = useState(false)
  const [showAuthInfo, setShowAuthInfo] = useState(false)
  const auth = useTourismoAuth()
  return <>
    <header className="topnav print:hidden"><div className="wrap flex h-[84px] items-center justify-between gap-5">
      <Link to="/" className="flex items-center gap-2" aria-label="Tourismo home">
        <img alt="Tourismo" className="h-11 w-auto max-w-[210px] object-contain" src="/brand/Tourismo_Logo_Horizontal_Vector.svg" />
      </Link>
      <nav className="hidden md:flex items-center gap-8" aria-label="Main navigation">
        {links.map(l=><NavLink key={l.path} to={l.path} end={l.path==='/'} className={({isActive})=>`navlink ${isActive?'active':''}`}>{l.name}</NavLink>)}
      </nav>
      <div className="hidden md:flex items-center gap-2">
        <span className="text-xs text-ink/50 mr-2">EN · <span title="Sinhala and Tamil content review planned">SI/TA planned</span></span>
        <button className="btn-secondary" onClick={()=>auth.enabled ? (auth.signedIn ? void auth.logout() : auth.login()) : setShowAuthInfo(true)}>
          <UserRound size={17}/> {auth.signedIn?'Log out':'Log in'}
        </button>
        <Link className="btn-primary" to="/plan"><Compass size={17}/> Start planning</Link>
      </div>
      <button aria-label="Toggle navigation" aria-expanded={opened} onClick={()=>setOpened(v=>!v)} className="md:hidden rounded-lg p-3 text-ink">{opened?<X/>:<Menu/>}</button>
    </div>
    {opened && <nav aria-label="Mobile navigation" className="mobile-menu">
      {links.map(l=><NavLink key={l.path} onClick={()=>setOpened(false)} to={l.path} className="block py-3">{l.name}</NavLink>)}
      <button onClick={()=>{setOpened(false); auth.enabled?auth.login():setShowAuthInfo(true)}} className="text-left py-3">Account / log in</button>
    </nav>}
    </header>
    {showAuthInfo && <div role="dialog" aria-modal="true" aria-labelledby="auth-info-title" className="dialog-backdrop" onClick={()=>setShowAuthInfo(false)}>
      <div className="dialog-panel" onClick={e=>e.stopPropagation()}><h2 className="text-xl font-bold" id="auth-info-title">Authentication setup required</h2>
        <p className="text-ink/70 mt-3">Guest discovery and trip drafts already work. To enable real Google/email sign-in and cloud saving, configure a Clerk application and backend verification keys as described in the README.</p>
        <p className="text-sm text-pine mt-3">No fake login or verification codes are issued.</p><button autoFocus className="btn-primary mt-5" onClick={()=>setShowAuthInfo(false)}>Continue exploring</button>
      </div></div>}
  </>
}
