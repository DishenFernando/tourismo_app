import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, ChevronRight, LockKeyhole, RefreshCw, Save, ShieldCheck, UserRound } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { updateProfile, type ProfileInput } from '../lib/api'

export function Account() {
  const auth = useTourismoAuth()
  const [name,setName] = useState('')
  const [locale,setLocale] = useState<ProfileInput['locale']>('en')
  const [region,setRegion] = useState('')
  const [bio,setBio] = useState('')
  const [busy,setBusy] = useState(false)
  const [message,setMessage] = useState('')
  const [error,setError] = useState('')
  useEffect(()=>{
    if (!auth.profile) return
    setName(auth.profile.display_name||(auth.person?.name==='Traveler'?'':auth.person?.name)||'')
    setLocale(auth.profile.locale)
    setRegion(auth.profile.home_region||'')
    setBio(auth.profile.bio||'')
  },[auth.profile,auth.person?.name])
  useEffect(()=>{
    if (auth.profile || !auth.person || auth.profileState !== 'ready') return
    setName(auth.person.name === 'Traveler' ? '' : auth.person.name)
  },[auth.profile,auth.person,auth.profileState])
  const save=async(event:FormEvent<HTMLFormElement>)=>{
    event.preventDefault();setError('');setMessage('');setBusy(true)
    try{
      const jwt=await auth.token()
      if(!jwt) throw new Error('Session unavailable. Please log in again.')
      const saved=await updateProfile({display_name:name,locale,home_region:region||null,bio:bio||null},jwt)
      auth.setProfile(saved)
      setMessage('Your Tourismo profile has been saved successfully.')
    } catch(exc){setError(exc instanceof Error?exc.message:'Could not update profile')}
    finally{setBusy(false)}
  }
  return <main className="wrap pb-20 pt-12 min-h-[65vh]">
    <span className="small-label">YOUR TOURISMO ACCOUNT</span>
    <h1 className="page-title">Your travel profile</h1>
    <p className="lead">Make Tourismo your own. Your profile stays private by default and never appears in public search results.</p>
    {!auth.enabled && <section className="empty-state"><LockKeyhole size={36}/><p>Configure Clerk to enable personal accounts.</p></section>}
    {auth.enabled&&!auth.signedIn && <section className="empty-state"><UserRound size={36}/><h2 className="text-xl font-bold">Sign in to create your profile</h2><p>Browsing and planning remain free without an account.</p><button className="btn-primary mt-5" onClick={auth.login}>Google or email sign-in</button></section>}
    {auth.signedIn && <div className="mt-9 grid gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(270px,1fr)] items-start">
      <div className="space-y-5">
        <section className="form-panel">
          <div className="flex flex-wrap items-center gap-4 mb-6">
            {auth.person?.avatar ? <img src={auth.person.avatar} alt="Your profile avatar" referrerPolicy="no-referrer" className="h-20 w-20 rounded-2xl object-cover"/> : <div className="grid h-20 w-20 place-items-center rounded-2xl bg-[#e6f4ee]"><UserRound className="text-pine" size={30}/></div>}
            <div><p className="font-bold text-lg">{auth.person?.name||'Welcome to Tourismo'}</p><p className="text-sm text-ink/60">{auth.person?.email||'Email not available'}</p><p className="text-xs text-pine mt-1">Signed in with verified Clerk authentication</p>{auth.profile&&<p className="text-xs text-ink/50 mt-2 break-all">Tourismo user ID for team invitations: <code>{auth.profile.id}</code> <button type="button" className="underline text-pine" onClick={()=>void navigator.clipboard.writeText(auth.profile!.id)}>Copy</button></p>}</div>
          </div>
          {auth.profileState==='syncing'&&<p role="status" className="info-banner">Creating or retrieving your Tourismo profile…</p>}
          {auth.profileState==='error'&&<div role="alert" className="error-banner flex-wrap"><span>Profile sync failed: {auth.profileError}</span><button className="underline font-bold" onClick={()=>{setError('');void auth.refreshProfile().catch(e=>setError(e instanceof Error?e.message:'Retry failed'))}}>Retry</button></div>}
          {auth.profile&&!auth.profile.profile_completed && <p className="info-banner mb-5">Welcome! Finish your profile now or later. Your saved trips work independently of profile completion.</p>}
          {message&&<p role="status" className="success-banner mb-5"><CheckCircle2 size={19}/>{message}</p>}
          {error&&<p role="alert" className="error-banner mb-5">{error}</p>}
          <form onSubmit={e=>void save(e)} className="space-y-5">
            <label className="field"><span>Display name *</span><input required minLength={2} maxLength={160} value={name} placeholder="How should we address you?" onChange={e=>setName(e.target.value)}/></label>
            <div className="grid gap-4 sm:grid-cols-2"><label className="field"><span>Preferred language</span><select value={locale} onChange={e=>setLocale(e.target.value as ProfileInput['locale'])}>
              <option value="en">English</option><option value="si">සිංහල (Sinhala)</option><option value="ta">தமிழ் (Tamil)</option>
            </select></label>
            <label className="field"><span>Home region (optional)</span><input value={region} maxLength={120} placeholder="e.g. Colombo" onChange={e=>setRegion(e.target.value)}/></label></div>
            <label className="field"><span>About your travel interests (optional)</span><textarea value={bio} maxLength={500} rows={4} placeholder="Nature, culture, food, family trips…" onChange={e=>setBio(e.target.value)}/><span className="text-xs text-ink/50">{bio.length}/500 characters · Private profile information</span></label>
            <button disabled={busy||!auth.profile} type="submit" className="btn-primary"><Save size={17}/>{busy?'Saving…':'Save my profile'}</button>
          </form>
        </section>
      </div>
      <aside className="space-y-5">
        <div className="form-panel"><ShieldCheck size={29} className="text-pine"/><h2 className="font-extrabold text-lg mt-3">Your account security</h2>
          <p className="text-sm text-ink/60 mt-2 leading-6">Google/email identity, verification and avatar are managed securely by Clerk. Your Tourismo profile and trips are stored separately in PostgreSQL.</p>
          <button onClick={auth.manageAccount} className="btn-secondary mt-5 w-full justify-center">Manage sign-in methods <ChevronRight size={16}/></button>
          <p className="text-xs text-ink/50 mt-3">Changing an email address must be verified through Clerk; it cannot be edited directly in this form.</p>
        </div>
        <div className="form-panel"><h2 className="font-extrabold text-lg">Personal space</h2><p className="text-sm text-ink/60 mt-2">Your saved trips are available only to your authenticated account.</p>
          <Link className="btn-secondary mt-4" to="/saved">View my saved trips <ChevronRight size={16}/></Link>
          {auth.profileState==='ready'&&<p className="text-xs text-ink/50 mt-4 flex items-center gap-1"><RefreshCw size={13}/> Profile linked to your account</p>}
        </div>
      </aside>
    </div>}
  </main>
}
