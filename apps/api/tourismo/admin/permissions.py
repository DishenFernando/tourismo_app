"""Platform-scoped, database-granted authorization. No browser-supplied roles."""
from datetime import datetime, timezone
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from tourismo.core.database import get_db
from tourismo.core.models import PlatformRole, UserRoleAssignment, User
from tourismo.identity.security import require_user


def active_roles(db: Session, user: User) -> list[str]:
    if user.status != 'active':
        return []
    stmt = (select(PlatformRole.key)
            .join(UserRoleAssignment, UserRoleAssignment.role_id == PlatformRole.id)
            .where(UserRoleAssignment.user_id == user.id,
                   UserRoleAssignment.scope_type == 'platform',
                   UserRoleAssignment.scope_id.is_(None),
                   (UserRoleAssignment.expires_at.is_(None) |
                    (UserRoleAssignment.expires_at > datetime.now(timezone.utc)))))
    return sorted(set(db.scalars(stmt).all()))


def require_editor(user: User = Depends(require_user), db: Session = Depends(get_db)) -> User:
    if not ({'admin', 'editor'} & set(active_roles(db, user))):
        raise HTTPException(status_code=403, detail='Editor permission required')
    return user


def require_admin(user: User = Depends(require_user), db: Session = Depends(get_db)) -> User:
    if 'admin' not in active_roles(db, user):
        raise HTTPException(status_code=403, detail='Administrator permission required')
    return user
