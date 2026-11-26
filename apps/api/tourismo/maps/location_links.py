"""Extract user-shared location coordinates without scraping map-provider place data."""
from dataclasses import dataclass
import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class LocationLinkInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=8, max_length=2048)


class ResolvedLocation(BaseModel):
    latitude: float
    longitude: float
    source_url: str
    provider: str
    precision: str
    message: str


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float
    precision: str


_GOOGLE = {'www.google.com', 'google.com', 'maps.google.com', 'www.google.lk',
           'google.lk', 'maps.google.lk', 'maps.app.goo.gl', 'goo.gl'}
_OSM = {'www.openstreetmap.org', 'openstreetmap.org'}
_APPLE = {'maps.apple.com'}
_BING = {'www.bing.com', 'bing.com'}
_ALLOWED = _GOOGLE | _OSM | _APPLE | _BING
_SHORT = {'maps.app.goo.gl', 'goo.gl'}
_PAIR = re.compile(r'^\s*(?:loc:)?(-?\d{1,3}(?:\.\d+)?)\s*[,~]\s*(-?\d{1,3}(?:\.\d+)?)\s*$')
_GOOGLE_POINT = re.compile(r'!3d(-?\d{1,3}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)')
_GOOGLE_POINT_ALT = re.compile(r'!2d(-?\d{1,3}(?:\.\d+)?)!3d(-?\d{1,3}(?:\.\d+)?)')
_GOOGLE_CENTER = re.compile(r'@(-?\d{1,3}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)(?:[,/]|$)')
_OSM_CENTER = re.compile(r'(?:^|[&#])map=\d{1,2}/(-?\d{1,3}(?:\.\d+)?)/(-?\d{1,3}(?:\.\d+)?)')


def checked_url(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if len(value) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise HTTPException(422, 'Paste a normal HTTPS map link (up to 2048 characters).')
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or '').lower().rstrip('.')
        if (parsed.scheme.lower() != 'https' or host not in _ALLOWED or
                parsed.username is not None or parsed.password is not None or
                parsed.port not in (None, 443)):
            raise HTTPException(422, 'Only supported HTTPS Google Maps, OpenStreetMap, Apple Maps or Bing Maps links are accepted.')
    except ValueError as exc:
        raise HTTPException(422, 'Invalid map link.') from exc
    if host == 'goo.gl' and not parsed.path.startswith('/maps/'):
        raise HTTPException(422, 'Only legacy goo.gl/maps links are supported.')
    if host in _GOOGLE and host not in _SHORT and not (parsed.path.startswith('/maps') or parsed.path == '/'):
        raise HTTPException(422, 'Link must point to a Google Maps location.')
    return value, host


def _checked(lat: float, lon: float, precision: str) -> Coordinates | None:
    return Coordinates(lat, lon, precision) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


def _pair(text: str | None, precision: str = 'pin') -> Coordinates | None:
    match = _PAIR.fullmatch(text or '')
    return _checked(float(match[1]), float(match[2]), precision) if match else None


def extract_coordinates(link: str) -> Coordinates | None:
    parsed = urlsplit(link)
    host = (parsed.hostname or '').lower().rstrip('.')
    query = parse_qs(parsed.query, keep_blank_values=False)
    path = unquote(parsed.path)
    full = unquote(link)
    if host in _OSM:
        if 'mlat' in query and 'mlon' in query:
            try:
                result = _checked(float(query['mlat'][0]), float(query['mlon'][0]), 'pin')
                if result:
                    return result
            except ValueError:
                pass
        center = _OSM_CENTER.search(parsed.fragment)
        return _checked(float(center[1]), float(center[2]), 'map_center') if center else None
    if host in _GOOGLE:
        for regex, swapped in ((_GOOGLE_POINT, False), (_GOOGLE_POINT_ALT, True)):
            match = regex.search(full)
            if match:
                result = (_checked(float(match[2]), float(match[1]), 'map_center') if swapped
                          else _checked(float(match[1]), float(match[2]), 'pin'))
                if result:
                    return result
        for key in ('q', 'query', 'destination', 'daddr'):
            if key in query:
                result = _pair(query[key][0])
                if result:
                    return result
        for marker in ('/maps/search/', '/maps/place/'):
            if marker in path:
                result = _pair(path.split(marker, 1)[1].split('/', 1)[0])
                if result:
                    return result
        center = _GOOGLE_CENTER.search(full)
        if center:
            return _checked(float(center[1]), float(center[2]), 'map_center')
        for key in ('ll', 'center'):
            if key in query:
                result = _pair(query[key][0], 'map_center')
                if result:
                    return result
    if host in _APPLE:
        for key in ('coordinate', 'll'):
            if key in query:
                result = _pair(query[key][0], 'map_center')
                if result:
                    return result
    if host in _BING and 'cp' in query:
        return _pair(query['cp'][0], 'map_center')
    return None


def follow_short_link(link: str, max_hops: int = 4) -> str:
    """Only accept HTTPS allowlisted redirect destinations, never read HTML bodies."""
    current = link
    with httpx.Client(follow_redirects=False, timeout=httpx.Timeout(4.0),
                      trust_env=False) as client:
        for _ in range(max_hops):
            _, host = checked_url(current)
            if host not in _SHORT:
                return current
            try:
                response = client.head(current)
                if response.status_code in (403, 405, 406, 501):
                    with client.stream('GET', current) as stream:
                        status, location = stream.status_code, stream.headers.get('location')
                else:
                    status, location = response.status_code, response.headers.get('location')
            except httpx.HTTPError as exc:
                raise HTTPException(502, 'Short map link unavailable. Try sharing the full URL from your map app.') from exc
            if status not in (301, 302, 303, 307, 308) or not location:
                raise HTTPException(422, 'Short map link did not provide a location redirect. Try sharing a full map URL.')
            # Validate the absolute destination after resolving a relative redirect.
            # All subsequent hosts remain restricted to our exact allowlist.
            current, _ = checked_url(urljoin(current, location))
    raise HTTPException(422, 'Too many map redirects. Try sharing the final map URL.')


def resolve_location_link(raw: str) -> ResolvedLocation:
    original, host = checked_url(raw)
    final = follow_short_link(original) if host in _SHORT else original
    final, final_host = checked_url(final)
    found = extract_coordinates(final)
    if found is None:
        raise HTTPException(422, 'The link does not expose coordinates. Share a pinned location with coordinates, or use the manual picker. Place-name-only links need a licensed geocoding provider.')
    if not (5.5 <= found.latitude <= 10.2 and 79.35 <= found.longitude <= 82.3):
        raise HTTPException(422, 'These coordinates appear outside Sri Lanka. Double-check the map link.')
    provider = ('Google Maps' if final_host in _GOOGLE else
                'OpenStreetMap' if final_host in _OSM else
                'Apple Maps' if final_host in _APPLE else 'Bing Maps')
    message = ('Shared pin found. Confirm its exact entrance or meeting point before saving.'
               if found.precision == 'pin' else
               'Only the map VIEW centre is available, not an exact place pin. Double-check before saving.')
    return ResolvedLocation(latitude=found.latitude, longitude=found.longitude,
                            source_url=original, provider=provider,
                            precision=found.precision, message=message)
