#!/usr/bin/env bash
# Samples VM and container resources and prints one CSV row per sample.
# Runs on the VM; run_load_test.sh streams it over SSH. Standalone use:
#   ./monitor_vm.sh | tee vm_monitor.csv      (stop with Ctrl+C)
set -u

BACKEND="${BACKEND_CONTAINER:-biocypher-registry-backend}"
DATABASE="${DATABASE_CONTAINER:-biocypher-registry-database}"
SCRATCH="${SCRATCH_PATH:-/run/biocypher-upload-scratch}"
INTERVAL="${SAMPLE_INTERVAL_SECONDS:-1}"

echo "timestamp_utc,mem_total_mb,mem_used_mb,mem_available_mb,swap_used_mb,tmpfs_used_kb,backend_cpu_pct,backend_mem_mb,database_mem_mb"

while true; do
  read -r mem_total mem_used mem_available swap_used < <(
    free -m | awk '/^Mem:/{t=$2;u=$3;a=$7} /^Swap:/{s=$3} END{print t,u,a,s}')
  tmpfs_used=$(docker exec "$BACKEND" df -k "$SCRATCH" 2>/dev/null | awk 'NR==2{print $3}')
  backend_cpu=""; backend_mem=""; database_mem=""
  while IFS=, read -r name cpu mem; do
    # MemUsage looks like "123.4MiB / 3.8GiB"; keep the used part in MB.
    used_mb=$(echo "$mem" | awk '{v=$1; if (v ~ /GiB$/) {sub(/GiB/,"",v); v*=1024} else if (v ~ /MiB$/) {sub(/MiB/,"",v)} else if (v ~ /KiB$/) {sub(/KiB/,"",v); v/=1024} else {sub(/B$/,"",v); v/=1048576}; printf "%.1f", v}')
    case "$name" in
      "$BACKEND") backend_cpu="${cpu%\%}"; backend_mem="$used_mb" ;;
      "$DATABASE") database_mem="$used_mb" ;;
    esac
  done < <(docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}}' "$BACKEND" "$DATABASE" 2>/dev/null)
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),$mem_total,$mem_used,$mem_available,$swap_used,${tmpfs_used:-},$backend_cpu,$backend_mem,$database_mem"
  sleep "$INTERVAL"
done
