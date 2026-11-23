# AggieFlow in one image: the React UI (web/) built and served by the FastAPI API.
#
#   docker build -t aggieflow .
#   docker run --env-file .env -p 8000:8000 aggieflow
#
# Then open http://localhost:8000. Keys come from the environment (--env-file here, the
# host's settings when deployed); .dockerignore keeps .env and data/ out of the image.

# 1. Build the UI. VITE_API_URL=/ makes it call the API on the same address.
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN VITE_API_URL=/ npm run build

# 2. The API, with the exact packages in uv.lock (no dev tools).
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev
COPY agent/ agent/
COPY api/ api/
COPY --from=web /web/dist web/dist

RUN useradd --create-home aggieflow
USER aggieflow
EXPOSE 8000
# Render, Heroku and Cloud Run say which port to listen on in PORT.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
