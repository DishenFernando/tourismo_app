import time
from collections import deque
from threading import Lock
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends
from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.geography.routes import router as destination_router
from tourismo.trips.routes import router as trips_router
from tourismo.identity.profile import router as identity_router

settings = get_settings()
_guest_rate_buckets: dict[str, deque[float]] = {}
_guest_rate_lock = Lock()


def over_guest_limit(request: Request) -> bool:
    """Basic per-process guard for expensive anonymous endpoints.

    Production must also use a shared edge/Redis-level limiter across replicas.
    """
    if request.url.path not in ('/api/v1/trips/preview', '/api/v1/destinations'):
        return False
    remote = request.client.host if request.client else 'unknown'
    key = f'{remote}:{request.url.path}'
    current = time.monotonic()
    with _guest_rate_lock:
        if len(_guest_rate_buckets) > 5000:
            for old_key, history in list(_guest_rate_buckets.items()):
                if not history or current - history[-1] > 60:
                    del _guest_rate_buckets[old_key]
        bucket = _guest_rate_buckets.setdefault(key, deque())
        while bucket and current - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_requests:
            return True
        bucket.append(current)
    return False

app = FastAPI(title='Tourismo API', version='0.1.0',
              docs_url='/api/docs' if settings.app_environment != 'production' else None,
              redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(',')],
                   allow_credentials=False, allow_methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
                   allow_headers=['Authorization', 'Content-Type', 'X-Request-ID'])


@app.middleware('http')
async def request_controls(request: Request, call_next):
    started = time.monotonic()
    request_id = str(uuid.uuid4())
    if over_guest_limit(request):
        response = JSONResponse(status_code=429, content={'error': {
            'code': 'RATE_LIMITED', 'message': 'Too many requests. Try again shortly.', 'request_id': request_id}})
        response.headers['Retry-After'] = '60'
        return response
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(self)'
    response.headers['Server-Timing'] = f'app;dur={(time.monotonic() - started) * 1000:.0f}'
    return response


@app.get('/api/v1/health/live', tags=['health'])
def live():
    return {'status': 'ok'}


@app.get('/api/v1/health/ready', tags=['health'])
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        return JSONResponse(status_code=503, content={'status': 'unavailable'})
    return {'status': 'ok'}


@app.get('/api/v1/auth/config', tags=['auth'])
def auth_config():
    return {'google_enabled': settings.auth_ready, 'email_otp_enabled': settings.auth_ready,
            'phone_otp_enabled': False, 'managed_provider_configured': settings.auth_ready}


app.include_router(identity_router)
app.include_router(destination_router)
app.include_router(trips_router)

# Statically compiled React is served by this API container on Render.
web_dist = Path(settings.web_dist_path)
if web_dist.is_dir() and (web_dist / 'index.html').is_file():
    app.mount('/assets', StaticFiles(directory=web_dist / 'assets'), name='assets')
    app.mount('/brand', StaticFiles(directory=web_dist / 'brand'), name='brand')

    @app.get('/{full_path:path}', include_in_schema=False)
    def spa(full_path: str):
        path = (web_dist / full_path).resolve()
        if path.is_relative_to(web_dist.resolve()) and path.is_file():
            return FileResponse(path)
        return FileResponse(web_dist / 'index.html')
