# Single production image: FastAPI backend + built React frontend + static-analysis tools (spec 18.1).

# ---------- 1. Build the frontend ----------
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ ./
RUN npx vite build

# ---------- 2. ESLint runner dependencies ----------
FROM node:20-slim AS eslint-deps
WORKDIR /opt/eslint
COPY backend/app/static_analysis/eslint/package.json ./
RUN npm install --omit=dev --no-audit --no-fund

# ---------- 3. Final image ----------
# Debian 12 (bookworm) still ships OpenJDK 17, which the spec requires for PMD.
FROM python:3.12-slim-bookworm

ARG PMD_VERSION=7.28.0
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    ESLINT_DIR=/opt/eslint \
    PMD_BIN=/opt/pmd/bin/pmd \
    STATIC_DIR=/app/static \
    SEMGREP_SEND_METRICS=off \
    HOME=/home/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        openjdk-17-jre-headless curl unzip ca-certificates \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi8 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20 (for ESLint and `node --check`), copied from the official image.
COPY --from=eslint-deps /usr/local/bin/node /usr/local/bin/node

# PMD 7 from the official GitHub release.
RUN curl -fsSL --retry 5 -o /tmp/pmd.zip \
        "https://github.com/pmd/pmd/releases/download/pmd_releases/${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip" \
    && unzip -q /tmp/pmd.zip -d /opt \
    && mv /opt/pmd-bin-${PMD_VERSION} /opt/pmd \
    && rm /tmp/pmd.zip

WORKDIR /app
COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
RUN pip install ".[tools]"

COPY --from=eslint-deps /opt/eslint /opt/eslint
COPY backend/app/static_analysis/eslint/eslint.config.mjs /opt/eslint/eslint.config.mjs
COPY --from=frontend-build /frontend/dist /app/static

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /opt/eslint/work /app/data \
    && chown -R app:app /opt/eslint/work /app/data /home/app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
