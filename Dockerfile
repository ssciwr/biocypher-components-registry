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

# Agentic workspace sandbox: every active session leases its own user from a
# pool sandbox1..N (N = maximum concurrent sessions overall). Each session's
# workspace belongs to its user (mode 0700), so sessions cannot read each
# other's files nor inspect each other's processes. Pool users have private
# primary groups and share only the `sandbox` group, which lets them traverse
# /app/data and create their workspace in the workspaces root (sticky, no
# read: they can neither list nor remove other entries). The sudoers rule lets
# apiuser run commands as pool users and nothing else; env_reset +
# umask_override give every command a clean environment and private files.
ARG SANDBOX_POOL_SIZE=20
RUN apt-get update \
    && apt-get install -y --no-install-recommends git sudo \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system apiuser \
    && groupadd --system sandbox \
    && useradd --system --gid apiuser --home-dir /app apiuser \
    && pool="" \
    && for i in $(seq 1 "$SANDBOX_POOL_SIZE"); do \
        useradd --system --user-group --groups sandbox --no-create-home \
            --home-dir /nonexistent --shell /usr/sbin/nologin "sandbox$i"; \
        pool="${pool:+$pool,}sandbox$i"; \
    done \
    && printf '%s\n' \
        'Defaults:apiuser !use_pty, !requiretty, env_reset, umask=0077, umask_override' \
        "Runas_Alias SANDBOX_POOL = $pool" \
        'apiuser ALL=(SANDBOX_POOL) NOPASSWD: ALL' \
        > /etc/sudoers.d/workspace-sandbox \
    && chmod 440 /etc/sudoers.d/workspace-sandbox \
    && visudo -cf /etc/sudoers.d/workspace-sandbox \
    && mkdir -p /app/data /app/data/workspaces \
    && chown -R apiuser:apiuser /app \
    && chgrp sandbox /app/data /app/data/workspaces \
    && chmod 710 /app/data \
    && chmod 1730 /app/data/workspaces

ENV AGENT_SANDBOX_USER_PREFIX=sandbox \
    AGENT_SANDBOX_POOL_SIZE=${SANDBOX_POOL_SIZE}
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
