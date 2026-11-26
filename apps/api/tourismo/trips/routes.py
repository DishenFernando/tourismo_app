import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from tourismo.core.database import get_db
from tourismo.core.models import Destination, Trip, User, new_uuid, now_utc
from tourismo.identity.security import require_user
from tourismo.trips.schemas import TripDraft, TripPreview, calculate_preview

router = APIRouter(prefix='/api/v1/trips', tags=['trips'])


class SavedTrip(BaseModel):
    id: uuid.UUID
    version: int
    draft: TripDraft
    preview: TripPreview


def to_saved(row: Trip) -> SavedTrip:
    draft = TripDraft(client_draft_id=row.client_draft_id, destination_slug=row.destination_slug, title=row.title, start_date=row.start_date,
                      end_date=row.end_date, adults=row.adults, children_ages=row.children_ages,
                      budget_limit_minor=row.budget_limit_minor, budget_flexible=row.budget_flexible,
                      budget_items=row.budget_items, itinerary=row.itinerary)
    return SavedTrip(id=row.id, version=getattr(row, "version", 1), draft=draft, preview=calculate_preview(draft))


@router.post('/preview', response_model=TripPreview)
def preview_trip(draft: TripDraft):
    # Stateless endpoint: no session, user row or DB write for guests.
    return calculate_preview(draft)


@router.post('', response_model=SavedTrip, status_code=201)
def create_trip(draft: TripDraft, user: User = Depends(require_user), db: Session = Depends(get_db)):
    published = db.scalar(select(Destination.id).where(Destination.slug == draft.destination_slug,
                                                       Destination.content_status.in_(['sample', 'published'])))
    if published is None:
        raise HTTPException(status_code=422, detail='Choose a known destination')
    data = draft.model_dump(mode='json')
    statement = pg_insert(Trip).values(
        id=new_uuid(), client_draft_id=draft.client_draft_id,
        owner_id=user.id, destination_slug=data['destination_slug'], title=data['title'],
        start_date=draft.start_date, end_date=draft.end_date, adults=draft.adults,
        children_ages=draft.children_ages, budget_limit_minor=draft.budget_limit_minor,
        budget_flexible=draft.budget_flexible,
        budget_items=data['budget_items'], itinerary=data['itinerary'],
    ).on_conflict_do_nothing(constraint='uq_trip_owner_draft').returning(Trip.id)
    created_id = db.scalar(statement)
    db.commit()
    if created_id is not None:
        row = db.get(Trip, created_id)
    else:
        row = db.scalar(select(Trip).where(Trip.owner_id == user.id, Trip.client_draft_id == draft.client_draft_id))
    if row is None:
        raise HTTPException(status_code=503, detail='Unable to resolve saved trip')
    return to_saved(row)


@router.get('', response_model=list[SavedTrip])
def my_trips(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Trip).where(Trip.owner_id == user.id).order_by(Trip.created_at.desc()).limit(100)).all()
    return [to_saved(row) for row in rows]


@router.get('/{trip_id}', response_model=SavedTrip)
def my_trip(trip_id: uuid.UUID, user: User = Depends(require_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.owner_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail='Trip not found')
    return to_saved(row)


class TripUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    draft: TripDraft


@router.patch('/{trip_id}', response_model=SavedTrip)
def update_trip(trip_id: uuid.UUID, payload: TripUpdate,
                user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Atomic owner-scoped compare-and-swap; stale edits never overwrite new data."""
    existing = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.owner_id == user.id))
    if existing is None:
        raise HTTPException(status_code=404, detail='Trip not found')
    if existing.version != payload.expected_version:
        raise HTTPException(status_code=409, detail='Trip changed elsewhere. Your local draft is preserved.')
    if payload.draft.destination_slug != existing.destination_slug:
        allowed = db.scalar(select(Destination.id).where(
            Destination.slug == payload.draft.destination_slug,
            Destination.content_status.in_(['sample', 'published'])))
        if allowed is None:
            raise HTTPException(status_code=422, detail='Choose a known destination')
    values = payload.draft.model_dump(mode='json')
    # Do not rewrite the immutable client_draft_id: this is an existing saved trip.
    statement = (update(Trip)
                 .where(Trip.id == trip_id, Trip.owner_id == user.id,
                        Trip.version == payload.expected_version)
                 .values(destination_slug=values['destination_slug'], title=values['title'],
                         start_date=payload.draft.start_date, end_date=payload.draft.end_date,
                         adults=values['adults'], children_ages=values['children_ages'],
                         budget_limit_minor=values['budget_limit_minor'],
                         budget_flexible=values['budget_flexible'],
                         budget_items=values['budget_items'], itinerary=values['itinerary'],
                         version=Trip.version + 1, updated_at=now_utc())
                 .returning(Trip.id))
    changed_id = db.scalar(statement)
    if changed_id is None:
        # A concurrent writer won the race between read and update.
        db.rollback()
        raise HTTPException(status_code=409, detail='Trip changed elsewhere. Your local draft is preserved.')
    db.commit()
    # Session(expire_on_commit=False) can retain stale ORM values after SQL UPDATE.
    # Explicitly refresh the owner-scoped row so the response has the new version.
    db.refresh(existing)
    return to_saved(existing)


@router.delete('/{trip_id}', status_code=204)
def delete_trip(trip_id: uuid.UUID, user: User = Depends(require_user),
                db: Session = Depends(get_db)):
    """Permanent deletion is owner-scoped; clients must explicitly confirm it."""
    deleted = db.scalar(delete(Trip).where(Trip.id == trip_id,
                                          Trip.owner_id == user.id).returning(Trip.id))
    if deleted is None:
        db.rollback()
        raise HTTPException(status_code=404, detail='Trip not found')
    db.commit()
