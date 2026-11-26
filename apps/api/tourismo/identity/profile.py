"""Authenticated Tourismo profile lifecycle. Clerk remains the identity authority."""
import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.core.models import User, now_utc
from tourismo.identity.security import require_user
from tourismo.admin.permissions import active_roles
from tourismo.notifications.service import queue_notification

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api/v1', tags=['identity'])


class ProfileRead(BaseModel):
    id: str
    display_name: str | None
    email: str | None
    locale: str
    home_region: str | None
    bio: str | None
    profile_completed: bool
    status: str
    roles: list[str]


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    display_name: str = Field(min_length=2, max_length=160)
    locale: Literal['en', 'si', 'ta'] = 'en'
    home_region: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=500)

    @field_validator('display_name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError('Enter a display name with at least two characters')
        return value

    @field_validator('home_region', 'bio')
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        value = value.strip() if value else None
        return value or None


def serialize_profile(user: User, db: Session | None = None) -> ProfileRead:
    return ProfileRead(id=str(user.id), display_name=user.display_name, email=user.email,
                       locale=user.locale, home_region=user.home_region, bio=user.bio,
                       profile_completed=user.profile_completed_at is not None,
                       status=user.status, roles=['tourist'] + (active_roles(db, user) if db is not None and hasattr(db, 'scalars') else []))


def fetch_clerk_identity(subject: str) -> tuple[str | None, str | None] | None:
    """Server-to-server verification: never accept email supplied by the browser.

    Failure does not block login or profile creation; another sign-in can retry.
    The secret key stays exclusively in the backend environment.
    """
    secret = get_settings().clerk_secret_key
    if not secret:
        return None
    try:
        response = httpx.get(f'https://api.clerk.com/v1/users/{subject}',
                             headers={'Authorization': f'Bearer {secret}'}, timeout=4.0)
        response.raise_for_status()
        payload = response.json()
        if payload.get('id') != subject:
            return None
        address_id = payload.get('primary_email_address_id')
        verified_email = next((item['email_address'] for item in payload.get('email_addresses', [])
                               if item.get('id') == address_id
                               and item.get('verification', {}).get('status') == 'verified'), None)
        full_name = ' '.join(part for part in (payload.get('first_name'), payload.get('last_name')) if part).strip()
        return verified_email, (full_name or None)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        logger.warning('Clerk profile data unavailable for verified session subject')
        return None


@router.post('/auth/session/bootstrap', response_model=ProfileRead)
def bootstrap(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Called automatically on verified sign-in; idempotent for Google and email."""
    details = fetch_clerk_identity(user.auth_subject)
    if details is not None:
        email, name = details
        if email is not None:
            user.email = email
        if name and not user.display_name:
            user.display_name = name[:160]
    # In-app welcome is idempotent even if login bootstrap is called repeatedly.
    # No email/SMS is sent; the user sees this after opening notifications.
    queue_notification(db, user.id, 'welcome', 'Welcome to Tourismo',
                       'Your account is ready. Explore places and complete your profile to save trips and write reviews.',
                       '/account', 'welcome:v1')
    db.commit()
    db.refresh(user)
    return serialize_profile(user, db)


@router.get('/me', response_model=ProfileRead)
def get_profile(user: User = Depends(require_user), db: Session = Depends(get_db)):
    return serialize_profile(user, db)


@router.patch('/me', response_model=ProfileRead)
def update_profile(details: ProfileUpdate, user: User = Depends(require_user), db: Session = Depends(get_db)):
    user.display_name = details.display_name
    user.locale = details.locale
    user.home_region = details.home_region
    user.bio = details.bio
    if user.profile_completed_at is None:
        user.profile_completed_at = now_utc()
    db.commit()
    db.refresh(user)
    return serialize_profile(user, db)
