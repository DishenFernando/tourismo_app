from datetime import date, timedelta
import uuid
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from tourismo.maps.place_ids import parse_place_id

BudgetCategory = Literal['accommodation', 'transport', 'food', 'entry_fees', 'guides', 'activities', 'misc', 'contingency']


class BudgetItem(BaseModel):
    category: BudgetCategory
    description: str = Field(default='', max_length=160)
    minimum_minor: int = Field(ge=0, le=100_000_000_00)
    expected_minor: int = Field(ge=0, le=100_000_000_00)
    maximum_minor: int = Field(ge=0, le=100_000_000_00)
    is_confirmed: bool = False
    source_label: str = Field(default='User-entered estimate', max_length=160)
    day: int | None = Field(default=None, ge=1, le=31)

    @model_validator(mode='after')
    def ordered_amounts(self):
        if not self.minimum_minor <= self.expected_minor <= self.maximum_minor:
            raise ValueError('Budget must satisfy minimum <= expected <= maximum')
        return self


class Stop(BaseModel):
    day: int = Field(ge=1, le=31)
    title: str = Field(min_length=1, max_length=160)
    note: str = Field(default='', max_length=600)
    place_id: str | None = Field(default=None, max_length=50)

    @field_validator('place_id')
    @classmethod
    def public_place_reference(cls, value: str | None) -> str | None:
        if value is not None:
            parse_place_id(value)
        return value


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


class BudgetSubtotal(BaseModel):
    minimum_minor: int
    expected_minor: int
    maximum_minor: int


class CategorySubtotal(BudgetSubtotal):
    category: BudgetCategory


class DaySubtotal(BudgetSubtotal):
    day: int


class TripPreview(BaseModel):
    minimum_minor: int
    expected_minor: int
    maximum_minor: int
    remaining_minor: int | None
    exceeds_limit: bool
    currency: Literal['LKR'] = 'LKR'
    estimated_not_quoted: bool = True
    per_traveler_expected_minor: int = 0
    by_category: list[CategorySubtotal] = Field(default_factory=list)
    by_day: list[DaySubtotal] = Field(default_factory=list)
    unassigned: BudgetSubtotal = Field(default_factory=lambda: BudgetSubtotal(minimum_minor=0, expected_minor=0, maximum_minor=0))


def calculate_preview(draft: TripDraft) -> TripPreview:
    """All money stays in integer LKR cents; no provider quotes are inferred."""
    low = expected = high = 0
    categories: dict[str, list[int]] = {}
    days: dict[int, list[int]] = {}
    unassigned = [0, 0, 0]
    for item in draft.budget_items:
        amounts = (item.minimum_minor, item.expected_minor, item.maximum_minor)
        low += amounts[0]
        expected += amounts[1]
        high += amounts[2]
        category = categories.setdefault(item.category, [0, 0, 0])
        target = unassigned if item.day is None else days.setdefault(item.day, [0, 0, 0])
        for index, amount in enumerate(amounts):
            category[index] += amount
            target[index] += amount
    limit = draft.budget_limit_minor
    total_travelers = draft.adults + len(draft.children_ages)
    return TripPreview(
        minimum_minor=low, expected_minor=expected, maximum_minor=high,
        remaining_minor=limit - expected if limit is not None else None,
        exceeds_limit=limit is not None and high > limit,
        per_traveler_expected_minor=(expected + total_travelers // 2) // total_travelers,
        by_category=[CategorySubtotal(category=category, minimum_minor=values[0],
                                      expected_minor=values[1], maximum_minor=values[2])
                     for category, values in categories.items()],
        by_day=[DaySubtotal(day=day, minimum_minor=values[0],
                            expected_minor=values[1], maximum_minor=values[2])
                for day, values in sorted(days.items())],
        unassigned=BudgetSubtotal(minimum_minor=unassigned[0], expected_minor=unassigned[1],
                                  maximum_minor=unassigned[2]),
    )
