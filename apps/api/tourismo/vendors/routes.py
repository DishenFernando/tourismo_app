"""Private vendor onboarding: no unreviewed business is exposed through a public API."""
from datetime import date
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tourismo.admin.permissions import require_admin
from tourismo.core.database import get_db
from tourismo.core.models import (
    AuditEvent, ServiceListing, User, VendorDocument, VendorEvidence, VendorMembership,
    VendorOrganization, VendorVerificationCheck, now_utc,
)
from tourismo.identity.security import require_user, require_privileged_mfa

router = APIRouter(prefix='/api/v1/vendor', tags=['vendor-onboarding'])
admin_router = APIRouter(prefix='/api/v1/admin/vendor-verifications', tags=['vendor-verification'])

CATEGORIES = Literal['accommodation', 'restaurant', 'guide', 'transport', 'tour_operator', 'activity']
EVIDENCE_TYPES = Literal['business_registration', 'tourism_license', 'professional_license', 'other_permit']


class VendorCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: CATEGORIES
    business_name: str = Field(min_length=2, max_length=160)
    registration_no: str | None = Field(default=None, max_length=120)
    contact_email: str = Field(min_length=5, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=40)
    province: str | None = Field(default=None, min_length=2, max_length=120)
    district: str | None = Field(default=None, min_length=2, max_length=120)
    operating_address: str | None = Field(default=None, min_length=6, max_length=800)
    license_no: str | None = Field(default=None, max_length=120)

    @field_validator('business_name')
    @classmethod
    def clean_required(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Business name may not be blank')
        return value

    @field_validator('province', 'district', 'operating_address')
    @classmethod
    def clean_later(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Provided location details may not be blank')
        return value

    @field_validator('registration_no', 'license_no')
    @classmethod
    def clean_identifier(cls, value: str | None) -> str | None:
        return ' '.join(value.upper().split()) or None if value is not None else None

    @field_validator('contact_email')
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count('@') != 1 or '.' not in value.rsplit('@', 1)[-1] or any(c.isspace() for c in value):
            raise ValueError('Enter a valid business email address')
        return value

    @field_validator('contact_phone')
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip()
        if any(c not in '+0123456789 -()' for c in value) or len(value) < 7:
            raise ValueError('Enter a contact phone with digits, optional + and separators')
        return value


class VendorEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    business_name: str | None = Field(default=None, min_length=2, max_length=160)
    registration_no: str | None = Field(default=None, max_length=120)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=40)
    province: str | None = Field(default=None, min_length=2, max_length=120)
    district: str | None = Field(default=None, min_length=2, max_length=120)
    operating_address: str | None = Field(default=None, min_length=6, max_length=800)
    license_no: str | None = Field(default=None, max_length=120)

    @model_validator(mode='after')
    def validate_supplied_values(self):
        # Apply the same validation to changed fields as to initial applications.
        for key in self.model_fields_set:
            if key in {'business_name', 'contact_email'} and getattr(self, key) is None:
                raise ValueError(f'{key} cannot be cleared')
        supplied = self.model_dump(exclude_unset=True)
        if supplied:
            defaults = dict(category='guide', business_name='Temporary', registration_no=None,
                contact_email='business@example.com', contact_phone=None, province='Western',
                district='Colombo', operating_address='Test address', license_no=None)
            VendorCreate.model_validate({**defaults, **supplied})
        return self


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    evidence_type: EVIDENCE_TYPES
    issuer: str = Field(min_length=2, max_length=160)
    reference_number: str = Field(min_length=3, max_length=160)
    expires_on: date | None = None

    @field_validator('issuer', 'reference_number')
    @classmethod
    def clean_reference(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Reference must not be blank')
        return value


class MemberInvite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: UUID
    role: Literal['manager', 'staff']


class MemberEmailInvite(BaseModel):
    """Invite a previously authenticated account by its Clerk-verified email."""
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=5, max_length=320)
    role: Literal['manager', 'staff']

    @field_validator('email')
    @classmethod
    def clean_invitee_email(cls, value: str) -> str:
        value = value.strip().lower()
        if (value.count('@') != 1 or '.' not in value.rsplit('@', 1)[-1]
                or any(character.isspace() for character in value)):
            raise ValueError('Enter a valid Tourismo account email')
        return value


class VerificationDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approved', 'rejected', 'changes_requested']
    reason: str = Field(min_length=15, max_length=600)
    source_url: str | None = Field(default=None, max_length=2048)

    @field_validator('reason')
    @classmethod
    def clean_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 15:
            raise ValueError('Give an explanation with at least 15 characters')
        return cleaned

    @model_validator(mode='after')
    def require_source_to_approve(self):
        if self.source_url:
            parsed = urlsplit(self.source_url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Verification source must be a public HTTPS page')
        if self.decision == 'approved' and not self.source_url:
            raise ValueError('Approval requires a reference to the external verification source')
        return self


def organization_dict(org: VendorOrganization, db: Session | None = None) -> dict:
    """Private response. Never include this representation in public listing APIs."""
    published = False
    if db and org.verification_state == 'approved':
        expired = db.scalar(select(VendorEvidence.id).where(
            VendorEvidence.organization_id == org.id, VendorEvidence.expires_on.is_not(None),
            VendorEvidence.expires_on < date.today()).limit(1))
        if not expired:
            published = bool(db.scalar(select(ServiceListing.id).where(
                ServiceListing.organization_id == org.id, ServiceListing.status == 'published').limit(1)))
    return dict(id=str(org.id), owner_id=str(org.owner_id), category=org.category,
        business_name=org.business_name, registration_no=org.registration_no,
        contact_email=org.contact_email, contact_phone=org.contact_phone,
        province=org.province, district=org.district, operating_address=org.operating_address,
        license_no=org.license_no, verification_state=org.verification_state,
        reviewed_at=org.reviewed_at.isoformat() if org.reviewed_at else None,
        review_feedback=org.review_feedback,
        created_at=org.created_at.isoformat() if org.created_at else None,
        # Explicitly avoid implying that approval starts paid access or publishes a listing.
        has_public_listing=published, subscription_trial_started=False)


def evidence_dict(evidence: VendorEvidence) -> dict:
    return dict(id=str(evidence.id), evidence_type=evidence.evidence_type,
        issuer=evidence.issuer, reference_number=evidence.reference_number,
        expires_on=evidence.expires_on.isoformat() if evidence.expires_on else None)


def _event(db: Session, actor: User, action: str, org: VendorOrganization, reason: str | None = None):
    db.add(AuditEvent(actor_id=actor.id, action=action, object_type='vendor_organization',
                      object_id=org.id, reason=reason[:300] if reason else None))


def _organization(db: Session, org_id: UUID, user: User, roles: tuple[str, ...] = ('owner','manager','staff')) -> VendorOrganization:
    result = db.scalar(select(VendorOrganization)
        .join(VendorMembership, VendorMembership.organization_id == VendorOrganization.id)
        .where(VendorOrganization.id == org_id, VendorMembership.user_id == user.id,
               VendorMembership.state == 'active', VendorMembership.role.in_(roles)))
    if result is None:
        raise HTTPException(status_code=404, detail='Organization not found')
    return result


def _editable(org: VendorOrganization):
    if org.verification_state not in ('draft', 'changes_requested', 'rejected'):
        raise HTTPException(status_code=409, detail='Submitted or approved records cannot be changed; request administrative review')


@router.get('/organizations/{org_id}/compliance')
def organization_compliance(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user)
    references = db.scalars(select(VendorEvidence).where(VendorEvidence.organization_id == org.id)).all()
    expired = [str(e.id) for e in references if e.expires_on and e.expires_on < date.today()]
    return dict(verification_state=org.verification_state, expired_evidence_ids=expired,
                verification_current=org.verification_state == 'approved' and not expired,
                renewal_required=org.verification_state == 'expired_license' or bool(expired))


@router.post('/organizations/{org_id}/start-renewal')
def start_renewal(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner',))
    if org.verification_state != 'expired_license':
        raise HTTPException(409, 'Renewal is available after license expiry is recorded')
    org.verification_state = 'changes_requested'
    org.review_feedback = 'Supply current registration or license evidence and resubmit for review.'
    _event(db, user, 'vendor.verification.renewal_started', org)
    db.commit()
    return organization_dict(org)


@router.post('/organizations', status_code=201)
def create_organization(body: VendorCreate, user: User = Depends(require_user), db: Session = Depends(get_db)):
    count = db.scalar(select(func.count()).select_from(VendorOrganization).where(VendorOrganization.owner_id == user.id))
    if count >= 5:
        raise HTTPException(status_code=409, detail='Maximum five business applications per account')
    org = VendorOrganization(owner_id=user.id, **body.model_dump())
    try:
        db.add(org)
        db.flush()
        db.add(VendorMembership(organization_id=org.id, user_id=user.id, role='owner', state='active', accepted_at=now_utc()))
        _event(db, user, 'vendor.organization.create', org)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='Business registration reference already exists') from exc
    return organization_dict(org)


@router.get('/organizations')
def list_organizations(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(VendorOrganization).join(VendorMembership,
        VendorMembership.organization_id == VendorOrganization.id).where(
        VendorMembership.user_id == user.id, VendorMembership.state == 'active')
        .order_by(VendorOrganization.created_at.desc()).limit(100)).all()
    return [organization_dict(org, db) for org in rows]


@router.get('/organizations/{org_id}')
def read_organization(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return organization_dict(_organization(db, org_id, user), db)


@router.patch('/organizations/{org_id}')
def edit_organization(org_id: UUID, body: VendorEdit, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner', 'manager'))
    _editable(org)
    values = body.model_dump(exclude_unset=True)
    validated = VendorCreate.model_validate({**{
        key:getattr(org,key) for key in VendorCreate.model_fields}, **values})
    for key, value in validated.model_dump(exclude={'category'}).items():
        setattr(org, key, value)
    _event(db,user,'vendor.organization.edit',org)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='Business registration reference already exists') from exc
    return organization_dict(org)


@router.get('/organizations/{org_id}/evidence')
def list_evidence(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    _organization(db, org_id, user)
    records = db.scalars(select(VendorEvidence).where(VendorEvidence.organization_id == org_id)
        .order_by(VendorEvidence.created_at)).all()
    return [evidence_dict(e) for e in records]


@router.post('/organizations/{org_id}/evidence', status_code=201)
def add_evidence(org_id: UUID, body: EvidenceCreate, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner','manager'))
    _editable(org)
    count = db.scalar(select(func.count()).select_from(VendorEvidence).where(VendorEvidence.organization_id == org_id))
    if count >= 10:
        raise HTTPException(status_code=409, detail='Maximum ten evidence references per organization')
    evidence = VendorEvidence(organization_id=org_id, **body.model_dump())
    db.add(evidence)
    _event(db,user,'vendor.evidence.reference_added',org)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail='Evidence reference already exists') from exc
    return evidence_dict(evidence)


@router.post('/organizations/{org_id}/submit')
def submit_organization(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner','manager'))
    _editable(org)
    if not (org.province and org.district and org.operating_address):
        raise HTTPException(status_code=422, detail='Complete your province, district and operating address before verification')
    if not (org.registration_no or org.license_no):
        raise HTTPException(status_code=422, detail='Supply a registration or relevant license number')
    evidences = db.scalars(select(VendorEvidence).where(VendorEvidence.organization_id == org.id)).all()
    if not evidences:
        raise HTTPException(status_code=422, detail='Add at least one license or registry reference')
    if any(e.expires_on and e.expires_on < date.today() for e in evidences):
        raise HTTPException(status_code=422, detail='Replace expired evidence references before submitting')
    org.verification_state='submitted'
    org.reviewer_id=None
    org.reviewed_at=None
    org.review_feedback=None
    _event(db,user,'vendor.verification.submitted',org)
    db.commit()
    return organization_dict(org)


@router.get('/organizations/{org_id}/members')
def list_members(org_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    _organization(db, org_id, user)
    records = db.scalars(select(VendorMembership).where(VendorMembership.organization_id == org_id)).all()
    return [dict(id=str(m.id), user_id=str(m.user_id), role=m.role, state=m.state) for m in records]


@router.post('/organizations/{org_id}/members', status_code=201)
def invite_member(org_id: UUID, body: MemberInvite, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner',))
    if user.id == body.user_id:
        raise HTTPException(status_code=422, detail='Owner cannot invite themselves')
    invitee = db.get(User, body.user_id)
    if invitee is None or invitee.status != 'active':
        raise HTTPException(status_code=404, detail='Eligible Tourismo account not found')
    membership = db.scalar(select(VendorMembership).where(VendorMembership.organization_id == org.id,
                                                          VendorMembership.user_id == body.user_id))
    if membership and membership.state != 'revoked':
        raise HTTPException(status_code=409, detail='User is already invited or belongs to this organization')
    if membership is None:
        membership = VendorMembership(organization_id=org.id, user_id=body.user_id)
    membership.role = body.role
    membership.state = 'pending'
    membership.invited_by = user.id
    membership.accepted_at = None
    db.add(membership)
    _event(db,user,'vendor.member.invited',org)
    db.commit()
    return dict(id=str(membership.id), state='pending', role=membership.role)


@router.post('/organizations/{org_id}/members/by-email', status_code=201)
def invite_member_by_email(org_id: UUID, body: MemberEmailInvite,
                           user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Private in-app invite by previously verified Clerk email; no email is sent.

    Does not create an identity, grant a role, or allow use of an unverified
    address typed into a browser. User must accept through their own session.
    """
    _organization(db, org_id, user, ('owner',))
    matches = db.scalars(select(User).where(
        func.lower(User.email) == body.email, User.status == 'active').limit(2)).all()
    if not matches or not all(account.auth_subject.startswith('user_') for account in matches):
        raise HTTPException(404, 'Invitee must first sign in to Tourismo with a verified email')
    if len(matches) != 1:
        raise HTTPException(409, 'Email cannot uniquely identify an account; contact support')
    return invite_member(org_id, MemberInvite(user_id=matches[0].id, role=body.role), user, db)


@router.get('/invitations')
def my_invitations(user: User = Depends(require_user), db: Session = Depends(get_db)):
    invitations = db.scalars(select(VendorMembership).where(
        VendorMembership.user_id == user.id, VendorMembership.state == 'pending')).all()
    return [dict(id=str(m.id), organization_id=str(m.organization_id),
                 role=m.role, state=m.state) for m in invitations]


@router.post('/invitations/{membership_id}/accept')
def accept_invitation(membership_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    membership = db.scalar(select(VendorMembership).where(
        VendorMembership.id == membership_id, VendorMembership.user_id == user.id,
        VendorMembership.state == 'pending').with_for_update())
    if membership is None:
        raise HTTPException(status_code=404, detail='Pending invitation not found')
    membership.state='active'
    membership.accepted_at=now_utc()
    org=db.get(VendorOrganization,membership.organization_id)
    _event(db,user,'vendor.member.invitation_accepted',org)
    db.commit()
    return {'state':'active','organization_id':str(org.id)}


@router.post('/organizations/{org_id}/members/{membership_id}/revoke')
def revoke_member(org_id: UUID, membership_id: UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    org = _organization(db, org_id, user, ('owner',))
    member = db.scalar(select(VendorMembership).where(
        VendorMembership.id == membership_id, VendorMembership.organization_id == org.id))
    if member is None:
        raise HTTPException(status_code=404, detail='Membership not found')
    if member.role == 'owner':
        raise HTTPException(status_code=403, detail='Owner membership cannot be revoked')
    member.state='revoked'
    _event(db,user,'vendor.member.revoked',org)
    db.commit()
    return {'state':'revoked'}


@admin_router.get('')
def verification_queue(state: Literal['submitted', 'approved', 'rejected', 'changes_requested', 'expired_license'] = 'submitted',
                       limit: int = Query(default=50, ge=1, le=100),
                       admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(VendorOrganization).where(VendorOrganization.verification_state == state)
                      .order_by(VendorOrganization.created_at).limit(limit)).all()
    return [organization_dict(o) for o in rows]


@admin_router.get('/{org_id}')
def verification_case(org_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    org=db.get(VendorOrganization,org_id)
    if org is None:
        raise HTTPException(status_code=404, detail='Organization not found')
    evidence=db.scalars(select(VendorEvidence).where(VendorEvidence.organization_id == org.id)).all()
    checks=db.scalars(select(VendorVerificationCheck).where(
        VendorVerificationCheck.organization_id == org.id).order_by(VendorVerificationCheck.checked_at.desc())).all()
    from tourismo.vendors.documents import _documents, document_dict
    return dict(organization=organization_dict(org), evidence=[evidence_dict(e) for e in evidence],
        documents=[document_dict(doc) for doc in _documents(db, org.id)],
        history=[dict(decision=c.decision,reason=c.reason,source_url=c.source_url,
                      checked_at=c.checked_at.isoformat() if c.checked_at else None) for c in checks])


@admin_router.post('/{org_id}/decision')
def verification_decision(org_id: UUID, body: VerificationDecision,
                          admin: User = Depends(require_admin), db: Session = Depends(get_db),
                          _mfa=Depends(require_privileged_mfa)):
    org=db.scalar(select(VendorOrganization).where(VendorOrganization.id == org_id).with_for_update())
    if org is None:
        raise HTTPException(status_code=404, detail='Organization not found')
    if org.verification_state != 'submitted':
        raise HTTPException(status_code=409, detail='Only submitted organizations can be reviewed')
    if org.owner_id == admin.id or db.scalar(select(VendorMembership.id).where(
        VendorMembership.organization_id == org.id, VendorMembership.user_id == admin.id)):
        raise HTTPException(status_code=403, detail='Cannot review an organization you own or belong to')
    if body.decision == 'approved':
        evidence=db.scalars(select(VendorEvidence).where(VendorEvidence.organization_id == org.id)).all()
        if not evidence or any(e.expires_on and e.expires_on < date.today() for e in evidence):
            raise HTTPException(status_code=409, detail='Valid supporting references required for approval')
        documents = db.scalars(select(VendorDocument).where(VendorDocument.organization_id == org.id,
            VendorDocument.deleted_at.is_(None))).all()
        if any(document.scan_state != 'clean' for document in documents):
            raise HTTPException(status_code=409, detail='Uploaded documents must pass malware scanning before approval')
    org.verification_state=body.decision
    org.reviewer_id=admin.id
    org.reviewed_at=now_utc()
    org.review_feedback=body.reason
    db.add(VendorVerificationCheck(organization_id=org.id, reviewer_id=admin.id,
        decision=body.decision, reason=body.reason, source_url=body.source_url))
    _event(db,admin,f'vendor.verification.{body.decision}',org,body.reason)
    db.commit()
    return organization_dict(org)
