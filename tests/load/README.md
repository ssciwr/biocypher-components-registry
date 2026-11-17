# Upload API load test

Exercises the real ephemeral upload protocol (create session, upload, finalize,
poll, with `429` retries). Each Locust user performs exactly one generation, so
`--users N` means N jobs.

## One-time setup

- Activate the virtualenv that has Locust installed.
- Passwordless SSH to the VM so the resource sampler can run there:
  `ssh-copy-id -p 2222 registryadmin@127.0.0.1`
- On the VM, keep `POSTGRES_PASSWORD` in a `.env` next to the Compose file so
  `docker` commands work in any shell, and start the stack.
- Make the backend reachable from the laptop (VirtualBox forward or SSH tunnel).

## Run

```bash
./tests/load/run_load_test.sh --users 100 --ramp 5 --name 100users_ramp5
```

The script checks health and that scratch is empty, streams `monitor_vm.sh` from
the VM, runs Locust headless until every job finishes, then calls `summarize.py`.
Results go to `~/load-test-runs/<timestamp>_<name>/` (override with
`LOAD_RESULTS_DIR`). Use `--no-vm` to skip VM sampling, `--host` for another
endpoint, and `VM_SSH` to change the SSH command.

Planned sequence: `10/5`, `100/5`, `103/50`. Compare all runs with:

```bash
python tests/load/summarize.py ~/load-test-runs
```

## Scenarios

`--scenario` selects the workload; every file is a valid complete CSV within the
upload limits (at most 1 MiB per file, 50 MiB and 1,000 files per session).

| Scenario | Session content | Purpose |
|---|---|---|
| `small` (default) | One 22-byte CSV | Protocol and session-cap checks |
| `bytes` | 50 files x 1 MiB (about 50 MiB) | Byte budget (110 MiB admits two sessions), `429` retries, tmpfs |
| `files` | 1,000 files x 50 KiB | Maximum file count |
| `wide` | One 1 MiB CSV with 200 columns | Wide-table generation time |
| `custom` | `LOAD_FILES`, `LOAD_FILE_BYTES`, `LOAD_COLUMNS` from the environment | Anything else |

`--jobs-per-user J` makes each user run J generations and `--think S` pauses about
S seconds between them, which gives a steady arrival rate for soak tests:

```bash
./tests/load/run_load_test.sh --users 5 --ramp 5 --scenario bytes \
  --jobs-per-user 8 --think 40 --name soak
```

## Reading the output

| Metric | Meaning |
|---|---|
| `jobs`, `jobs_failed` | Completed generations. `jobs` must equal `--users`. |
| `admission_429_retries` | Times admission was refused and retried. |
| `api p95_ms` | Slowest p95 among the four fast API calls (limit 1000 ms). |
| `end_to_end` | Time from first admission attempt to `complete`, including queueing. |
| `peak_used_MB` | Peak VM RAM from `free -m` (limit 85% of total). |
| `peak_swap_MB`, `swap_sustained_samples` | Swap use; 10 or more samples above the starting value fail the check. |
| `peak_tmpfs_kB`, `final_tmpfs_kB` | Upload scratch usage; the final value must be 0. |

The two extra Locust rows `END-TO-END admission to complete` and
`admission rejected (429)` are metrics, not HTTP calls, and are excluded from
the API checks. Locust's Aggregated row includes them.

The 22-byte artifact of the default scenario does not exercise the 110 MiB byte
budget or meaningful tmpfs use; use the `bytes` scenario for that.

The Locust GUI still works (`locust -f tests/load/locustfile.py`); it stays open
after the jobs finish.
