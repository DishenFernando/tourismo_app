from datetime import datetime, date, timezone
import uuid
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Index, Integer, Float, LargeBinary, String, Text, UniqueConstraint, text,
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
    location_source_url: Mapped[str | None] = mapped_column(String(2048))
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
    location_source_url: Mapped[str | None] = mapped_column(String(2048))
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
    media_kind: Mapped[str] = mapped_column(String(24), nullable=False, default='commons_photo')
    destination: Mapped[Destination] = relationship(back_populates='photos')
    __table_args__ = (UniqueConstraint('destination_id', 'file_page_url', name='uq_destination_photo_file'),)


class DestinationImageBlob(Base):
    """Small local-development images; production should migrate to managed object storage."""
    __tablename__ = 'destination_image_blobs'
    photo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('destination_photos.id', ondelete='CASCADE'), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


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
    province: Mapped[str | None] = mapped_column(String(120), nullable=True)
    district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    operating_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_no: Mapped[str | None] = mapped_column(String(120))
    verification_state: Mapped[str] = mapped_column(String(24), nullable=False, default='draft', index=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_feedback: Mapped[str | None] = mapped_column(String(600))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    __table_args__ = (
        CheckConstraint("category IN ('accommodation','restaurant','guide','transport','tour_operator','activity')", name='ck_vendor_category'),
        CheckConstraint("verification_state IN ('draft','submitted','changes_requested','approved','rejected','expired_license')", name='ck_vendor_state'),
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


class VendorDocument(Base):
    """Private evidence attachment. Only a clean scanner result permits retrieval."""
    __tablename__ = 'vendor_documents'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('vendor_organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('vendor_evidence.id', ondelete='RESTRICT'), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    original_name: Mapped[str] = mapped_column(String(120), nullable=False)
    media_type: Mapped[str] = mapped_column(String(60), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    scan_state: Mapped[str] = mapped_column(String(20), nullable=False, default='pending_scan')
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("scan_state IN ('pending_scan','clean','infected')", name='ck_vendor_document_scan'),
        CheckConstraint('size_bytes > 0 AND size_bytes <= 5242880', name='ck_vendor_document_size'),
    )


class ServiceListing(Base):
    """A business-owned offer; only independently published listings are public."""
    __tablename__ = 'service_listings'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('vendor_organizations.id', ondelete='RESTRICT'), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(String(350), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    province: Mapped[str] = mapped_column(String(120), nullable=False)
    district: Mapped[str] = mapped_column(String(120), nullable=False)
    public_email: Mapped[str | None] = mapped_column(String(320))
    public_phone: Mapped[str | None] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSONB, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_source_url: Mapped[str | None] = mapped_column(String(2048))
    location_note: Mapped[str | None] = mapped_column(String(250))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='draft', index=True)
    review_feedback: Mapped[str | None] = mapped_column(String(600))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    organization: Mapped[VendorOrganization] = relationship(lazy='selectin')
    photos: Mapped[list['ServiceListingPhoto']] = relationship(back_populates='listing', lazy='selectin', order_by='ServiceListingPhoto.created_at', cascade='all, delete-orphan')
    revisions: Mapped[list['ServiceListingRevision']] = relationship(back_populates='listing', lazy='selectin', order_by='ServiceListingRevision.created_at')
    __table_args__ = (
        CheckConstraint("category IN ('accommodation','restaurant','guide','transport','tour_operator','activity')", name='ck_service_listing_category'),
        CheckConstraint("status IN ('draft','submitted','changes_requested','published','archived')", name='ck_service_listing_status'),
    )


class ServiceListingPhoto(Base):
    """Credited HTTPS media only; never an image of a different business."""
    __tablename__ = 'service_listing_photos'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('service_listings.id', ondelete='CASCADE'), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    credit: Mapped[str] = mapped_column(String(160), nullable=False)
    license_name: Mapped[str] = mapped_column(String(100), nullable=False)
    license_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    alt_text: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    listing: Mapped[ServiceListing] = relationship(back_populates='photos')
    __table_args__ = (UniqueConstraint('listing_id', 'source_url', name='uq_service_listing_photo_source'),)


class ServiceListingImageBlob(Base):
    """Sanitized developer-uploaded listing photograph, stored against its photo record."""
    __tablename__ = 'service_listing_image_blobs'
    photo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey('service_listing_photos.id', ondelete='CASCADE'), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ServiceListingReview(Base):
    """Durable independent publication decisions; no implicit business verification."""
    __tablename__ = 'service_listing_reviews'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('service_listings.id', ondelete='CASCADE'), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(600), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (CheckConstraint("decision IN ('published','changes_requested')", name='ck_listing_review_decision'),)


class ServiceListingRevision(Base):
    """Private proposed replacement; never changes public listing before independent approval."""
    __tablename__ = 'service_listing_revisions'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('service_listings.id', ondelete='CASCADE'), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default='draft')
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    review_feedback: Mapped[str | None] = mapped_column(String(600))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    listing: Mapped[ServiceListing] = relationship(back_populates='revisions')
    __table_args__ = (CheckConstraint("status IN ('draft','submitted','changes_requested','approved')", name='ck_service_listing_revision_status'),)


class CustomerReview(Base):
    """User-authored feedback, separate from ServiceListingReview (editorial publication decisions)."""
    __tablename__ = 'customer_reviews'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('service_listings.id', ondelete='CASCADE'), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default='pending', index=True)
    moderation_note: Mapped[str | None] = mapped_column(String(600))
    moderated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    __table_args__ = (
        Index('ix_customer_reviews_listing_author', 'listing_id', 'author_id'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='ck_customer_review_rating'),
        CheckConstraint("state IN ('pending','published','changes_requested','hidden')", name='ck_customer_review_state'),
        Index('ix_customer_review_listing_state', 'listing_id', 'state'),
    )


class CustomerReviewReply(Base):
    """One provider response per customer review; edited replies require renewed moderation."""
    __tablename__ = 'customer_review_replies'
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('customer_reviews.id', ondelete='CASCADE'), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('vendor_organizations.id', ondelete='RESTRICT'), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default='pending', index=True)
    moderation_note: Mapped[str | None] = mapped_column(String(600))
    moderated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    __table_args__ = (
        CheckConstraint("state IN ('pending','published','changes_requested','hidden')", name='ck_customer_review_reply_state'),
    )


