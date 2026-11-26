"""Strict, stable references to public places in itinerary drafts."""
import re
import uuid

PLACE_ID_RE = re.compile(r'^(destination|attraction|service):([0-9a-fA-F-]{36})$')


def parse_place_id(value: str) -> tuple[str, uuid.UUID]:
    if not isinstance(value, str) or not (match := PLACE_ID_RE.fullmatch(value)):
        raise ValueError('Place reference must be destination, attraction, or service plus a UUID')
    try:
        public_id = uuid.UUID(match.group(2))
    except ValueError as exc:
        raise ValueError('Invalid place UUID') from exc
    if str(public_id) != match.group(2):
        raise ValueError('Place UUID must use the canonical hyphenated format')
    return match.group(1), public_id
