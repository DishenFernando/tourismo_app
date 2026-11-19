# Single deployable container: Vite assets + FastAPI, as specified in the blueprint.
FROM node:22-alpine AS frontend
WORKDIR /build/web
COPY apps/web/package*.json ./
RUN npm install --no-audit --no-fund
COPY apps/web/ ./
ARG VITE_CLERK_PUBLISHABLE_KEY=""
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/apps/api WEB_DIST_PATH=/app/web-dist
WORKDIR /app/apps/api
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && groupadd -r app && useradd -r -g app app
COPY apps/api/ ./
RUN mkdir -p /app/private_vendor_documents && chown app:app /app/private_vendor_documents && chmod 700 /app/private_vendor_documents
COPY --from=frontend /build/web/dist /app/web-dist
USER app
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn tourismo.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
