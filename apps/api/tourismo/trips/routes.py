import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from pydantic import BaseModel
from tourismo.core.database import get_db
from tourismo.core.models import Destination, Trip, User, new_uuid
from tourismo.identity.security import require_user
from tourismo.trips.schemas import TripDraft, TripPreview, calculate_preview

router = APIRouter(prefix='/api/v1/trips', tags=['trips'])


class SavedTrip(BaseModel):
    id: uuid.UUID
    draft: TripDraft
    preview: TripPreview


def to_saved(row: Trip) -> SavedTrip:
    draft = TripDraft(client_draft_id=row.client_draft_id, destination_slug=row.destination_slug, title=row.title, start_date=row.start_date,
                      end_date=row.end_date, adults=row.adults, children_ages=row.children_ages,
                      budget_limit_minor=row.budget_limit_minor, budget_flexible=row.budget_flexible,
                      budget_items=row.budget_items, itinerary=row.itinerary)
    return SavedTrip(id=row.id, draft=draft, preview=calculate_preview(draft))


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
