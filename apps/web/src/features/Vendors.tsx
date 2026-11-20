import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Building2, CheckCircle2, ClipboardList, LockKeyhole, Plus, RefreshCw, ShieldCheck, UserRound, Users } from 'lucide-react'
import { useTourismoAuth } from '../app/Auth'
import { allDistricts, provinceForDistrict } from '../lib/sriLankaRegions'
import { acceptVendorInvitation, inviteVendorMemberByEmail, addVendorEvidence, createVendorOrganization, editVendorOrganization,
  submitVendorOrganization, vendorEvidence, vendorInvitations, vendorMembers, vendorOrganizations,
  vendorDocuments, vendorCompliance, uploadVendorDocument, deleteVendorDocument, downloadVendorDocument, startVendorRenewal,
  type VendorDocument, type VendorCompliance,
  type VendorApplication, type VendorCategory, type VendorEvidence, type VendorInvitation,
  type VendorMember, type VendorOrganization } from '../lib/api'

const categories: {value:VendorCategory;label:string}[] = [
  {value:'accommodation',label:'Accommodation / hotel'}, {value:'restaurant',label:'Restaurant / cafe'},
  {value:'guide',label:'Tourist guide'}, {value:'transport',label:'Transport provider'},
  {value:'tour_operator',label:'Tour operator'}, {value:'activity',label:'Activity / experience'}
]
const emptyApplication:VendorApplication = {category:'accommodation',business_name:'',registration_no:null,
  contact_email:'',contact_phone:null,province:null,district:null,operating_address:null,license_no:null}
const initialEvidence:Omit<VendorEvidence,'id'> = {evidence_type:'business_registration',issuer:'',reference_number:'',expires_on:null}

