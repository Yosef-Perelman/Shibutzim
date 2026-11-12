# One image: FastAPI serves the API and the built client (plan 005, architecture §10).
# Build from the repository root: docker build -t shibutzim .

# --- Stage 1: build the client ---
FROM node:24-slim AS client
WORKDIR /client
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ ./
# Comma-separated emails of the demo accounts the login screen offers; empty hides the switch.
ARG VITE_DEMO_USERS=""
ENV VITE_DEMO_USERS=${VITE_DEMO_USERS}
RUN npm run build

# --- Stage 2: the server, with the client next to it ---
FROM python:3.12-slim AS server
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/server/.venv/bin:$PATH" \
    STATIC_DIR=/app/static \
    PORT=8080

WORKDIR /app/server
COPY server/pyproject.toml server/uv.lock server/.python-version ./
RUN uv sync --frozen --no-dev

COPY server/ ./
COPY docker/start.sh /app/start.sh
COPY --from=client /client/dist /app/static

RUN useradd --system --no-create-home shibutzim && chown -R shibutzim /app
USER shibutzim

EXPOSE 8080
CMD ["/app/start.sh"]
