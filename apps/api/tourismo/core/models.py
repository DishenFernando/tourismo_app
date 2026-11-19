from datetime import datetime, date, timezone
import uuid
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint,
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
