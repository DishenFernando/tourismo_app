from datetime import date, timedelta
import uuid
from typing import Literal
from pydantic import BaseModel, Field, model_validator

BudgetCategory = Literal['accommodation', 'transport', 'food', 'entry_fees', 'guides', 'activities', 'misc', 'contingency']


class BudgetItem(BaseModel):
    category: BudgetCategory
    description: str = Field(default='', max_length=160)
    minimum_minor: int = Field(ge=0, le=100_000_000_00)
    expected_minor: int = Field(ge=0, le=100_000_000_00)
    maximum_minor: int = Field(ge=0, le=100_000_000_00)
    is_confirmed: bool = False
    source_label: str = Field(default='User-entered estimate', max_length=160)

    @model_validator(mode='after')
    def ordered_amounts(self):
        if not self.minimum_minor <= self.expected_minor <= self.maximum_minor:
            raise ValueError('Budget must satisfy minimum <= expected <= maximum')
        return self


class Stop(BaseModel):
    day: int = Field(ge=1, le=31)
    title: str = Field(min_length=1, max_length=160)
    note: str = Field(default='', max_length=600)


class TripDraft(BaseModel):
    client_draft_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    destination_slug: str = Field(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=120)
    title: str = Field(min_length=1, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    adults: int = Field(ge=1, le=30)
    children_ages: list[int] = Field(default_factory=list, max_length=20)
    currency: Literal['LKR'] = 'LKR'
    budget_limit_minor: int | None = Field(default=None, ge=0, le=100_000_000_00)
    budget_flexible: bool = False
    budget_items: list[BudgetItem] = Field(default_factory=list, max_length=80)
    itinerary: list[Stop] = Field(default_factory=list, max_length=90)

    @model_validator(mode='after')
    def validate_trip(self):
        if any(age < 0 or age > 17 for age in self.children_ages):
            raise ValueError('Child ages must be between 0 and 17')
        if self.adults + len(self.children_ages) > 40:
            raise ValueError('Traveler group exceeds the supported limit')
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError('Specify both travel dates or neither')
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError('End date must not precede start date')
            if self.end_date - self.start_date > timedelta(days=30):
                raise ValueError('Trips longer than 31 days are not supported in this release')
        return self


class TripPreview(BaseModel):
    minimum_minor: int
    expected_minor: int
    maximum_minor: int
    remaining_minor: int | None
    exceeds_limit: bool
    currency: Literal['LKR'] = 'LKR'
    estimated_not_quoted: bool = True


def calculate_preview(draft: TripDraft) -> TripPreview:
    low = sum(item.minimum_minor for item in draft.budget_items)
    expected = sum(item.expected_minor for item in draft.budget_items)
    high = sum(item.maximum_minor for item in draft.budget_items)
    limit = draft.budget_limit_minor
    return TripPreview(minimum_minor=low, expected_minor=expected,
                       maximum_minor=high, remaining_minor=limit - expected if limit is not None else None,
                       exceeds_limit=limit is not None and high > limit)
