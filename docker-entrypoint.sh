#!/bin/sh
set -eu

# New files are private to apiuser, except inside workspaces, whose setgid
# directories share them with the sandbox user through the `workspace` group.
umask 007

# Volumes created by older images keep their old permissions: re-apply the
# sandbox layout so the sandbox user can reach the workspaces but nothing else
# under /app/data.
if [ -n "${AGENT_SANDBOX_USER:-}" ]; then
    workspaces="${AGENT_WORKSPACES_ROOT:-/app/data/workspaces}"
    data_dir="$(dirname "$workspaces")"
    mkdir -p "$workspaces"
    # Skip the workspaces tree: it is closed to others already and may hold
    # sandbox-owned files this user cannot chmod.
    find "$data_dir" -path "$workspaces" -prune -o -exec chmod o-rwx {} +
    # The sandbox user may traverse /app/data (group workspace, x only) to
    # reach its workspace, but not list it; others get nothing.
    chgrp workspace "$data_dir"
    chmod 710 "$data_dir"
    chgrp workspace "$workspaces"
    chmod 2770 "$workspaces"
fi

exec "$@"
