"""Explicit local operator task, never exposed over HTTP.
Example: python -m tourismo.admin.cli grant --subject user_... --role admin --confirm
"""
import argparse
from sqlalchemy import select
from sqlalchemy.orm import Session
from tourismo.core.database import get_engine
from tourismo.core.models import User, PlatformRole, UserRoleAssignment, AuditEvent


def main():
    parser = argparse.ArgumentParser(description='Manage Tourismo platform roles from a trusted shell')
    parser.add_argument('action', choices=['grant', 'revoke'])
    parser.add_argument('--subject', required=True, help='Exact Clerk subject ID (user_...)')
    parser.add_argument('--role', choices=['admin', 'editor'], required=True)
    parser.add_argument('--confirm', action='store_true', help='Required to alter privileges')
    args = parser.parse_args()
    if not args.confirm:
        parser.error('Specify --confirm to apply a role change')
    if not args.subject.startswith('user_') or len(args.subject) > 200:
        parser.error('Expected the full Clerk subject starting with user_')
    with Session(get_engine()) as db:
        user = db.scalar(select(User).where(User.auth_subject == args.subject))
        role = db.scalar(select(PlatformRole).where(PlatformRole.key == args.role))
        if user is None or user.status != 'active':
            parser.error('No active Tourismo user with that Clerk subject; sign in first')
        if role is None:
            parser.error('Role missing. Apply Alembic migration 0004 first')
        assignment = db.scalar(select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user.id, UserRoleAssignment.role_id == role.id,
            UserRoleAssignment.scope_type == 'platform', UserRoleAssignment.scope_id.is_(None)))
        changed = False
        if args.action == 'grant' and assignment is None:
            db.add(UserRoleAssignment(user_id=user.id, role_id=role.id, scope_type='platform', scope_id=None))
            changed = True
        elif args.action == 'revoke' and assignment is not None:
            db.delete(assignment)
            changed = True
        if changed:
            db.add(AuditEvent(action=f'platform.role.{args.action}', actor_id=None,
                              object_type='user', object_id=user.id,
                              reason=f'Operator CLI: {args.role}'))
            db.commit()
        print(f'{args.action} {args.role}: {"changed" if changed else "already in requested state"} for {args.subject}')


if __name__ == '__main__':
    main()
