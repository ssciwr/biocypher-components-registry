#!/usr/bin/env bash
# One reproducible load-test run: VM sampling + headless Locust + summary.
#
#   ./tests/load/run_load_test.sh --users 100 --ramp 5 --name 100users_ramp5
#
# Requires the virtualenv with Locust to be active and passwordless SSH to the VM.
# Environment overrides:
#   VM_SSH            ssh command for the VM   (default: ssh -p 2222 registryadmin@127.0.0.1)
#   LOAD_RESULTS_DIR  where runs are stored    (default: ~/load-test-runs)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
VM_SSH="${VM_SSH:-ssh -p 2222 -o BatchMode=yes registryadmin@127.0.0.1}"
RESULTS_DIR="${LOAD_RESULTS_DIR:-$HOME/load-test-runs}"
HOST="http://127.0.0.1:8000"
MAX_RUN_TIME="30m"
USERS="" RAMP="" NAME="" MONITOR=1 SCENARIO="small" JOBS_PER_USER=1 THINK=0

usage() {
  echo "Usage: $0 --users N --ramp R [--scenario small|bytes|files|wide|custom] [--jobs-per-user J] [--think S] [--name NAME] [--host URL] [--no-vm] [--max-run-time 30m]" >&2
  echo "  small: 22-byte CSV | bytes: 50 files x 1 MiB | files: 1000 files x 50 KiB | wide: one 1 MiB CSV with 200 columns" >&2
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --users) USERS="$2"; shift 2 ;;
    --ramp) RAMP="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    --max-run-time) MAX_RUN_TIME="$2"; shift 2 ;;
    --no-vm) MONITOR=0; shift ;;
    --scenario) SCENARIO="$2"; shift 2 ;;
    --jobs-per-user) JOBS_PER_USER="$2"; shift 2 ;;
    --think) THINK="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[[ -n "$USERS" && -n "$RAMP" ]] || usage
NAME="${NAME:-${USERS}users_ramp${RAMP}}"

case "$SCENARIO" in
  small) LOAD_FILES=1;    LOAD_FILE_BYTES=0;       LOAD_COLUMNS=2 ;;
  bytes) LOAD_FILES=50;   LOAD_FILE_BYTES=1048576; LOAD_COLUMNS=10 ;;
  files) LOAD_FILES=1000; LOAD_FILE_BYTES=51200;   LOAD_COLUMNS=5 ;;
  wide)  LOAD_FILES=1;    LOAD_FILE_BYTES=1048576; LOAD_COLUMNS=200 ;;
  custom) LOAD_FILES="${LOAD_FILES:-1}"; LOAD_FILE_BYTES="${LOAD_FILE_BYTES:-0}"; LOAD_COLUMNS="${LOAD_COLUMNS:-2}" ;;
  *) usage ;;
esac
export LOAD_FILES LOAD_FILE_BYTES LOAD_COLUMNS
export LOAD_JOBS_PER_USER="$JOBS_PER_USER" LOAD_THINK_SECONDS="$THINK"

command -v locust >/dev/null || { echo "locust not found: activate the virtualenv first." >&2; exit 1; }

RUN_DIR="$RESULTS_DIR/$(date +%Y-%m-%d_%H%M%S)_$NAME"
mkdir -p "$RUN_DIR"

echo "Checking $HOST ..."
curl -fsS -m 5 "$HOST/api/v1/health" >/dev/null || { echo "Health check failed." >&2; exit 1; }

if [[ $MONITOR -eq 1 ]]; then
  # shellcheck disable=SC2086
  scratch=$($VM_SSH "docker exec biocypher-registry-backend df -k /run/biocypher-upload-scratch" | awk 'NR==2{print $3}')
  [[ "$scratch" == "0" ]] || { echo "Scratch is not empty at start (${scratch} kB); wait or restart the backend." >&2; exit 1; }
  # shellcheck disable=SC2086
  $VM_SSH "bash -s" < "$HERE/monitor_vm.sh" > "$RUN_DIR/vm_monitor.csv" &
  MONITOR_PID=$!
  trap 'kill "$MONITOR_PID" 2>/dev/null || true' EXIT
  sleep 3
fi

cat > "$RUN_DIR/meta.txt" <<EOF
name=$NAME
users=$USERS
ramp=$RAMP
scenario=$SCENARIO
files=$LOAD_FILES
file_bytes=$LOAD_FILE_BYTES
columns=$LOAD_COLUMNS
jobs_per_user=$JOBS_PER_USER
think_seconds=$THINK
host=$HOST
commit=$(git -C "$REPO" rev-parse HEAD)
branch=$(git -C "$REPO" rev-parse --abbrev-ref HEAD)
locust=$(locust --version)
start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

locust -f "$HERE/locustfile.py" --host "$HOST" --headless \
  --users "$USERS" --spawn-rate "$RAMP" --run-time "$MAX_RUN_TIME" \
  --csv "$RUN_DIR/locust" --html "$RUN_DIR/report.html" --only-summary \
  || echo "Locust exited with a non-zero status (failures were recorded)."

echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$RUN_DIR/meta.txt"

if [[ $MONITOR -eq 1 ]]; then
  sleep 3  # capture the final scratch value after cleanup
  kill "$MONITOR_PID" 2>/dev/null || true
  wait "$MONITOR_PID" 2>/dev/null || true
  trap - EXIT
fi

python3 "$HERE/summarize.py" "$RUN_DIR"
echo "Results: $RUN_DIR"
