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

# Agentic workspace sandbox: run_command executes as `sandbox`, which shares
# only the `workspace` group with apiuser. The sudoers rule lets apiuser run
# commands as sandbox and nothing else; env_reset + umask_override give every
# command a clean environment and group-writable files.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git sudo \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system apiuser \
    && groupadd --system workspace \
    && useradd --system --gid apiuser --groups workspace --home-dir /app apiuser \
    && useradd --system --gid workspace --no-create-home --home-dir /nonexistent \
        --shell /usr/sbin/nologin sandbox \
    && printf '%s\n' \
        'Defaults:apiuser !use_pty, !requiretty, env_reset, umask=0007, umask_override' \
        'apiuser ALL=(sandbox) NOPASSWD: ALL' \
        > /etc/sudoers.d/workspace-sandbox \
    && chmod 440 /etc/sudoers.d/workspace-sandbox \
    && mkdir -p /app/data /app/data/workspaces \
    && chown -R apiuser:apiuser /app \
    && chgrp workspace /app/data /app/data/workspaces \
    && chmod 710 /app/data \
    && chmod 2770 /app/data/workspaces

ENV AGENT_SANDBOX_USER=sandbox
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

# ==== Container entrypoint ====
COPY --chown=apiuser:apiuser docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 555 /usr/local/bin/docker-entrypoint.sh

USER apiuser
# ====

# ==== Network configuration ====
EXPOSE 8000
# ====

# ==== Application startup ====
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uv", "run", "--no-sync", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
# ====
