"""Summarize load-test runs produced by run_load_test.sh.

Usage: python summarize.py RUN_DIR_OR_PARENT [...]
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

REJECTED_ROW = "admission rejected (429)"
END_TO_END_ROW = "END-TO-END admission to complete"
API_ROWS = {
    "POST upload session admission",
    "PUT upload artifact",
    "POST finalize generation",
    "GET generation status",
}
P95_LIMIT_MS = 1000
MEMORY_LIMIT_FRACTION = 0.85
SUSTAINED_SWAP_SAMPLES = 10


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def _meta(run: Path) -> dict[str, str]:
    lines = (run / "meta.txt").read_text().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


def _seconds_between(start: str, end: str) -> float:
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.strptime(end, fmt) - datetime.strptime(start, fmt)).total_seconds()


def _longest_run_above(values: list[float], baseline: float) -> int:
    longest = current = 0
    for value in values:
        current = current + 1 if value > baseline else 0
        longest = max(longest, current)
    return longest


def _locust_metrics(run: Path) -> dict[str, float]:
    rows = {row["Name"]: row for row in _read_csv(run / "locust_stats.csv")}
    api = [rows[name] for name in API_ROWS if name in rows]
    end_to_end = rows.get(END_TO_END_ROW)
    return {
        "api_requests": sum(int(r["Request Count"]) for r in api),
        "api_failures": sum(int(r["Failure Count"]) for r in api),
        "api_p95_ms": max((float(r["95%"]) for r in api), default=0.0),
        "api_max_ms": max((float(r["Max Response Time"]) for r in api), default=0.0),
        "jobs": int(end_to_end["Request Count"]) if end_to_end else 0,
        "jobs_failed": int(end_to_end["Failure Count"]) if end_to_end else 0,
        "e2e_p50_s": float(end_to_end["50%"]) / 1000 if end_to_end else 0.0,
        "e2e_max_s": float(end_to_end["Max Response Time"]) / 1000
        if end_to_end
        else 0.0,
        "rejected_429": int(rows[REJECTED_ROW]["Request Count"])
        if REJECTED_ROW in rows
        else 0,
    }


def _monitor_metrics(run: Path) -> dict[str, float] | None:
    path = run / "vm_monitor.csv"
    if not path.exists():
        return None
    samples = [row for row in _read_csv(path) if row.get("tmpfs_used_kb")]
    if not samples:
        return None

    def column(name: str) -> list[float]:
        return [float(row[name]) for row in samples if row.get(name)]

    swap = column("swap_used_mb")
    total = column("mem_total_mb")[0]
    return {
        "samples": len(samples),
        "mem_total_mb": total,
        "peak_used_mb": max(column("mem_used_mb")),
        "peak_swap_mb": max(swap),
        "swap_sustained_samples": _longest_run_above(swap, swap[0]),
        "peak_tmpfs_kb": max(column("tmpfs_used_kb")),
        "final_tmpfs_kb": column("tmpfs_used_kb")[-1],
        "peak_backend_cpu_pct": max(column("backend_cpu_pct"), default=0.0),
        "peak_backend_mb": max(column("backend_mem_mb"), default=0.0),
        "peak_database_mb": max(column("database_mem_mb"), default=0.0),
    }


def summarize(run: Path) -> dict[str, object]:
    meta = _meta(run)
    locust = _locust_metrics(run)
    monitor = _monitor_metrics(run)
    users = int(meta["users"])
    expected_jobs = users * int(meta.get("jobs_per_user", 1))
    checks = {
        "all jobs finished": locust["jobs"] == expected_jobs
        and locust["jobs_failed"] == 0,
        "no API failures": locust["api_failures"] == 0,
        f"API p95 < {P95_LIMIT_MS} ms": locust["api_p95_ms"] < P95_LIMIT_MS,
    }
    if monitor:
        checks.update(
            {
                f"memory < {MEMORY_LIMIT_FRACTION:.0%}": monitor["peak_used_mb"]
                < MEMORY_LIMIT_FRACTION * monitor["mem_total_mb"],
                "no sustained swap": monitor["swap_sustained_samples"]
                < SUSTAINED_SWAP_SAMPLES,
                "scratch back to 0": monitor["final_tmpfs_kb"] == 0,
            }
        )
    duration = (
        _seconds_between(meta["start_utc"], meta["end_utc"]) if "end_utc" in meta else 0
    )
    return {
        "name": meta["name"],
        "users": users,
        "scenario": meta.get("scenario", "small"),
        "ramp": meta["ramp"],
        "duration_s": duration,
        "locust": locust,
        "monitor": monitor,
        "checks": checks,
    }


def _print_run(result: dict[str, object]) -> None:
    locust, monitor = result["locust"], result["monitor"]
    print(
        f"\n=== {result['name']} (scenario={result['scenario']}, users={result['users']}, ramp={result['ramp']}/s) ==="
    )
    print(
        f"duration_s={result['duration_s']:.0f}  jobs={locust['jobs']:.0f}  jobs_failed={locust['jobs_failed']:.0f}"
    )
    print(f"admission_429_retries={locust['rejected_429']:.0f}")
    print(
        f"api: requests={locust['api_requests']:.0f}  failures={locust['api_failures']:.0f}  "
        f"p95_ms={locust['api_p95_ms']:.0f}  max_ms={locust['api_max_ms']:.0f}"
    )
    print(
        f"end_to_end: median_s={locust['e2e_p50_s']:.1f}  max_s={locust['e2e_max_s']:.1f}"
    )
    if monitor:
        print(
            f"memory: peak_used_MB={monitor['peak_used_mb']:.0f} of {monitor['mem_total_mb']:.0f}  "
            f"peak_swap_MB={monitor['peak_swap_mb']:.0f}  swap_sustained_samples={monitor['swap_sustained_samples']:.0f}"
        )
        print(
            f"scratch: peak_tmpfs_kB={monitor['peak_tmpfs_kb']:.0f}  final_tmpfs_kB={monitor['final_tmpfs_kb']:.0f}"
        )
        print(
            f"containers: backend_cpu_peak_pct={monitor['peak_backend_cpu_pct']:.0f}  "
            f"backend_peak_MB={monitor['peak_backend_mb']:.0f}  database_peak_MB={monitor['peak_database_mb']:.0f}"
        )
    else:
        print("vm monitor: not available")
    for check, passed in result["checks"].items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {check}")


def _runs(paths: list[str]) -> list[Path]:
    runs: list[Path] = []
    for raw in paths:
        path = Path(raw)
        runs += (
            [path]
            if (path / "meta.txt").exists()
            else sorted(p.parent for p in path.glob("*/meta.txt"))
        )
    return runs


def main() -> int:
    runs = _runs(sys.argv[1:])
    if not runs:
        print("No runs found (a run directory contains meta.txt).", file=sys.stderr)
        return 2
    results = [summarize(run) for run in runs]
    for result in results:
        _print_run(result)
    if len(results) > 1:
        print(
            "\n| run | scenario | users | jobs | 429s | API p95 ms | job median s | job max s | peak RAM MB | peak swap MB | peak tmpfs kB | verdict |"
        )
        print("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in results:
            m = r["monitor"] or {}
            verdict = "PASS" if all(r["checks"].values()) else "FAIL"
            print(
                f"| {r['name']} | {r['scenario']} | {r['users']} | {r['locust']['jobs']:.0f} | {r['locust']['rejected_429']:.0f} | "
                f"{r['locust']['api_p95_ms']:.0f} | {r['locust']['e2e_p50_s']:.0f} | {r['locust']['e2e_max_s']:.0f} | "
                f"{m.get('peak_used_mb', float('nan')):.0f} | "
                f"{m.get('peak_swap_mb', float('nan')):.0f} | {m.get('peak_tmpfs_kb', float('nan')):.0f} | {verdict} |"
            )
    return 0 if all(all(r["checks"].values()) for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
