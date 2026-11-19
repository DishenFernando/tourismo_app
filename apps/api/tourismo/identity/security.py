from dataclasses import dataclass
from functools import lru_cache
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.core.models import User

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    session_id: str
    second_factor_minutes: int | None = None


@lru_cache(maxsize=8)
def get_jwks_client(url: str) -> jwt.PyJWKClient:
    # Cache the key set between requests; PyJWT handles key-set cache lifetime.
    return jwt.PyJWKClient(url, cache_jwk_set=True, lifespan=300)


def verify_session_token(token: str) -> VerifiedIdentity:
    settings = get_settings()
    if not settings.auth_ready:
        raise HTTPException(status_code=503, detail='Managed identity is not configured')
    try:
        key = get_jwks_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=['RS256'], issuer=settings.clerk_issuer,
            audience=settings.clerk_audience or None,
            options={'verify_aud': bool(settings.clerk_audience), 'require': ['iss', 'sub', 'exp', 'iat', 'sid']},
            leeway=5,
        )
        if claims.get('azp') not in settings.accepted_origins:
            raise jwt.InvalidTokenError('Unauthorized token origin')
        if not isinstance(claims.get('sub'), str) or not claims['sub']:
            raise jwt.InvalidTokenError('Missing identity subject')
        age = claims.get('fva')
        second_factor = age[1] if isinstance(age, (list, tuple)) and len(age) == 2 and isinstance(age[1], int) and age[1] >= 0 else None
        return VerifiedIdentity(subject=claims['sub'], session_id=claims['sid'], second_factor_minutes=second_factor)
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired session') from exc


def require_identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> VerifiedIdentity:
    if credentials is None:
        raise HTTPException(status_code=401, detail='Authentication required')
    return verify_session_token(credentials.credentials)


def require_user(identity: VerifiedIdentity = Depends(require_identity), db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.auth_subject == identity.subject))
    if user is None:
        # The identity is provider-verified, not user-submitted. This is idempotent under unique subject.
        from sqlalchemy.exc import IntegrityError
        try:
            with db.begin_nested():
                user = User(auth_subject=identity.subject)
                db.add(user)
                db.flush()
            db.commit()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.auth_subject == identity.subject))
            if user is None:
                raise HTTPException(status_code=503, detail='Unable to create profile')
    if user.status != 'active':
        raise HTTPException(status_code=403, detail='Account not active')
    return user


def require_privileged_mfa(identity: VerifiedIdentity = Depends(require_identity)) -> VerifiedIdentity:
    """In production, require a recent Clerk second-factor verification for sensitive vendor review.

    The frontend can direct users to Clerk account security to configure MFA. A normal
    Google or email login does not substitute for a second factor.
    """
    if get_settings().app_environment.lower() == 'production':
        if identity.second_factor_minutes is None or identity.second_factor_minutes > 10:
            raise HTTPException(status_code=403, detail='Recent multi-factor verification required for vendor review')
    return identity
