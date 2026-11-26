import {useCallback,useEffect,useState,type FormEvent} from 'react'
import {Link} from 'react-router-dom'
import {Bell,CheckCheck,Megaphone,RefreshCw} from 'lucide-react'
import {useTourismoAuth} from '../app/Auth'
import {allNotifications,markNotificationRead,markAllNotificationsRead,publishReleaseAnnouncement,
  emailPreferences,setEmailPreferences,type EmailPreferences,type NotificationItem,type AnnouncementWrite} from '../lib/api'

export function Notifications(){
  const auth=useTourismoAuth()
  const [items,setItems]=useState<NotificationItem[]>([])
  const [unread,setUnread]=useState(0)
  const [hasMore,setHasMore]=useState(false)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [preferences,setPreferences] = useState<EmailPreferences|null>(null)
  const [emailSaving,setEmailSaving] = useState(false)
  const [release,setRelease]=useState<AnnouncementWrite>({release_key:'',title:'',body:'',target_url:'/discover',expires_in_days:30})
  const admin=auth.profile?.roles.includes('admin')===true

  const load=useCallback(async(more=false)=>{
    if(!auth.signedIn)return
    setLoading(true);setError('')
    try{
      const token=await auth.token();if(!token)return
      const result=await allNotifications(token,more?items.length:0)
      setItems(old=>more?[...old,...result.items.filter(x=>!old.some(p=>p.id===x.id))]:result.items)
      setUnread(result.unread_count);setHasMore(result.has_more)
    }catch(e){setError(e instanceof Error?e.message:'Unable to load notifications')}
    finally{setLoading(false)}
  },[auth.signedIn,auth.token,items.length])
  useEffect(()=>{setItems([]);setUnread(0);setPreferences(null);void load();
    if(auth.signedIn)void auth.token().then(t=>t?emailPreferences(t):null).then(setPreferences).catch(()=>setPreferences(null))
  },[auth.signedIn,auth.profile?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  async function saveEmailSettings(next: Pick<EmailPreferences,'activity_enabled'|'releases_enabled'>){
    setEmailSaving(true);setError('');setNotice('')
    try{const token=await auth.token();if(!token)throw new Error('Please sign in again')
      const result=await setEmailPreferences(next,token);setPreferences(result)
      setNotice('Email preferences saved. New notifications follow these settings.')
    }catch(e){setError(e instanceof Error?e.message:'Unable to save email settings')}
    finally{setEmailSaving(false)}
  }
  async function mark(item:NotificationItem){
    if(item.read)return
    try{
      const token=await auth.token();if(!token)return
      await markNotificationRead(item.id,token)
      setItems(old=>old.map(x=>x.id===item.id?{...x,read:true}:x));setUnread(n=>Math.max(0,n-1))
    }catch(e){setError(e instanceof Error?e.message:'Unable to mark notification read')}
  }
  async function markAll(){
    try{const token=await auth.token();if(!token)return
      await markAllNotificationsRead(token)
      setItems(old=>old.map(x=>({...x,read:true})));setUnread(0)
    }catch(e){setError(e instanceof Error?e.message:'Unable to mark notifications read')}
  }
  async function announce(event:FormEvent){
    event.preventDefault();setError('');setNotice('')
    if(!window.confirm('Publish this release announcement to eligible Tourismo users?'))return
    try{const token=await auth.token();if(!token)return
      await publishReleaseAnnouncement(release,token)
      setNotice('Release published in-app. Opted-in members may receive an email when the delivery worker is configured.')
      setRelease({release_key:'',title:'',body:'',target_url:'/discover',expires_in_days:30})
      await load()
    }catch(e){setError(e instanceof Error?e.message:'Unable to publish release announcement')}
  }
  return <main className="wrap min-h-[65vh] py-12 pb-24" aria-labelledby="notifications-title">
    <p className="small-label">YOUR PRIVATE INBOX</p>
    <h1 id="notifications-title" className="page-title flex items-center gap-3"><Bell aria-hidden="true"/> Notifications</h1>
    <p className="lead">Account updates, reviews, replies, enquiries and Tourismo announcements. In-app updates are always available. Email alerts can be enabled when the mail service is configured.</p>
    {!auth.signedIn?<button className="btn-primary mt-8" onClick={auth.login}>Sign in to see notifications</button>:<>
      <div className="flex flex-wrap items-center gap-3 mt-6">
        <span className="font-semibold" aria-live="polite">{unread} unread</span>
        <button type="button" disabled={loading} onClick={()=>void load()} className="btn-secondary"><RefreshCw size={16}/> Refresh</button>
        <button type="button" disabled={unread===0} onClick={()=>void markAll()} className="btn-secondary"><CheckCheck size={16}/> Mark all read</button>
      </div>
      <section className="form-panel mt-6 space-y-3" aria-label="Email notification preferences">
        <h2 className="text-lg font-bold">Email alerts</h2>
        <p className="text-sm text-ink/70">Get important activity outside Tourismo. Your email address comes from your verified sign-in account. Release announcements are optional.</p>
        {!preferences ? <p className="text-sm text-ink/70">Email settings are unavailable at the moment.</p> : <>
          {!preferences.verified_email_available && <p role="status" className="text-sm text-amber-800">Sign in with a verified email address before mail can be delivered.</p>}
          {!preferences.delivery_configured && <p role="status" className="text-sm text-amber-800">Email delivery is not yet enabled by Tourismo. Your in-app notifications still work.</p>}
          <label className="flex gap-3 items-start"><input type="checkbox" className="mt-1" disabled={emailSaving} checked={preferences.activity_enabled}
            onChange={e=>void saveEmailSettings({activity_enabled:e.target.checked,releases_enabled:preferences.releases_enabled})}/>
            <span><strong className="block">Important activity</strong><span className="text-sm text-ink/65">Reviews, enquiries, replies and business decisions</span></span></label>
          <label className="flex gap-3 items-start"><input type="checkbox" className="mt-1" disabled={emailSaving} checked={preferences.releases_enabled}
            onChange={e=>void saveEmailSettings({activity_enabled:preferences.activity_enabled,releases_enabled:e.target.checked})}/>
            <span><strong className="block">Product updates</strong><span className="text-sm text-ink/65">Opt in to emails about Tourismo releases and major improvements</span></span></label>
        </>}
      </section>
      {error&&<p role="alert" className="error-banner mt-4">{error}</p>}
      {notice&&<p role="status" className="success-banner mt-4">{notice}</p>}
      <section aria-label="Recent notifications" className="space-y-3 mt-6">
        {!loading&&items.length===0&&<p className="info-banner">No notifications yet. New account and service activity will appear here.</p>}
        {items.map(item=><article key={item.id} className={`form-panel space-y-2 ${item.read?'opacity-80':'border-l-4 border-l-pine'}`}>
          <div className="flex flex-wrap items-start justify-between gap-2"><div className="flex items-center gap-2">
            {item.announcement&&<Megaphone size={18} className="text-pine"/>}
            <h2 className="font-bold">{item.title}</h2>
            {!item.read&&<span className="rounded-full bg-pine text-white px-2 py-0.5 text-xs">New</span>}
          </div><time className="text-xs text-ink/60" dateTime={item.created_at??undefined}>{item.created_at?new Date(item.created_at).toLocaleString():'Recently'}</time></div>
          <p className="text-sm text-ink/80 whitespace-pre-wrap break-words">{item.body}</p>
          <div className="flex gap-4 items-center flex-wrap text-sm"><Link to={item.target_url} onClick={()=>void mark(item)} className="underline text-pine">View details</Link>
            {!item.read&&<button className="underline text-ink/75" type="button" onClick={()=>void mark(item)}>Mark as read</button>}</div>
        </article>)}
      </section>
      {hasMore&&<button type="button" className="btn-secondary mt-4" disabled={loading} onClick={()=>void load(true)}>{loading?'Loading…':'See older notifications'}</button>}
    </>}
    {admin&&<section className="form-panel mt-12 space-y-4" aria-label="Publish platform release notification">
      <h2 className="text-xl font-bold">Publish a Tourismo release announcement</h2>
      <p className="text-sm text-ink/70">Administrator-only. Announce after the release has passed deployment verification. This creates an in-app announcement. Members who opted in to release emails may also receive an email when a delivery worker is enabled.</p>
      <form onSubmit={e=>void announce(e)} className="grid gap-4">
        <label className="field">Unique release key<input required minLength={4} maxLength={64} pattern="[a-zA-Z0-9][a-zA-Z0-9._-]{3,63}" value={release.release_key} onChange={e=>setRelease(s=>({...s,release_key:e.target.value}))} placeholder="tourismo-1.9.3"/></label>
        <label className="field">Announcement title<input required minLength={8} maxLength={160} value={release.title} onChange={e=>setRelease(s=>({...s,title:e.target.value}))}/></label>
        <label className="field">What's new?<textarea required minLength={15} maxLength={600} rows={3} value={release.body} onChange={e=>setRelease(s=>({...s,body:e.target.value}))}/></label>
        <label className="field">Link to an internal page<input required pattern="/[a-zA-Z0-9/_-]*" value={release.target_url} onChange={e=>setRelease(s=>({...s,target_url:e.target.value}))}/></label>
        <label className="field">Show for (days)<input type="number" min={1} max={90} value={release.expires_in_days} onChange={e=>setRelease(s=>({...s,expires_in_days:Number(e.target.value)}))}/></label>
        <button className="btn-primary" type="submit"><Megaphone size={17}/> Publish in-app announcement</button>
      </form>
    </section>}
  </main>
}
