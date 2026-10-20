#!/bin/sh
set -eu

# New files are private to apiuser.
umask 007

# Volumes created by older images keep their old permissions: re-apply the
# sandbox layout so pool users can reach the workspaces root but nothing else
# under /app/data.
if [ -n "${AGENT_SANDBOX_USER_PREFIX:-}" ]; then
    workspaces="${AGENT_WORKSPACES_ROOT:-/app/data/workspaces}"
    data_dir="$(dirname "$workspaces")"
    mkdir -p "$workspaces"
    # Skip the workspaces tree: it is closed to others already and may hold
    # sandbox-owned files this user cannot chmod. Leftover workspaces are
    # removed by the API at startup.
    find "$data_dir" -path "$workspaces" -prune -o -exec chmod o-rwx {} +
    # Pool users may traverse /app/data (group sandbox, x only) to reach the
    # workspaces root, but not list it; others get nothing.
    chgrp sandbox "$data_dir"
    chmod 710 "$data_dir"
    # Sticky and group-writable without read: a pool user can create its own
    # workspace there, but not list, rename or remove anyone else's.
    chgrp sandbox "$workspaces"
    chmod 1730 "$workspaces"
fi

exec "$@"
