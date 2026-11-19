from datetime import datetime, date, timezone
import uuid
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Index, Integer, Float, String, Text, UniqueConstraint,
)
from tourismo.core.geo import Geography
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from tourismo.core.database import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    auth_subject: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(320))
    home_region: Mapped[str | None] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(String(500))
    profile_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locale: Mapped[str] = mapped_column(String(10), default='en')
    status: Mapped[str] = mapped_column(String(24), default='active', nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class PlatformRole(Base):
    __tablename__ = 'platform_roles'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str] = mapped_column(Text)


class UserRoleAssignment(Base):
    __tablename__ = 'user_role_assignments'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('platform_roles.id', ondelete='RESTRICT'))
    scope_type: Mapped[str] = mapped_column(String(32), default='platform')
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index('ix_user_role_scope', 'user_id', 'role_id', 'scope_type', 'scope_id'),)


class ContentSource(Base):
    __tablename__ = 'content_sources'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(160))
    url: Mapped[str | None] = mapped_column(String(2048))
    license_status: Mapped[str] = mapped_column(String(40), default='not_assessed')
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Destination(Base):
    __tablename__ = 'destinations'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    district: Mapped[str] = mapped_column(String(120), index=True)
    province: Mapped[str] = mapped_column(String(120))
    location: Mapped[object | None] = mapped_column(Geography(), nullable=True)
    content_status: Mapped[str] = mapped_column(String(30), default='draft', nullable=False, index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('content_sources.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    translations: Mapped[list['DestinationTranslation']] = relationship(back_populates='destination', lazy='selectin')
    photos: Mapped[list['DestinationPhoto']] = relationship(back_populates='destination', lazy='selectin')


class DestinationTranslation(Base):
    __tablename__ = 'destination_translations'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    destination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('destinations.id', ondelete='CASCADE'))
    locale: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text, default='')
    __table_args__ = (UniqueConstraint('destination_id', 'locale', name='uq_destination_locale'),)
    destination: Mapped[Destination] = relationship(back_populates='translations')


class Trip(Base):
    __tablename__ = 'trips'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), index=True)
    client_draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    destination_slug: Mapped[str] = mapped_column(ForeignKey('destinations.slug', ondelete='RESTRICT'))
    title: Mapped[str] = mapped_column(String(160))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    adults: Mapped[int] = mapped_column(Integer)
    children_ages: Mapped[list[int]] = mapped_column(JSONB, default=list)
    currency: Mapped[str] = mapped_column(String(3), default='LKR')
    budget_limit_minor: Mapped[int | None] = mapped_column(BigInteger)
    budget_flexible: Mapped[bool] = mapped_column(Boolean, default=False)
    budget_items: Mapped[list] = mapped_column(JSONB, default=list)
    itinerary: Mapped[list] = mapped_column(JSONB, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    __table_args__ = (
        UniqueConstraint('owner_id', 'client_draft_id', name='uq_trip_owner_draft'),
        CheckConstraint('adults >= 1 AND adults <= 30', name='trip_adults_range'),
        CheckConstraint('budget_limit_minor IS NULL OR budget_limit_minor >= 0', name='trip_budget_nonnegative'),
        CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date', name='trip_valid_dates'),
    )


class AuditEvent(Base):
    __tablename__ = 'audit_events'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    action: Mapped[str] = mapped_column(String(120), index=True)
    object_type: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reason: Mapped[str | None] = mapped_column(String(300))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class DestinationGuide(Base):
    """Localized editorial guide; unpublished drafts are not exposed by public APIs."""
    __tablename__ = 'destination_guides'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    destination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('destinations.id', ondelete='CASCADE'), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    highlights: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    local_tips: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    content_status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft', index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('content_sources.id'))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    source: Mapped['ContentSource | None'] = relationship()
    __table_args__ = (UniqueConstraint('destination_id', 'locale', name='uq_destination_guide_locale'),)


class GuideRevision(Base):
    """Reviewable drafts and retained approved snapshots; public text stays unchanged until approval."""
    __tablename__ = 'destination_guide_revisions'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    guide_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('destination_guides.id', ondelete='CASCADE'), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    highlights: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    local_tips: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('content_sources.id'))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='draft', index=True)
    edited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    source: Mapped['ContentSource | None'] = relationship()
    __table_args__ = (UniqueConstraint('guide_id', 'version', name='uq_guide_revision_version'),)


