# Tick Latency Diagnostics

## Overview

oompah's dispatch loop runs on a periodic tick. Each tick:

1. Reconciles running agents against the tracker (`reconcile`)
2. Fetches forge state (PRs, merged branches) (`review_check`)
3. **Fetches candidates and dispatches eligible tasks** (`dispatch_needed`)
4. Runs YOLO merge actions and auto-archive (`yolo_review`)
5. Runs watchdog and repo self-heal (`watchdog`, `repo_heal`)

**Dispatch always runs before maintenance.** If a slow maintenance job (repo
self-heal, worktree cleanup) extends a tick to 150 seconds, the eligible tasks
*in that tick* were already dispatched before maintenance started. However, the
*next* tick is delayed, so new tasks that become eligible during the long tick
must wait.

The bounded-refresh infrastructure (TASK-467.2) caps how long each project's
tracker fetch can take. If a project's fetch times out, oompah falls back to
stale cached data and continues dispatching from other projects without delay.

---

## Reading the Diagnostics

The `/api/v1/state` endpoint returns an `orchestrator_metrics` block:

```json
{
  "orchestrator_metrics": {
    "last_tick": { "total_ms": 420, "dispatch_ms": 80, "reconcile_ms": 12, ... },
    "maintenance": {
      "repo_heal":        { "last_run_at": "2026-06-09T05:00:00Z", "duration_ms": 3200 },
      "worktree_cleanup": { "last_run_at": "2026-06-09T05:00:00Z", "cleaned": 4, "deferred": false },
      "auto_archive":     { "last_run_at": "2026-06-09T05:00:00Z", "cleaned": 0, "deferred": false }
    },
    "project_refresh": {
      "proj-backend": {
        "candidates": { "last_duration_ms": 95.3, "success_count": 42, "timeout_count": 0, "last_error": null },
        "reviews":    { "last_duration_ms": 120.7, "success_count": 38, "timeout_count": 2, "last_error": "timeout after 5000ms" }
      },
      "proj-frontend": {
        "candidates": { "last_duration_ms": 4821.0, "success_count": 1, "timeout_count": 7, "last_error": "timeout after 5000ms" }
      }
    },
    "last_dispatch": { "candidate_count": 14, "ready_count": 2, "dispatched_count": 1, ... }
  }
}
```

### `last_tick`

| Field          | What it means                                              |
|----------------|------------------------------------------------------------|
| `total_ms`     | Wall-clock time for the entire tick                        |
| `dispatch_ms`  | Time spent in `_handle_dispatch_needed` (candidates + sort + dispatch) |
| `reconcile_ms` | Time spent reconciling running agents against the tracker  |
| `reviews_ms`   | Time to fetch forge PRs/MRs                               |
| `post_yolo_ms` | Time for watchdog + repo self-heal after dispatch          |

**Action**: If `total_ms` > 5000 but `dispatch_ms` is small, look at `maintenance`
or `project_refresh` — those phases are the bottleneck.

### `maintenance`

| Sub-key            | Key fields                                      |
|--------------------|-------------------------------------------------|
| `repo_heal`        | `duration_ms`, `last_run_at`, `delayed`         |
| `worktree_cleanup` | `cleaned`, `deferred`, `cursor`, `last_run_at`  |
| `auto_archive`     | `cleaned`, `deferred`, `cursor`, `last_run_at`  |

- **`deferred: true`** — the job hit its batch limit mid-run and will resume on
  the next eligible tick. Normal for large repos.
- **`delayed: true` on `repo_heal`** — startup delay has not yet elapsed. The job
  won't run until `maintenance_startup_delay_seconds` (default: 60) after process
  start.
- **High `duration_ms` on `repo_heal`** — git I/O is slow. Common on NFS mounts or
  during large fetches. This extends the tick but does not block dispatch within
  the same tick.

### `project_refresh`

Each project has per-operation metrics:

| Field              | What it means                                           |
|--------------------|---------------------------------------------------------|
| `last_duration_ms` | How long the last refresh attempt took (wall clock)     |
| `success_count`    | Successful refreshes since process start                |
| `timeout_count`    | Times the refresh timed out and stale data was used     |
| `last_error`       | Error message from the most recent failure              |

**Action**: High `timeout_count` on a project's `candidates` operation means
oompah repeatedly cannot fetch that project's tasks within
`project_refresh_timeout_ms` (default: 5000 ms). Candidates for that project
will be served from stale cache.

---

## Common Scenarios

### Scenario 1: One project is slow; others dispatch normally

```
project_refresh.proj-slow.candidates.timeout_count: 12
project_refresh.proj-slow.candidates.last_error: "timeout after 5000ms"
project_refresh.proj-fast.candidates.timeout_count: 0
```

**What happened**: proj-slow's tracker fetch consistently times out. oompah
falls back to the last known candidate list for that project (may be stale or
empty) and dispatches normally from proj-fast. No cross-project blocking.

**Remediation**:
- Check the tracker for proj-slow (large task files? filesystem issue?)
- Increase `project_refresh_timeout_ms` if the tracker is normally fast but
  occasionally spikes
- Set `project_refresh_max_concurrent` to limit parallelism if disk I/O contention
  is the root cause

### Scenario 2: Long total_ms, small dispatch_ms

```
last_tick.total_ms: 38000
last_tick.dispatch_ms: 95
maintenance.repo_heal.duration_ms: 37800
```

**What happened**: Repo self-heal (git fetch + pull + hard-reset across all
projects) took 37.8 seconds. Dispatch completed in 95 ms, before the long
maintenance phase.

**Implication**: Tasks that become eligible *during* the 37.8-second repo-heal
window must wait for the next tick. This is the original long-tick scenario
(TASK-467.4). The fix is bounded refresh — each project's fetch is capped
at `project_refresh_timeout_ms`, and maintenance runs after dispatch within
each tick.

**Remediation**:
- Review `full_sync_interval_ms` (default: 300 000 ms = 5 min). If self-heal
  runs too often, increase this interval.
- On repos with many worktrees, `worktree_cleanup_batch_size` limits how many
  worktrees are cleaned per tick, preventing single-tick cleanup storms.

### Scenario 3: Running agent in Project A; eligible task in Project B not dispatching

Symptoms:
```
running: [{ issue_identifier: "TASK-A-001", project_id: "proj-a" }]
last_dispatch.dispatched_count: 0
```

Check:
1. `available_slots` — is `max_in_flight` reached?
2. `project_refresh.proj-b.candidates.timeout_count` — is proj-b timing out?
3. `maintenance.repo_heal.delayed: true` — startup delay active?

If slots are available and proj-b candidates are fetched, check the task itself
via `/api/v1/state` → `running`/`retrying` for any reject reason.

---

## Key Configuration Variables

| Variable                        | Default | Description                                              |
|---------------------------------|---------|----------------------------------------------------------|
| `project_refresh_timeout_ms`    | 5000    | Per-project tracker fetch timeout (ms)                   |
| `project_refresh_max_concurrent`| 4       | Max parallel refreshes per project                       |
| `project_stale_cache_ttl_ms`    | 300000  | How long stale cached data is valid (ms)                 |
| `full_sync_interval_ms`         | 300000  | Minimum interval between repo self-heal runs (ms)        |
| `worktree_cleanup_batch_size`   | 25      | Worktrees cleaned per maintenance pass                   |
| `maintenance_startup_delay_seconds` | 60  | Grace period before maintenance jobs start               |

All variables can be set via `.env` with the `OOMPAH_` prefix (e.g.
`OOMPAH_PROJECT_REFRESH_TIMEOUT_MS=10000`).
