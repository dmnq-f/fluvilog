# syntax=docker/dockerfile:1

ARG BASE_IMAGE=python:3.13-slim-trixie

# Dedicated alias for the pinned uv release image, binary copied into the builder below.
FROM ghcr.io/astral-sh/uv:0.11.25 AS uv

# ---- builder: resolve the locked deps into a self-contained /app/.venv ----
FROM ${BASE_IMAGE} AS builder

COPY --from=uv /uv /bin/uv

# only-system + no-downloads pins the venv to the base image's interpreter, so
# the venv copied into the runtime stage points at a path that still exists.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Third-party deps first (cached until the lockfile changes), the project after.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev --extra api

COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra api

# ---- runtime: clean base, venv only, non-root ----
FROM ${BASE_IMAGE} AS runtime

# /data is chowned before any volume mount, a fresh volume inherits this ownership
RUN useradd --system --create-home --uid 10001 fluvilog \
    && mkdir -p /data \
    && chown fluvilog:fluvilog /data

COPY --from=builder --chown=fluvilog:fluvilog /app /app

# FLUVILOG_DB points the default database at the /data volume; an explicit
# --db flag still overrides it.
ENV PATH="/app/.venv/bin:$PATH" \
    FLUVILOG_DB=/data/fluvilog.db
WORKDIR /app
USER fluvilog
VOLUME ["/data"]

ENTRYPOINT ["fluvilog"]
CMD ["collect"]
