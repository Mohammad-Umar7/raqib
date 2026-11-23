# Raqib: API + dashboard + the isolated browser, in one hardened container.
# Build:  docker compose -f docker/docker-compose.yml build
# Run:    docker compose -f docker/docker-compose.yml up

# ---- dashboard build
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- runtime: Playwright image ships Chromium and its system libraries
FROM mcr.microsoft.com/playwright/python:v1.65.2-noble AS app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 RAQIB_MODE=live RAQIB_BROWSER_CHANNEL= PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/ backend/
COPY --from=web /web/dist frontend/dist

# Chromium runs as an unprivileged user with its own sandbox; nothing from the host is mounted.
RUN useradd --create-home --uid 10001 raqib && mkdir -p /app/backend/raqib/data/runs /app/backend/raqib/data/evidence && chown -R raqib /app/backend/raqib/data
USER raqib
EXPOSE 8600
CMD ["python", "-m", "uvicorn", "raqib.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8600"]
