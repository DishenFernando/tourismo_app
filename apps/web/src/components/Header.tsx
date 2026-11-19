import { Compass, LogOut, Menu, Settings2, UserRound, X, ChevronDown } from 'lucide-react'
import { NavLink, Link } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useTourismoAuth } from '../app/Auth'

const links = [{path:'/', name:'Home'}, {path:'/discover', name:'Discover'}, {path:'/plan',name:'Plan trip'}, {path:'/saved',name:'Saved trips'}]

export function Header() {
  const [opened,setOpened] = useState(false)
  const [showAuthInfo,setShowAuthInfo] = useState(false)
  const [menuOpen,setMenuOpen] = useState(false)
  const [profilePromptDismissed,setProfilePromptDismissed] = useState(false)
  const menuRef=useRef<HTMLDivElement|null>(null)
  const auth=useTourismoAuth()
  useEffect(()=>{
    if (!menuOpen) return
    const handleClick=(event:MouseEvent)=>{if(!menuRef.current?.contains(event.target as Node))setMenuOpen(false)}
    const handleKey=(event:KeyboardEvent)=>{if(event.key==='Escape')setMenuOpen(false)}
    document.addEventListener('mousedown',handleClick)
    document.addEventListener('keydown',handleKey)
    return()=>{document.removeEventListener('mousedown',handleClick);document.removeEventListener('keydown',handleKey)}
  },[menuOpen])
  const login=()=>auth.enabled?auth.login():setShowAuthInfo(true)
  const accountPicture=auth.person?.avatar ?
    <img src={auth.person.avatar} alt="" className="h-9 w-9 rounded-full object-cover" referrerPolicy="no-referrer"/> :
    <span className="grid h-9 w-9 place-items-center rounded-full bg-[#e6f4ee] text-pine"><UserRound size={20}/></span>
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
        {!auth.signedIn ? <button className="btn-secondary" onClick={login}><UserRound size={17}/> Log in / Sign up</button> :
          <div className="relative" ref={menuRef}>
            <button type="button" aria-expanded={menuOpen} aria-haspopup="menu" onClick={()=>setMenuOpen(v=>!v)} className="account-button">
              {accountPicture}
              <span className="max-w-[125px] truncate text-left text-sm font-bold">{auth.person?.name || 'My account'}</span>
              <ChevronDown size={15}/>
            </button>
            {menuOpen && <div className="account-menu" role="menu">
              <p className="px-4 pb-2 pt-3 text-xs text-ink/60 truncate">{auth.person?.email || 'Signed in to Tourismo'}</p>
              {auth.profileState==='error' && <p className="px-4 pb-2 text-xs text-red-600">Profile sync failed. Open profile to retry.</p>}
              <Link role="menuitem" onClick={()=>setMenuOpen(false)} to="/account" className="account-menu-item"><UserRound size={17}/> My profile {auth.profile&&!auth.profile.profile_completed&&<span className="text-xs text-amber-700">· Complete</span>}</Link>
              <button role="menuitem" className="account-menu-item" onClick={()=>{setMenuOpen(false);auth.manageAccount()}}><Settings2 size={17}/> Sign-in & security</button>
              <button role="menuitem" className="account-menu-item text-red-700" onClick={()=>{setMenuOpen(false);void auth.logout()}}><LogOut size={17}/> Log out</button>
            </div>}
          </div>}
        <Link className="btn-primary" to="/plan"><Compass size={17}/> Start planning</Link>
      </div>
      <button aria-label="Toggle navigation" aria-expanded={opened} onClick={()=>setOpened(v=>!v)} className="md:hidden rounded-lg p-3 text-ink">{opened?<X/>:<Menu/>}</button>
    </div>
    {opened && <nav aria-label="Mobile navigation" className="mobile-menu">
      {links.map(l=><NavLink key={l.path} onClick={()=>setOpened(false)} to={l.path} className="block py-3">{l.name}</NavLink>)}
      {auth.signedIn ? <>
        <Link to="/account" onClick={()=>setOpened(false)} className="flex items-center gap-3 py-3">{accountPicture}<span>{auth.person?.name || 'My profile'}</span></Link>
        <button className="block py-3" onClick={()=>{setOpened(false);void auth.logout()}}>Log out</button>
      </> : <button className="text-left py-3" onClick={()=>{setOpened(false);login()}}>Log in / Sign up</button>}
    </nav>}
    </header>
    {auth.signedIn && auth.profile && !auth.profile.profile_completed && !profilePromptDismissed &&
      <div className="border-b border-[#d4e9e0] bg-[#eef8f2] print:hidden"><div className="wrap flex flex-wrap items-center justify-between gap-3 py-3 text-sm text-[#21554e]">
        <p><b>Welcome to Tourismo!</b> Add your travel name and preferences to personalize your account.</p>
        <div className="flex items-center gap-4"><Link to="/account" className="font-bold underline">Create my profile</Link>
          <button aria-label="Dismiss profile reminder" onClick={()=>setProfilePromptDismissed(true)} className="rounded p-1"><X size={17}/></button></div>
      </div></div>}
    {showAuthInfo && <div role="dialog" aria-modal="true" aria-labelledby="auth-info-title" className="dialog-backdrop" onClick={()=>setShowAuthInfo(false)}>
      <div className="dialog-panel" onClick={e=>e.stopPropagation()}><h2 className="text-xl font-bold" id="auth-info-title">Authentication setup required</h2>
        <p className="text-ink/70 mt-3">Guest discovery and trip drafts already work. To enable real Google/email sign-in and cloud saving, configure a Clerk application and backend verification keys as described in the README.</p>
        <p className="text-sm text-pine mt-3">No fake login or verification codes are issued.</p><button autoFocus className="btn-primary mt-5" onClick={()=>setShowAuthInfo(false)}>Continue exploring</button>
      </div></div>}
  </>
}