class CustomerReviewReport(Base):
    """One privacy/abuse report per account and review; report content is admin-only."""
    __tablename__ = 'customer_review_reports'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('customer_reviews.id', ondelete='CASCADE'), nullable=False, index=True)
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation: Mapped[str] = mapped_column(String(600), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default='open', index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (
        UniqueConstraint('review_id', 'reporter_id', name='uq_customer_review_reporter'),
        CheckConstraint("reason IN ('spam','abuse','privacy','misleading','other')", name='ck_customer_review_report_reason'),
        CheckConstraint("state IN ('open','dismissed','actioned')", name='ck_customer_review_report_state'),
    )


class ServiceEnquiry(Base):
    """Private conversation about one published service; never a reservation."""
    __tablename__ = 'service_enquiries'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    listing_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('service_listings.id', ondelete='RESTRICT'), nullable=False, index=True)
    traveler_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(140), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default='open', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    __table_args__ = (
        CheckConstraint("state IN ('open','answered','closed','withdrawn','blocked')", name='ck_service_enquiry_state'),
        Index('uq_service_enquiry_active', 'listing_id', 'traveler_id', unique=True,
              postgresql_where=text("state IN ('open','answered')")),
        Index('ix_service_enquiry_traveler_created', 'traveler_id', 'created_at'),
    )


