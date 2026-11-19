"""Fixed safety limits for transient dataset uploads.

These values are part of the web-upload protocol. They deliberately live in
code rather than environment files so the API, tests, and frontend share one
stable contract.
"""

from pathlib import Path

# ===========================================================
# Source and Artifact Limits
# ===========================================================

MAX_FILES_PER_SOURCE = 1_000
MAX_ARTIFACT_BYTES = 1 * 1024 * 1024
MAX_SESSION_ARTIFACT_BYTES = 50 * 1024 * 1024
MAX_GLOBAL_SCRATCH_BYTES = 110 * 1024 * 1024

# ===========================================================
# Session and Generator Limits
# ===========================================================

MAX_ACTIVE_SESSIONS = 100
MAX_CONCURRENT_GENERATIONS = 1
SESSION_IDLE_TTL_SECONDS = 10 * 60
SESSION_START_TTL_SECONDS = 60
RESULT_TTL_SECONDS = 10 * 60
MAX_TERMINAL_RESULTS = 2
REAPER_INTERVAL_SECONDS = 30
GENERATOR_TIMEOUT_SECONDS = 120
MAX_GENERATED_JSON_BYTES = 10 * 1024 * 1024
MAX_DIAGNOSTIC_BYTES = 16 * 1024

# ===========================================================
# Ephemeral Scratch Contract
# ===========================================================

UPLOAD_SCRATCH_ROOT = Path("/run/biocypher-upload-scratch")
EXPECTED_SCRATCH_FILESYSTEM = "tmpfs"

SUPPORTED_FORMATS = frozenset({"csv", "tsv"})
SUPPORTED_STRATEGIES = frozenset(
    {
        "complete-file-v1",
        "csv-complete-rows-v1",
        "tsv-complete-rows-v1",
        "csv-gzip-complete-rows-v1",
        "tsv-gzip-complete-rows-v1",
    }
)
