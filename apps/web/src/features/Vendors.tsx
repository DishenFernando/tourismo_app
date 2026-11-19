import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Building2, CheckCircle2, ClipboardList, LockKeyhole, Plus, RefreshCw, ShieldCheck, UserRound, Users } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { acceptVendorInvitation, addVendorEvidence, createVendorOrganization, editVendorOrganization, inviteVendorMember,
  submitVendorOrganization, vendorEvidence, vendorInvitations, vendorMembers, vendorOrganizations,
  type VendorApplication, type VendorCategory, type VendorEvidence, type VendorInvitation,
  type VendorMember, type VendorOrganization } from '../lib/api'

const categories: {value:VendorCategory;label:string}[] = [
  {value:'accommodation',label:'Accommodation / hotel'}, {value:'restaurant',label:'Restaurant / cafe'},
  {value:'guide',label:'Tourist guide'}, {value:'transport',label:'Transport provider'},
  {value:'tour_operator',label:'Tour operator'}, {value:'activity',label:'Activity / experience'}
]
const emptyApplication:VendorApplication = {category:'accommodation',business_name:'',registration_no:null,
  contact_email:'',contact_phone:null,province:'',district:'',operating_address:'',license_no:null}
const initialEvidence:Omit<VendorEvidence,'id'> = {evidence_type:'business_registration',issuer:'',reference_number:'',expires_on:null}