export function Vendors() {
  const auth=useTourismoAuth()
  const [organizations,setOrganizations]=useState<VendorOrganization[]>([])
  const [selected,setSelected]=useState<string|null>(null)
  const [references,setReferences]=useState<VendorEvidence[]>([])
  const [members,setMembers]=useState<VendorMember[]>([])
  const [documents,setDocuments]=useState<VendorDocument[]>([])
  const [compliance,setCompliance]=useState<VendorCompliance|null>(null)
  const [file,setFile]=useState<File|null>(null)
  const [evidenceId,setEvidenceId]=useState('')
  const [invitations,setInvitations]=useState<VendorInvitation[]>([])
  const [newBusiness,setNewBusiness]=useState<VendorApplication>(emptyApplication)
  const [editing,setEditing]=useState(false)
  const [applicationEdit,setApplicationEdit]=useState<VendorApplication>(emptyApplication)
  const [newEvidence,setNewEvidence]=useState<Omit<VendorEvidence,'id'>>(initialEvidence)
  const [inviteEmail,setInviteEmail]=useState('')
  const [combinedDocument,setCombinedDocument]=useState<File|null>(null)
  const [inviteRole,setInviteRole]=useState<'manager'|'staff'>('staff')
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')
  const [notice,setNotice]=useState('')
  const [showCreate,setShowCreate]=useState(false)
  const [vendorTab,setVendorTab]=useState<'details'|'verification'|'team'>('details')
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
    if (!selected || !auth.signedIn) {setReferences([]);setMembers([]);setDocuments([]);setCompliance(null);return}
    let active=true
    void (async()=>{try {const jwt=await auth.token();if(!jwt)return
      const [refs,team,docs,check]=await Promise.all([vendorEvidence(selected,jwt),vendorMembers(selected,jwt),vendorDocuments(selected,jwt),vendorCompliance(selected,jwt)])
      if(active){setReferences(refs);setMembers(team);setDocuments(docs);setCompliance(check)}
    }catch(e){if(active)setError(e instanceof Error?e.message:'Could not load private business details')}})()
    return()=>{active=false}
  },[selected,auth.signedIn,auth.token])
  async function run(action:(jwt:string)=>Promise<unknown>,message:string) {
    setBusy(true);setError('');setNotice('')
    try {const jwt=await auth.token();if(!jwt)throw new Error('Please sign in again')
      await action(jwt);await refresh();setNotice(message)
      if(selected){const [refs,team,docs,check]=await Promise.all([vendorEvidence(selected,jwt),vendorMembers(selected,jwt),vendorDocuments(selected,jwt),vendorCompliance(selected,jwt)]);setReferences(refs);setMembers(team);setDocuments(docs);setCompliance(check)}
    }catch(e){setError(e instanceof Error?e.message:'Request failed')}finally{setBusy(false)}
  }
  function create(e:FormEvent){e.preventDefault();void run(async jwt=>{
    const org=await createVendorOrganization(newBusiness,jwt)
    setNewBusiness(emptyApplication);setSelected(org.id);setVendorTab('details');setShowCreate(false)
  },'Your private application has been created. Add reference information before submitting.')}
  function saveChanges(e:FormEvent){e.preventDefault();if(!current)return
    void run(async jwt=>{await editVendorOrganization(current.id,{business_name:applicationEdit.business_name,registration_no:applicationEdit.registration_no,contact_email:applicationEdit.contact_email,contact_phone:applicationEdit.contact_phone,province:applicationEdit.province,district:applicationEdit.district,operating_address:applicationEdit.operating_address,license_no:applicationEdit.license_no},jwt);setEditing(false)},'Application details updated.')
  }
  function addEvidence(e:FormEvent){e.preventDefault();if(!current)return
    if(combinedDocument&&combinedDocument.size>5*1024*1024){setError('Document exceeds the 5 MB limit');return}
    void run(async jwt=>{
      const saved=await addVendorEvidence(current.id,newEvidence,jwt)
      if(combinedDocument){
        try{await uploadVendorDocument(current.id,saved.id,combinedDocument,jwt)}
        catch(error){throw new Error(`License reference saved, but attachment failed. Select it below to retry: ${error instanceof Error?error.message:String(error)}`)}
      }
      setNewEvidence(initialEvidence);setCombinedDocument(null)
    },combinedDocument?'License reference and private document saved for scanning.':'License reference saved for review.')
  }
  function invite(e:FormEvent){e.preventDefault();if(!current)return
    void run(async jwt=>{await inviteVendorMemberByEmail(current.id,inviteEmail,inviteRole,jwt);setInviteEmail('')},
      'Private invitation created. Ask the invited user to open Tourismo and accept under Team invitations.')
  }
  return <main className="wrap py-12 pb-24 min-h-[70vh]">
    <span className="small-label">TOURISMO FOR BUSINESS</span>
    <h1 className="page-title">Your business dashboard</h1>
    <p className="lead">Register your tourism organization, submit license references, and track human verification. Nothing becomes a public listing automatically.</p>
    {!auth.signedIn && <section className="empty-state mt-8"><LockKeyhole size={36}/><h2 className="text-xl font-bold">Sign in to register a business</h2><p>Google or verified email sign-in is required for accountable business ownership.</p><button className="btn-primary mt-4" onClick={auth.login}>Sign in / Create account</button></section>}
    {auth.signedIn && <div className="space-y-6 mt-8">
      {error&&<p role="alert" className="error-banner">{error}</p>}
      {notice&&<p role="status" className="success-banner"><CheckCircle2 size={18}/>{notice}</p>}
      <div className="flex flex-wrap gap-3 items-center justify-between"><h2 className="text-xl font-bold">My organizations</h2><button className="btn-primary" onClick={()=>{setShowCreate(v=>!v);if (!newBusiness.contact_email && auth.person?.email) setNewBusiness(x=>({...x,contact_email:auth.person!.email!}))}}><Plus size={17}/> {showCreate?'Close form':'Register business'}</button></div>
      {showCreate&&<form onSubmit={create} className="form-panel space-y-4">
        <div className="rounded-xl bg-[#eaf5ef] p-4"><h3 className="font-extrabold text-lg">Get started in under a minute</h3><p className="text-sm mt-1">Only three details are needed to save a private draft. You can add registration, address and verification documents when you are ready. No listing goes public automatically.</p></div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="field">What kind of business?<select value={newBusiness.category} onChange={e=>setNewBusiness(v=>({...v,category:e.target.value as VendorCategory}))}>{categories.map(c=><option key={c.value} value={c.value}>{c.label}</option>)}</select></label>
          <label className="field">Business name *<input required minLength={2} maxLength={160} autoComplete="organization" placeholder="e.g. Mountain View Guesthouse" value={newBusiness.business_name} onChange={e=>setNewBusiness(v=>({...v,business_name:e.target.value}))}/></label>
          <label className="field sm:col-span-2">Business email *<input required type="email" maxLength={320} autoComplete="email" placeholder="contact@business.com" value={newBusiness.contact_email} onChange={e=>setNewBusiness(v=>({...v,contact_email:e.target.value}))}/></label>
        </div>
        <button type="submit" disabled={busy} className="btn-primary w-full justify-center">{busy?'Savingâ€¦':'Create my private business draft'}</button>
        <p className="text-xs text-ink/60">No license number, documents, or payment required to start a draft. They are needed later for independent verification.</p>
      </form>}
      {organizations.length===0&&!showCreate&&<section className="empty-state"><Building2 size={32}/><p>No businesses registered yet. Start with your organization's legal details.</p></section>}
      {organizations.length>0&&<div className="grid gap-6 lg:grid-cols-[minmax(220px,.8fr)_minmax(0,1.5fr)] items-start">
        <nav aria-label="Your organizations" className="form-panel space-y-2">
          {organizations.map(o=><button key={o.id} type="button" onClick={()=>{setSelected(o.id);setVendorTab('details');setEditing(false);setError('');setNotice('')}} className={`w-full p-3 text-left rounded-xl border ${selected===o.id?'border-pine bg-[#eaf5ef]':'border-ink/10'}`}>
            <span className="block font-bold">{o.business_name}</span><span className="text-xs text-ink/60 capitalize">{o.category.replace('_',' ')} Â· {o.verification_state.replace('_',' ')}</span>
          </button>)}
        </nav>
        {current&&<section className="form-panel space-y-5"><div className="flex justify-between items-start gap-3 flex-wrap"><div><h2 className="text-xl font-extrabold">{current.business_name}</h2><p className="text-sm text-ink/60">{current.district && current.province?`${current.district}, ${current.province}`:'Location not added yet'}</p></div><span className="rounded-full bg-[#e9f4ed] text-pine px-3 py-1 text-sm font-bold capitalize">{current.verification_state.replace('_',' ')}</span></div>
          <p className="text-sm text-ink/70">Business contact: {current.contact_email} Â· {current.contact_phone||'No phone provided'}</p>
          <div className="rounded-xl border border-[#cddfd9] bg-white p-4" aria-label="Verification progress">
            <h3 className="font-extrabold">Your setup journey</h3>
            <ol className="mt-2 grid gap-2 sm:grid-cols-3 text-sm">
              <li className="rounded-lg bg-[#eff8f3] p-3"><b>1 Â· Business draft âœ“</b><p>You're in. Keep editing privately.</p></li>
              <li className="rounded-lg bg-[#eff8f3] p-3"><b>2 Â· Complete details {current.province&&current.district&&current.operating_address&&(current.registration_no||current.license_no)?'âœ“':''}</b><p>Add address and registration information.</p></li>
              <li className="rounded-lg bg-[#eff8f3] p-3"><b>3 Â· Request verification</b><p>Add evidence, then submit for review.</p></li>
            </ol>
          </div>
          <nav className="flex flex-wrap gap-2" aria-label="Business dashboard sections">
            {([{key:'details',label:'1 Â· Business details'},{key:'verification',label:'2 Â· Verification'},{key:'team',label:'3 Â· Team (optional)'}] as const).map(tab=><button key={tab.key} type="button" aria-pressed={vendorTab===tab.key} className={`rounded-xl px-3 py-2 text-sm font-bold border ${vendorTab===tab.key?'border-pine bg-[#e4f2eb] text-pine':'border-ink/10'}`} onClick={()=>setVendorTab(tab.key)}>{tab.label}</button>)}
          </nav>
          {vendorTab==='details'&&<div className="space-y-4">
          {current.review_feedback&&<div className="border border-amber-200 bg-amber-50 rounded-xl p-4 text-sm"><b>Administrator feedback:</b> {current.review_feedback}</div>}
          {editable&&!(current.province&&current.district&&current.operating_address&&(current.registration_no||current.license_no))&&<p className="text-sm text-amber-800">Next step: complete your location, business registration or license number. You can return to this anytime.</p>}
          {editable&&<button type="button" className="text-sm text-pine underline" onClick={()=>{setApplicationEdit({category:current.category,business_name:current.business_name,registration_no:current.registration_no,contact_email:current.contact_email,contact_phone:current.contact_phone,province:current.province,district:current.district,operating_address:current.operating_address,license_no:current.license_no});setEditing(v=>!v)}}>{editing?'Close editor':'Edit application details'}</button>}
          {editing&&editable&&<form onSubmit={saveChanges} className="grid sm:grid-cols-2 gap-3">
            {(['business_name','contact_email','registration_no','license_no','contact_phone'] as const).map(field=><label key={field} className="field capitalize">{field.replaceAll('_',' ')}<input required={['business_name','contact_email'].includes(field)} value={applicationEdit[field]||''} onChange={e=>setApplicationEdit(v=>({...v,[field]:e.target.value||null}))}/></label>)}
            <label className="field">District *<select required value={applicationEdit.district||''} onChange={e=>setApplicationEdit(v=>({...v,district:e.target.value||null,province:provinceForDistrict(e.target.value)}))}><option value="">Choose a district</option>{applicationEdit.district&&!allDistricts.includes(applicationEdit.district)&&<option value={applicationEdit.district}>{applicationEdit.district} (existing)</option>}{allDistricts.map(name=><option key={name} value={name}>{name}</option>)}</select></label>
            <label className="field">Province (automatic)<input readOnly value={applicationEdit.province||''} placeholder="Choose district first"/></label>
            <label className="field sm:col-span-2">Operating address<textarea required minLength={6} maxLength={800} value={applicationEdit.operating_address||''} onChange={e=>setApplicationEdit(v=>({...v,operating_address:e.target.value}))}/></label>
            <button type="submit" disabled={busy} className="btn-primary sm:col-span-2 justify-center">Save changes</button>
          </form>}
          <button type="button" className="btn-secondary" onClick={()=>setVendorTab('verification')}>Continue to verification â†’</button>
          </div>}
          <div className="info-banner"><ShieldCheck size={19}/> {current.verification_state==='approved'?'Organization verification approved. You can now create service listing drafts and submit them for independent publication review. Subscription activation is separate.':current.verification_state==='submitted'?'Awaiting independent administrator review. Business details are locked during review.':'Verification is not complete. This business is not discoverable until verification and a listing are separately approved.'}</div>
          {vendorTab==='verification'&&<div className="space-y-4">
          <h3 className="font-extrabold">License & registration references</h3>
          <p className="text-sm text-ink/60">Reference details are private and require manual cross-checking. Private attachments are supported below. Reference details still require independent validation.</p>
          {references.map(r=><p key={r.id} className="text-sm border border-ink/10 rounded-lg p-3"><b>{r.evidence_type.replaceAll('_',' ')}</b> Â· {r.issuer} Â· {r.reference_number}{r.expires_on?` Â· Expires ${r.expires_on}`:''}</p>)}
          {editable&&<form onSubmit={addEvidence} className="grid gap-3 sm:grid-cols-2">
            <label className="field">Reference type<select value={newEvidence.evidence_type} onChange={e=>setNewEvidence(v=>({...v,evidence_type:e.target.value as VendorEvidence['evidence_type']}))}><option value="business_registration">Business registration</option><option value="tourism_license">Tourism license</option><option value="professional_license">Professional license</option><option value="other_permit">Other permit</option></select></label>
            <label className="field">Issuing authority *<input required minLength={2} maxLength={160} value={newEvidence.issuer} onChange={e=>setNewEvidence(v=>({...v,issuer:e.target.value}))}/></label>
            <label className="field">Reference number *<input required minLength={3} maxLength={160} value={newEvidence.reference_number} onChange={e=>setNewEvidence(v=>({...v,reference_number:e.target.value}))}/></label>
            <label className="field">Expiration (if applicable)<input type="date" value={newEvidence.expires_on||''} onChange={e=>setNewEvidence(v=>({...v,expires_on:e.target.value||null}))}/></label>
            <label className="field sm:col-span-2">Attach document now (optional, PDF/JPEG/PNG, max 5 MB)<input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={e=>setCombinedDocument(e.target.files?.[0]||null)}/></label>
            {combinedDocument&&combinedDocument.size>5*1024*1024&&<p className="error-banner sm:col-span-2">File is too large (maximum 5 MB).</p>}
            <button disabled={busy||(combinedDocument?.size||0)>5*1024*1024} type="submit" className="btn-secondary sm:col-span-2 justify-center"><Plus size={16}/> Save license {combinedDocument?'and upload document':'reference'}</button>
          </form>}
          {editable&&<div className="border-t border-ink/10 pt-4"><p className="text-sm text-ink/60">Submission needs a complete business address, a registration/license number and at least one unexpired evidence reference.</p><button disabled={busy||!current.province||!current.district||!current.operating_address||!(current.registration_no||current.license_no)||references.length===0} className="btn-primary mt-3" onClick={()=>void run(jwt=>submitVendorOrganization(current.id,jwt),'Submitted for manual verification.')}><ClipboardList size={16}/> Submit for verification</button></div>}
          <section className="border-t border-ink/10 pt-4 space-y-3">
            <h3 className="font-extrabold">Private verification documents</h3>
            <p className="text-sm text-ink/60">Attach a PDF, PNG or JPEG to an existing registration reference (maximum 5 MB). Files stay private. An antivirus scan is required before anyone can download an attachment or use it in approval.</p>
            {documents.map(doc=><div key={doc.id} className="flex flex-wrap gap-3 items-center justify-between border border-ink/10 rounded-xl p-3 text-sm">
              <div><b>{doc.name}</b><p className="text-xs text-ink/60">{Math.ceil(doc.size_bytes/1024)} KB Â· {doc.scan_state.replace('_',' ')}</p></div>
              <div className="flex gap-2">
                {doc.downloadable&&<button className="btn-secondary" type="button" disabled={busy} onClick={()=>void (async()=>{try{const jwt=await auth.token();if(jwt)await downloadVendorDocument(current.id,doc.id,jwt)}catch(e){setError(String(e))}})()}>Download</button>}
                {editable&&<button className="btn-secondary" type="button" disabled={busy} onClick={()=>void run(jwt=>deleteVendorDocument(current.id,doc.id,jwt),'Document deleted.')}>Delete</button>}
              </div>
            </div>)}
            {editable&&references.length>0&&<form className="grid sm:grid-cols-2 gap-3" onSubmit={e=>{e.preventDefault();if(!file||!evidenceId)return;void run(jwt=>uploadVendorDocument(current.id,evidenceId,file,jwt),'Evidence document securely submitted for scanning.');setFile(null)}}>
              <label className="field">Matching evidence reference<select required value={evidenceId} onChange={e=>setEvidenceId(e.target.value)}><option value="">Select a reference</option>{references.map(ref=><option key={ref.id} value={ref.id}>{ref.evidence_type} Â· {ref.reference_number}</option>)}</select></label>
              <label className="field">Evidence file<input required type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={e=>setFile(e.target.files?.[0]||null)}/></label>
              <button className="btn-secondary sm:col-span-2 justify-center" disabled={busy||!file||!evidenceId||file.size>5*1024*1024} type="submit">Upload private document</button>
              {file&&file.size>5*1024*1024&&<p className="text-red-700 text-sm">File exceeds the 5 MB limit.</p>}
            </form>}
            {compliance?.renewal_required&&<div className="border border-amber-200 bg-amber-50 rounded-xl p-3 text-sm"><b>License renewal required.</b> {compliance.expired_evidence_ids.length} expired evidence references detected. {current.verification_state==='expired_license'&&owner&&<button type="button" className="btn-secondary ml-2" disabled={busy} onClick={()=>void run(jwt=>startVendorRenewal(current.id,jwt),'Renewal started. Update references and resubmit.')}>Start renewal</button>}</div>}
            {documents.some(d=>d.scan_state==='pending_scan')&&<p className="text-amber-800 text-sm">Some documents are awaiting antivirus scanning; they cannot be opened yet. Contact the platform administrator if they remain pending.</p>}
          </section>
          </div>}
          {vendorTab==='team'&&<div className="border-t border-ink/10 pt-4"><h3 className="font-extrabold flex items-center gap-2"><Users size={18}/> Team members</h3><div className="mt-3 space-y-1">{members.map(m=><p className="text-xs text-ink/70" key={m.id}>{m.role} Â· {m.state} Â· {m.user_id}</p>)}</div>
            {owner&&<form className="grid gap-3 sm:grid-cols-2 mt-4" onSubmit={invite}><label className="field sm:col-span-2">Team member's verified Tourismo email<input required type="email" value={inviteEmail} onChange={e=>setInviteEmail(e.target.value)} placeholder="colleague@example.com"/><span className="text-xs text-ink/60">This person must have signed into Tourismo once with a verified email. Invitations appear in their account; Tourismo does not send invitation emails yet.</span></label><label className="field">Role<select value={inviteRole} onChange={e=>setInviteRole(e.target.value as 'staff'|'manager')}><option value="staff">Staff (read-only)</option><option value="manager">Manager (edit drafts)</option></select></label><button type="submit" disabled={busy} className="btn-secondary self-end justify-center">Invite team member</button></form>}
          </div>}
        </section>}
      </div>}
      {invitations.length>0&&<section className="form-panel"><h2 className="text-lg font-extrabold">Team invitations</h2>{invitations.map(inv=><div key={inv.id} className="flex items-center justify-between py-3 gap-3"><p className="text-sm">Invitation for organization {inv.organization_id} Â· {inv.role}</p><button disabled={busy} className="btn-secondary" onClick={()=>void run(jwt=>acceptVendorInvitation(inv.id,jwt),'Invitation accepted.')}>Accept</button></div>)}</section>}
      <div className="text-sm text-ink/60 flex gap-2 items-start"><UserRound size={17}/><p>Your Tourismo profile remains a personal tourist account. You can register a business without losing access to your saved trips. <Link to="/account" className="underline text-pine">Manage profile</Link>.</p></div>
      <div className="flex flex-wrap gap-4 items-center"><Link to="/vendor/listings" className="btn-primary"><Building2 size={17}/> Manage service listings</Link><button onClick={()=>void refresh().catch(e=>setError(String(e)))} className="text-sm text-pine underline inline-flex items-center gap-2"><RefreshCw size={15}/> Refresh organizations</button></div>
    </div>}
  </main>
}
