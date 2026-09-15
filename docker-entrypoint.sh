#!/bin/sh
set -eu

prepare_dir() {
    if [ -n "$1" ]; then
        mkdir -p "$1"
        chown -R apiuser:apiuser "$1"
    fi
}

prepare_dir /app/data

if [ -n "${BIOCYPHER_REGISTRY_DB_PATH:-}" ]; then
    prepare_dir "$(dirname "$BIOCYPHER_REGISTRY_DB_PATH")"
fi

if [ -n "${AGENT_WORKSPACES_ROOT:-}" ]; then
    prepare_dir "$AGENT_WORKSPACES_ROOT"
fi

exec gosu apiuser "$@"