class ServiceEnquiryMessage(Base):
    """Append-only message text; author and role are determined by server-side identity."""
    __tablename__ = 'service_enquiry_messages'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    enquiry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('service_enquiries.id', ondelete='RESTRICT'), nullable=False, index=True)
    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    sender_type: Mapped[str] = mapped_column(String(12), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (
        CheckConstraint("sender_type IN ('traveler','vendor')", name='ck_service_enquiry_sender'),
        Index('ix_service_enquiry_messages_page', 'enquiry_id', 'created_at', 'id'),
        Index('ix_service_enquiry_message_sender_time', 'sender_id', 'created_at'),
    )


class ServiceEnquiryReport(Base):
    """Private abuse reports visible only to admins; no public report count."""
    __tablename__ = 'service_enquiry_reports'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    enquiry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('service_enquiries.id', ondelete='RESTRICT'), nullable=False, index=True)
    reporter_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    reason: Mapped[str] = mapped_column(String(24), nullable=False)
    explanation: Mapped[str] = mapped_column(String(600), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default='open', index=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (
        UniqueConstraint('enquiry_id', 'reporter_id', name='uq_service_enquiry_reporter'),
        CheckConstraint("reason IN ('spam','abuse','privacy','misleading','other')", name='ck_service_enquiry_report_reason'),
        CheckConstraint("state IN ('open','dismissed','actioned')", name='ck_service_enquiry_report_state'),
    )


import sqlalchemy as _phase71_sa


class CustomerReviewImage(Base):
    """Bounded, normalized JPEG attachment; never served unless review is published."""
    __tablename__ = 'customer_review_images'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('customer_reviews.id', ondelete='CASCADE'), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    jpeg_data: Mapped[bytes] = mapped_column(_phase71_sa.LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (
        Index('ix_customer_review_images_review', 'review_id'),
        UniqueConstraint('review_id', 'position', name='uq_customer_review_image_position'),
        CheckConstraint('position >= 0 AND position <= 4', name='ck_customer_review_image_position'),
    )


class UserNotification(Base):
    """Private inbox item. Dedupe key is scoped to exactly one recipient."""
    __tablename__ = 'user_notifications'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    kind: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(String(600), nullable=False)
    target_url: Mapped[str] = mapped_column(String(400), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(190), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('recipient_id', 'dedupe_key', name='uq_user_notification_dedupe'),
        CheckConstraint("char_length(title) > 0 AND char_length(body) > 0", name='ck_notification_nonempty'),
        Index('ix_user_notification_inbox', 'recipient_id', 'created_at'),
        Index('ix_user_notification_unread', 'recipient_id', 'read_at'),
    )


class PlatformAnnouncement(Base):
    """One administrator-published release notice, shown without mass fan-out."""
    __tablename__ = 'platform_announcements'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    release_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(String(600), nullable=False)
    target_url: Mapped[str] = mapped_column(String(400), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='RESTRICT'), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index('ix_platform_announcement_published', 'published_at'),
                      CheckConstraint("char_length(title) > 0 AND char_length(body) > 0", name='ck_announcement_nonempty'))


class AnnouncementRead(Base):
    """One per-user receipt, never marks a release read for other users."""
    __tablename__ = 'announcement_reads'
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    announcement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('platform_announcements.id', ondelete='CASCADE'), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class EmailPreference(Base):
    """The user owns email delivery choices; release email is opt-in."""
    __tablename__ = 'email_preferences'
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    activity_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    releases_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc, onupdate=now_utc)


class EmailOutbox(Base):
    """Idempotent, retryable mail job. The user's current verified email is looked up at delivery."""
    __tablename__ = 'email_outbox'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('user_notifications.id', ondelete='CASCADE'))
    announcement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('platform_announcements.id', ondelete='CASCADE'))
    idempotency_key: Mapped[str] = mapped_column(String(190), nullable=False, unique=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default='queued', index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(80))
    provider_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("state IN ('queued','sending','sent','failed','suppressed')", name='ck_email_outbox_state'),
        CheckConstraint("(notification_id IS NOT NULL) <> (announcement_id IS NOT NULL)", name='ck_email_outbox_one_source'),
        Index('ix_email_outbox_ready', 'state', 'next_attempt_at'),
    )


class EmailBroadcastJob(Base):
    """Batch cursors prevent huge release fan-outs in an admin HTTP request."""
    __tablename__ = 'email_broadcast_jobs'
    announcement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('platform_announcements.id', ondelete='CASCADE'), primary_key=True)
    last_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    finished: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=now_utc)
