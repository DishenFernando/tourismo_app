import {useLocale, navLabel} from '../i18n/LocaleProvider'
import { Bell, Compass, LogOut, Menu, Settings2, UserRound, X, ChevronDown, ShieldCheck, MapPin } from 'lucide-react'
import { NavLink, Link } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useTourismoAuth } from '../app/Auth'
import {unreadNotificationCount} from '../lib/api'

const baseLinks = [{path:'/', name:'Home'}, {path:'/discover', name:'Discover'}, {path:'/map', name:'Map'}, {path:'/listings',name:'Services'}, {path:'/plan',name:'Plan trip'}, {path:'/saved',name:'Saved trips'}, {path:'/enquiries',name:'Enquiries'}, {path:'/vendors',name:'For businesses'}]

export function Header() {
  const {locale} = useLocale()
  const links = baseLinks.map(item => ({...item, name: navLabel(locale, item.path, item.name)}))
  const [opened,setOpened] = useState(false)
  const [unread,setUnread] = useState(0)
  const [showAuthInfo,setShowAuthInfo] = useState(false)
  const [menuOpen,setMenuOpen] = useState(false)
  const [profilePromptDismissed,setProfilePromptDismissed] = useState(false)
  const menuRef=useRef<HTMLDivElement|null>(null)
  const auth=useTourismoAuth()
  useEffect(()=>{
    if(!auth.signedIn){setUnread(0);return}
    let mounted=true
    const refresh=()=>void auth.token().then(token=>token?unreadNotificationCount(token):null)
      .then(result=>{if(mounted&&result)setUnread(result.unread_count)})
      .catch(()=>{ /* An offline inbox must not break primary navigation. */ })
    refresh()
    const timer=window.setInterval(refresh,60_000)
    return()=>{mounted=false;window.clearInterval(timer)}
  },[auth.signedIn,auth.token])
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
    <header className="tourismo-navbar-shell topnav print:hidden"><div className="wrap flex h-[84px] items-center justify-between gap-5">
      <Link to="/" className="flex items-center gap-2" aria-label="Tourismo home">
        <img alt="Tourismo" className="h-11 w-auto max-w-[210px] object-contain" src="/brand/Tourismo_Logo_Horizontal_Vector.svg" />
      </Link>
      <nav className="hidden md:flex items-center gap-8" aria-label="Main navigation">
        {links.map(l=><NavLink key={l.path} to={l.path} end={l.path==='/'} className={({isActive})=>`navlink ${isActive?'active':''}`}>{l.name}</NavLink>)}
      </nav>
      <div className="hidden md:flex items-center gap-2">
        {auth.signedIn&&<Link to="/notifications" aria-label={`Notifications${unread?` (${unread} unread)`:''}`}
          title="Notifications" className="relative inline-flex min-h-11 min-w-11 items-center justify-center rounded-full border border-ink/15 bg-white hover:bg-[#eaf5f0] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pine">
          <Bell size={19}/>{unread>0&&<span aria-hidden="true" className="absolute -right-1 -top-1 min-w-5 rounded-full bg-red-700 px-1 text-center text-xs font-bold text-white">{unread>99?'99+':unread}</span>}
        </Link>}
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
              <Link role="menuitem" onClick={()=>setMenuOpen(false)} to="/notifications" className="account-menu-item"><Bell size={17}/> Notifications {unread>0?`(${unread})`:''}</Link>
              <Link role="menuitem" onClick={()=>setMenuOpen(false)} to="/account" className="account-menu-item"><UserRound size={17}/> My profile {auth.profile&&!auth.profile.profile_completed&&<span className="text-xs text-amber-700">· Complete</span>}</Link>
              {auth.profile?.roles.some(r=>r==='admin'||r==='editor') && <Link role="menuitem" to="/admin" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Content dashboard</Link>}
              {auth.profile?.roles.some(r=>r==='admin'||r==='editor') && <Link role="menuitem" to="/admin/translation-workbench" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Translation workbench</Link>}
              {auth.profile?.roles.some(r=>r==='admin'||r==='editor') && <Link role="menuitem" to="/admin/geo-quality" onClick={()=>setMenuOpen(false)} className="account-menu-item"><MapPin size={17}/> Map quality report</Link>}
              <Link role="menuitem" to="/vendors" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> My businesses</Link>
              <Link role="menuitem" to="/vendor/enquiries" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Provider enquiries</Link>
              <Link role="menuitem" to="/vendor/feedback" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Customer feedback</Link>
              <Link role="menuitem" to="/vendor/listings" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Manage listings</Link>
              {auth.profile?.roles.includes('admin') && <Link role="menuitem" to="/admin/vendors" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Vendor verification</Link>}
              {auth.profile?.roles.includes('admin') && <Link role="menuitem" to="/admin/enquiry-reports" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Enquiry reports</Link>}
              {auth.profile?.roles.includes('admin') && <Link role="menuitem" to="/admin/customer-reviews" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Feedback moderation</Link>}
              {auth.profile?.roles.includes('admin') && <Link role="menuitem" to="/admin/listings" onClick={()=>setMenuOpen(false)} className="account-menu-item"><ShieldCheck size={17}/> Listing reviews</Link>}
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
        {auth.profile?.roles.some(r=>r==='admin'||r==='editor') && <Link to="/admin" onClick={()=>setOpened(false)} className="block py-3">Content dashboard</Link>}
        {auth.profile?.roles.some(r=>r==='admin'||r==='editor') && <Link to="/admin/geo-quality" onClick={()=>setOpened(false)} className="block py-3">Map quality report</Link>}
        <Link to="/vendors" onClick={()=>setOpened(false)} className="block py-3">My businesses</Link>
        <Link to="/vendor/listings" onClick={()=>setOpened(false)} className="block py-3">Manage listings</Link>
        <Link to="/vendor/enquiries" onClick={()=>setOpened(false)} className="block py-3">Provider enquiries</Link>
        <Link to="/vendor/feedback" onClick={()=>setOpened(false)} className="block py-3">Customer feedback</Link>
        {auth.profile?.roles.includes('admin') && <Link to="/admin/vendors" onClick={()=>setOpened(false)} className="block py-3">Vendor verification</Link>}
        {auth.profile?.roles.includes('admin') && <Link to="/admin/enquiry-reports" onClick={()=>setOpened(false)} className="block py-3">Enquiry reports</Link>}
        {auth.profile?.roles.includes('admin') && <Link to="/admin/customer-reviews" onClick={()=>setOpened(false)} className="block py-3">Feedback moderation</Link>}
        {auth.profile?.roles.includes('admin') && <Link to="/admin/listings" onClick={()=>setOpened(false)} className="block py-3">Listing reviews</Link>}
        <Link to="/notifications" onClick={()=>setOpened(false)} className="flex items-center gap-3 py-3"><Bell size={17}/> Notifications {unread>0?`(${unread})`:''}</Link>
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