export function Vendors() {
  const auth=useTourismoAuth()
  const [organizations,setOrganizations]=useState<VendorOrganization[]>([])
  const [selected,setSelected]=useState<string|null>(null)
  const [references,setReferences]=useState<VendorEvidence[]>([])
  const [members,setMembers]=useState<VendorMember[]>([])
  const [invitations,setInvitations]=useState<VendorInvitation[]>([])
  const [newBusiness,setNewBusiness]=useState<VendorApplication>(emptyApplication)
  const [editing,setEditing]=useState(false)
  const [applicationEdit,setApplicationEdit]=useState<VendorApplication>(emptyApplication)
  const [newEvidence,setNewEvidence]=useState<Omit<VendorEvidence,'id'>>(initialEvidence)
  const [inviteId,setInviteId]=useState('')
  const [inviteRole,setInviteRole]=useState<'manager'|'staff'>('staff')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [showCreate,setShowCreate]=useState(false)
  const current=organizations.find(o=>o.id===selected)
  const owner=!!current && current.owner_id===auth.profile?.id
  const editable=!!current && ['draft','changes_requested','rejected'].includes(current.verification_state)

  const refresh=useCallback(async()=>{
    const jwt=await auth.token()
    if (!jwt) return
    const [orgs,invites]=await Promise.all([vendorOrganizations(jwt),vendorInvitations(jwt)])
    setOrganizations(orgs);setInvitations(invites)
    setSelected(previous=>previous && orgs.some(o=>o.id===previous)?previous:(orgs[0]?.id||null))
  },[auth.token])
  useEffect(()=>{if(auth.signedIn)void refresh().catch(e=>setError(String(e)))},[auth.signedIn,refresh])
  useEffect(()=>{
    if (!selected || !auth.signedIn) {setReferences([]);setMembers([]);return}
    let active=true
    void (async()=>{try {const jwt=await auth.token();if(!jwt)return
      const [refs,team]=await Promise.all([vendorEvidence(selected,jwt),vendorMembers(selected,jwt)])
      if(active){setReferences(refs);setMembers(team)}
    }catch(e){if(active)setError(e instanceof Error?e.message:'Could not load private business details')}})()
    return()=>{active=false}
  },[selected,auth.signedIn,auth.token])
  async function run(action:(jwt:string)=>Promise<unknown>,message:string) {
    setBusy(true);setError('');setNotice('')
    try {const jwt=await auth.token();if(!jwt)throw new Error('Please sign in again')
      await action(jwt);await refresh();setNotice(message)
      if(selected){const [refs,team]=await Promise.all([vendorEvidence(selected,jwt),vendorMembers(selected,jwt)]);setReferences(refs);setMembers(team)}
    }catch(e){setError(e instanceof Error?e.message:'Request failed')}finally{setBusy(false)}
  }
  function create(e:FormEvent){e.preventDefault();void run(async jwt=>{
    const org=await createVendorOrganization(newBusiness,jwt)
    setNewBusiness(emptyApplication);setSelected(org.id);setShowCreate(false)
  },'Your private application has been created. Add reference information before submitting.')}
  function saveChanges(e:FormEvent){e.preventDefault();if(!current)return
    void run(async jwt=>{await editVendorOrganization(current.id,{business_name:applicationEdit.business_name,registration_no:applicationEdit.registration_no,contact_email:applicationEdit.contact_email,contact_phone:applicationEdit.contact_phone,province:applicationEdit.province,district:applicationEdit.district,operating_address:applicationEdit.operating_address,license_no:applicationEdit.license_no},jwt);setEditing(false)},'Application details updated.')
  }
  function addEvidence(e:FormEvent){e.preventDefault();if(!current)return
    void run(jwt=>addVendorEvidence(current.id,newEvidence,jwt),'Reference recorded for manual verification.')
    setNewEvidence(initialEvidence)
  }
  function invite(e:FormEvent){e.preventDefault();if(!current)return
    void run(jwt=>inviteVendorMember(current.id,inviteId,inviteRole,jwt),'Invitation created. The invited user must accept in their Tourismo account.')
    setInviteId('')
  }
  return <main className="wrap py-12 pb-24 min-h-[70vh]">
    <span className="small-label">TOURISMO FOR BUSINESS</span>
    <h1 className="page-title">Your business dashboard</h1>
    <p className="lead">Register your tourism organization, submit license references, and track human verification. Nothing becomes a public listing automatically.</p>
    {!auth.signedIn && <section className="empty-state mt-8"><LockKeyhole size={36}/><h2 className="text-xl font-bold">Sign in to register a business</h2><p>Google or verified email sign-in is required for accountable business ownership.</p><button className="btn-primary mt-4" onClick={auth.login}>Sign in / Create account</button></section>}
    {auth.signedIn && <div className="space-y-6 mt-8">
      {error&&<p role="alert" className="error-banner">{error}</p>}
      {notice&&<p role="status" className="success-banner"><CheckCircle2 size={18}/>{notice}</p>}
      <div className="flex flex-wrap gap-3 items-center justify-between"><h2 className="text-xl font-bold">My organizations</h2><button className="btn-primary" onClick={()=>setShowCreate(v=>!v)}><Plus size={17}/> {showCreate?'Close form':'Register business'}</button></div>
      {showCreate&&<form onSubmit={create} className="form-panel grid gap-4 sm:grid-cols-2">
        <label className="field">Business category<select value={newBusiness.category} onChange={e=>setNewBusiness(v=>({...v,category:e.target.value as VendorCategory}))}>{categories.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
        <label className="field">Legal business name *<input required minLength={2} maxLength={160} value={newBusiness.business_name} onChange={e=>setNewBusiness(v=>({...v,business_name:e.target.value}))}/></label>
        <label className="field">Business email *<input required type="email" maxLength={320} value={newBusiness.contact_email} onChange={e=>setNewBusiness(v=>({...v,contact_email:e.target.value}))}/></label>
        <label className="field">Phone (optional)<input maxLength={40} value={newBusiness.contact_phone||''} onChange={e=>setNewBusiness(v=>({...v,contact_phone:e.target.value||null}))}/></label>
        <label className="field">Business registration number<input maxLength={120} value={newBusiness.registration_no||''} onChange={e=>setNewBusiness(v=>({...v,registration_no:e.target.value||null}))}/></label>
        <label className="field">Tourism / professional license number<input maxLength={120} value={newBusiness.license_no||''} onChange={e=>setNewBusiness(v=>({...v,license_no:e.target.value||null}))}/></label>
        <label className="field">Province *<input required maxLength={120} value={newBusiness.province} onChange={e=>setNewBusiness(v=>({...v,province:e.target.value}))}/></label>
        <label className="field">District *<input required maxLength={120} value={newBusiness.district} onChange={e=>setNewBusiness(v=>({...v,district:e.target.value}))}/></label>
        <label className="field sm:col-span-2">Operating address (private) *<textarea required minLength={6} maxLength={800} rows={2} value={newBusiness.operating_address} onChange={e=>setNewBusiness(v=>({...v,operating_address:e.target.value}))}/></label>
        <p className="text-xs text-ink/60 sm:col-span-2">Your business data stays private during review. Registration numbers are not considered verified just because you enter them.</p>
        <button type="submit" disabled={busy} className="btn-primary sm:col-span-2 justify-center">{busy?'Creating…':'Create application'}</button>
      </form>}
      {organizations.length===0&&!showCreate&&<section className="empty-state"><Building2 size={32}/><p>No businesses registered yet. Start with your organization's legal details.</p></section>}
      {organizations.length>0&&<div className="grid gap-6 lg:grid-cols-[minmax(220px,.8fr)_minmax(0,1.5fr)] items-start">
        <nav aria-label="Your organizations" className="form-panel space-y-2">
          {organizations.map(o=><button key={o.id} type="button" onClick={()=>{setSelected(o.id);setError('');setNotice('')}} className={`w-full p-3 text-left rounded-xl border ${selected===o.id?'border-pine bg-[#eaf5ef]':'border-ink/10'}`}>
            <span className="block font-bold">{o.business_name}</span><span className="text-xs text-ink/60 capitalize">{o.category.replace('_',' ')} · {o.verification_state.replace('_',' ')}</span>
          </button>)}
        </nav>
        {current&&<section className="form-panel space-y-5"><div className="flex justify-between items-start gap-3 flex-wrap"><div><h2 className="text-xl font-extrabold">{current.business_name}</h2><p className="text-sm text-ink/60">{current.district}, {current.province}</p></div><span className="rounded-full bg-[#e9f4ed] text-pine px-3 py-1 text-sm font-bold capitalize">{current.verification_state.replace('_',' ')}</span></div>
          <p className="text-sm text-ink/70">Business contact: {current.contact_email} · {current.contact_phone||'No phone provided'}</p>
          {current.review_feedback&&<div className="border border-amber-200 bg-amber-50 rounded-xl p-4 text-sm"><b>Administrator feedback:</b> {current.review_feedback}</div>}
          {editable&&<button type="button" className="text-sm text-pine underline" onClick={()=>{setApplicationEdit({category:current.category,business_name:current.business_name,registration_no:current.registration_no,contact_email:current.contact_email,contact_phone:current.contact_phone,province:current.province,district:current.district,operating_address:current.operating_address,license_no:current.license_no});setEditing(v=>!v)}}>{editing?'Close editor':'Edit application details'}</button>}
          {editing&&editable&&<form onSubmit={saveChanges} className="grid sm:grid-cols-2 gap-3">
            {(['business_name','contact_email','registration_no','license_no','contact_phone','district','province'] as const).map(field=><label key={field} className="field capitalize">{field.replaceAll('_',' ')}<input required={['business_name','contact_email','district','province'].includes(field)} value={applicationEdit[field]||''} onChange={e=>setApplicationEdit(v=>({...v,[field]:e.target.value||null}))}/></label>)}
            <label className="field sm:col-span-2">Operating address<textarea required minLength={6} maxLength={800} value={applicationEdit.operating_address} onChange={e=>setApplicationEdit(v=>({...v,operating_address:e.target.value}))}/></label>
            <button type="submit" disabled={busy} className="btn-primary sm:col-span-2 justify-center">Save changes</button>
          </form>}
          <div className="info-banner"><ShieldCheck size={19}/> {current.verification_state==='approved'?'Organization verification approved. Public listing setup and subscription trials are separate future steps.':current.verification_state==='submitted'?'Awaiting independent administrator review. Business details are locked during review.':'Verification is not complete. The business will not be discoverable until it has approved listings in a later phase.'}</div>
          <h3 className="font-extrabold">License & registration references</h3>
          <p className="text-sm text-ink/60">Reference details are private and require manual cross-checking. Document uploads are not enabled in this release.</p>
          {references.map(r=><p key={r.id} className="text-sm border border-ink/10 rounded-lg p-3"><b>{r.evidence_type.replaceAll('_',' ')}</b> · {r.issuer} · {r.reference_number}{r.expires_on?` · Expires ${r.expires_on}`:''}</p>)}
          {editable&&<form onSubmit={addEvidence} className="grid gap-3 sm:grid-cols-2">
            <label className="field">Reference type<select value={newEvidence.evidence_type} onChange={e=>setNewEvidence(v=>({...v,evidence_type:e.target.value as VendorEvidence['evidence_type']}))}><option value="business_registration">Business registration</option><option value="tourism_license">Tourism license</option><option value="professional_license">Professional license</option><option value="other_permit">Other permit</option></select></label>
            <label className="field">Issuing authority *<input required minLength={2} maxLength={160} value={newEvidence.issuer} onChange={e=>setNewEvidence(v=>({...v,issuer:e.target.value}))}/></label>
            <label className="field">Reference number *<input required minLength={3} maxLength={160} value={newEvidence.reference_number} onChange={e=>setNewEvidence(v=>({...v,reference_number:e.target.value}))}/></label>
            <label className="field">Expiration (if applicable)<input type="date" value={newEvidence.expires_on||''} onChange={e=>setNewEvidence(v=>({...v,expires_on:e.target.value||null}))}/></label>
            <button disabled={busy} type="submit" className="btn-secondary sm:col-span-2 justify-center"><Plus size={16}/> Add reference</button>
          </form>}
          {editable&&<div className="border-t border-ink/10 pt-4"><p className="text-sm text-ink/60">Submission needs a registration/license number and at least one unexpired evidence reference.</p><button disabled={busy} className="btn-primary mt-3" onClick={()=>void run(jwt=>submitVendorOrganization(current.id,jwt),'Submitted for manual verification.')}><ClipboardList size={16}/> Submit for verification</button></div>}
          <div className="border-t border-ink/10 pt-4"><h3 className="font-extrabold flex items-center gap-2"><Users size={18}/> Team members</h3><div className="mt-3 space-y-1">{members.map(m=><p className="text-xs text-ink/70" key={m.id}>{m.role} · {m.state} · {m.user_id}</p>)}</div>
            {owner&&<form className="grid gap-3 sm:grid-cols-2 mt-4" onSubmit={invite}><label className="field sm:col-span-2">Existing Tourismo user ID<input required value={inviteId} onChange={e=>setInviteId(e.target.value)} placeholder="UUID from the invited user's profile"/></label><label className="field">Role<select value={inviteRole} onChange={e=>setInviteRole(e.target.value as 'staff'|'manager')}><option value="staff">Staff (read-only)</option><option value="manager">Manager (edit drafts)</option></select></label><button type="submit" disabled={busy} className="btn-secondary self-end justify-center">Invite team member</button></form>}
          </div>
        </section>}
      </div>}
      {invitations.length>0&&<section className="form-panel"><h2 className="text-lg font-extrabold">Team invitations</h2>{invitations.map(inv=><div key={inv.id} className="flex items-center justify-between py-3 gap-3"><p className="text-sm">Invitation for organization {inv.organization_id} · {inv.role}</p><button disabled={busy} className="btn-secondary" onClick={()=>void run(jwt=>acceptVendorInvitation(inv.id,jwt),'Invitation accepted.')}>Accept</button></div>)}</section>}
      <div className="text-sm text-ink/60 flex gap-2 items-start"><UserRound size={17}/><p>Your Tourismo profile remains a personal tourist account. You can register a business without losing access to your saved trips. <Link to="/account" className="underline text-pine">Manage profile</Link>.</p></div>
      <button onClick={()=>void refresh().catch(e=>setError(String(e)))} className="text-sm text-pine underline inline-flex items-center gap-2"><RefreshCw size={15}/> Refresh organizations</button>
    </div>}
  </main>
}