class PointOfInterest(Base):
    __tablename__ = 'poi'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    destination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('destinations.id', ondelete='CASCADE'), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    location: Mapped[object | None] = mapped_column(Geography(), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft', index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('content_sources.id'))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    source: Mapped['ContentSource | None'] = relationship()
    translations: Mapped[list['PoiTranslation']] = relationship(back_populates='poi', lazy='selectin')
    __table_args__ = (UniqueConstraint('destination_id', 'slug', name='uq_poi_destination_slug'),)


class PoiTranslation(Base):
    __tablename__ = 'poi_translations'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    poi_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('poi.id', ondelete='CASCADE'), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default='')
    local_tips: Mapped[str] = mapped_column(Text, nullable=False, default='')
    poi: Mapped[PointOfInterest] = relationship(back_populates='translations')
    __table_args__ = (UniqueConstraint('poi_id', 'locale', name='uq_poi_locale'),)


class DestinationPhoto(Base):
    __tablename__ = 'destination_photos'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    destination_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('destinations.id', ondelete='CASCADE'), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_page_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    photographer: Mapped[str] = mapped_column(String(160), nullable=False)
    license_name: Mapped[str] = mapped_column(String(60), nullable=False)
    license_url: Mapped[str] = mapped_column(String(512), nullable=False)
    alt_text: Mapped[str] = mapped_column(String(240), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    destination: Mapped[Destination] = relationship(back_populates='photos')
    __table_args__ = (UniqueConstraint('destination_id', 'file_page_url', name='uq_destination_photo_file'),)


class VendorOrganization(Base):
    """Private applicant business. No vendor listing exists until later phases."""
    __tablename__ = 'vendor_organizations'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    business_name: Mapped[str] = mapped_column(String(160), nullable=False)
    registration_no: Mapped[str | None] = mapped_column(String(120), unique=True)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    district: Mapped[str] = mapped_column(String(120), nullable=False)
    operating_address: Mapped[str] = mapped_column(Text, nullable=False)
    license_no: Mapped[str | None] = mapped_column(String(120))
    verification_state: Mapped[str] = mapped_column(String(24), nullable=False, default='draft', index=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_feedback: Mapped[str | None] = mapped_column(String(600))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    __table_args__ = (
        CheckConstraint("category IN ('accommodation','restaurant','guide','transport','tour_operator','activity')", name='ck_vendor_category'),
        CheckConstraint("verification_state IN ('draft','submitted','changes_requested','approved','rejected')", name='ck_vendor_state'),
    )


class VendorMembership(Base):
    """Organization-scoped grants; never grants a platform admin/editor role."""
    __tablename__ = 'vendor_memberships'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('vendor_organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (
        UniqueConstraint('organization_id', 'user_id', name='uq_vendor_org_member'),
        CheckConstraint("role IN ('owner','manager','staff')", name='ck_vendor_member_role'),
        CheckConstraint("state IN ('pending','active','revoked')", name='ck_vendor_member_state'),
    )


class VendorEvidence(Base):
    """Private license/registry reference; not a document upload or verified credential."""
    __tablename__ = 'vendor_evidence'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('vendor_organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    issuer: Mapped[str] = mapped_column(String(160), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(160), nullable=False)
    expires_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint('organization_id','evidence_type','reference_number', name='uq_vendor_evidence_ref'),)


class VendorVerificationCheck(Base):
    __tablename__ = 'vendor_verification_checks'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('vendor_organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(600), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
