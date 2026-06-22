# ==== Base image ====
FROM ghcr.io/astral-sh/uv:python3.13-bookworm
# ====

# ==== Application working directory ====
WORKDIR /app
# ====

# ==== Runtime and uv configuration ====
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# ====

# ==== System dependencies and application user ====
USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system apiuser \
    && useradd --system --gid apiuser --home-dir /app apiuser \
    && chown apiuser:apiuser /app
# ====

# ==== Python dependency installation ====
USER apiuser

COPY --chown=apiuser:apiuser pyproject.toml ./
COPY --chown=apiuser:apiuser uv.lock ./
COPY --chown=apiuser:apiuser README.md ./
RUN uv sync --frozen --no-dev --no-install-project
# ====

# ==== Application source ====
COPY --chown=apiuser:apiuser src/api ./src/api
COPY --chown=apiuser:apiuser src/core ./src/core
COPY --chown=apiuser:apiuser src/persistence ./src/persistence
RUN uv sync --frozen --no-dev
# ====

# ==== Network configuration ====
EXPOSE 8000
# ====

# ==== Application startup ====
CMD ["uv", "run", "--no-sync", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
# ====
