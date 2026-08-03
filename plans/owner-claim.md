# Owner-Claim: Durable Direct-Owner Fence for In-Progress Tasks

**Status:** Proposed — not yet implemented (OOMPAH-707)  
**Triggered by:** OOMPAH-701 production evidence

## Problem

When a project owner sets a task to **In Progress** and begins direct implementation — without dispatching a scheduler agent — the orphan-watchdog resets it back to **Open** within minutes. This happened twice on OOMPAH-701 on 2026-08-02.

### Root cause

`_reset_orphaned_in_progress()` (`oompah/orchestrator.py`, ~line 15228) resets every In Progress task whose `issue.id` is absent from three in-memory sets:

| Set | What it tracks |
|---|---|
| `state.running` | Issues with an active `RunningEntry` (scheduler agent started) |
| `state.retry_attempts` | Issues in the retry backoff window |
| `state.claimed` | Issues that the scheduler has claimed for dispatch but not yet started |

A human who directly moves a task to In Progress has no representation in any of these sets. From the watchdog's perspective, the task looks orphaned — and it resets it.

### Why `human-only` is not enough

The `human-only` label blocks dispatch (lines 14654, 10591) but is **not checked in `_reset_orphaned_in_progress()`**. A human-only task that is In Progress is still reset.

---

## Proposed Design

Add a **durable owner-claim** — a time-bounded lease that tells the watchdog "this task is being worked on directly by a named owner; do not reset it."

### Data model

```python
@dataclass
class OwnerClaim:
    """Time-bounded direct-owner work lease."""
    claim_id: str          # uuid4 hex — unique per claim grant
    issue_id: str          # tracker issue id (matches OrchestratorState keys)
    project_id: str | None # project scope; None for legacy unscoped tracker
    owner_login: str       # the login that placed the claim
    claimed_at: float      # UTC epoch seconds (time.time())
    expires_at: float      # UTC epoch seconds; watchdog respects until this passes
    renewable: bool = True # if True, activity against the issue extends expiry
```

**Default expiry:** 48 hours from claim time (configurable via `OOMPAH_OWNER_CLAIM_TTL_HOURS`).

### State integration

Add to `OrchestratorState` in `oompah/models.py`:

```python
@dataclass
class OrchestratorState:
    ...
    # Direct-owner work leases, keyed by issue_id.
    # A live (non-expired) entry prevents orphan-watchdog reset.
    # Persisted to service_state.json so restarts preserve active claims.
    owner_claims: dict[str, "OwnerClaim"] = field(default_factory=dict)
```

### Persistence

Owner claims survive service restarts via the existing `_save_state()` / `_load_state()` path:

```python
# On claim grant or renewal:
self._save_state(owner_claims={
    issue_id: dataclasses.asdict(claim)
    for issue_id, claim in self.state.owner_claims.items()
})

# On service startup (in _load_state / __init__):
for issue_id, raw in state_data.get("owner_claims", {}).items():
    self.state.owner_claims[issue_id] = OwnerClaim(**raw)
```

### Watchdog guard

In `_reset_orphaned_in_progress()`, add a check before the reset:

```python
# Skip issues covered by a live owner claim.
claim = self.state.owner_claims.get(issue.id)
if claim is not None:
    if claim.expires_at > time.time():
        logger.debug(
            "Owner claim active for %s (owner=%s, expires=%s) — skipping orphan reset",
            issue.identifier, claim.owner_login,
            datetime.fromtimestamp(claim.expires_at, tz=timezone.utc).isoformat(),
        )
        continue
    else:
        # Claim has expired — purge it and fall through to reset.
        logger.info(
            "Owner claim expired for %s (owner=%s) — proceeding with orphan reset",
            issue.identifier, claim.owner_login,
        )
        del self.state.owner_claims[issue.id]
        self._save_state(owner_claims={
            k: dataclasses.asdict(v) for k, v in self.state.owner_claims.items()
        })
```

### API endpoints

Three REST endpoints manage claims:

#### `POST /api/v1/projects/{project_id}/tasks/{identifier}/owner-claim`

Grant a direct-owner claim. Requires the caller to be the `status_actor_login` or an authorized login from `status_label_authorized_logins`.

**Request body (optional):**
```json
{ "actor_login": "alice", "ttl_hours": 24 }
```

**Response:**
```json
{
  "claim_id": "a1b2c3d4...",
  "issue_id": "issue-uuid",
  "owner_login": "alice",
  "claimed_at": "2026-08-02T22:30:00Z",
  "expires_at": "2026-08-03T22:30:00Z"
}
```

**Behavior:**
- Atomically moves the task to `In Progress` and creates `OwnerClaim` in
  project-scoped `state.owner_claims`, eliminating the status-to-claim race
- If a live claim already exists for this issue (same or different owner), replaces it and resets expiry
- `ttl_hours` may shorten the lease but cannot exceed the configured maximum
- Persists via `_save_state()`
- Acquires per-project write lock (same lock as orphan-reset writes) to serialize with concurrent watchdog scans

#### `DELETE /api/v1/projects/{project_id}/tasks/{identifier}/owner-claim`

Release a claim explicitly. The task returns to the normal dispatchable lifecycle on the next watchdog tick.

**Response:** `{ "released": true }`

**Behavior:**
- Removes `state.owner_claims[issue.id]`
- Persists via `_save_state()`
- Acquires per-project write lock

#### `GET /api/v1/projects/{project_id}/tasks/{identifier}/owner-claim`

Retrieve current claim state for observability and dashboard display.

**Response (active claim):**
```json
{
  "active": true,
  "claim_id": "a1b2c3d4...",
  "owner_login": "alice",
  "claimed_at": "2026-08-02T22:30:00Z",
  "expires_at": "2026-08-03T22:30:00Z",
  "age_seconds": 1800,
  "remaining_seconds": 84600
}
```

**Response (no claim):**
```json
{ "active": false }
```

### Race serialization

The watchdog and claim operations share the same per-project write lock (`project_store.project_write_lock(project_id)`) already used in the orphan-reset `with _lock_ctx:` block. This ensures:

- A concurrent watchdog scan cannot read `state.owner_claims` during a claim write
- A concurrent claim grant cannot race with an in-flight reset that already read the absence of a claim

For the unscoped (legacy) tracker path the lock is a `contextlib.nullcontext()`, matching the existing behavior for single-tracker deployments.

The watchdog read of `state.owner_claims` and the subsequent conditional reset must both occur **inside** the acquired lock to eliminate the TOCTOU window. The claim route performs its `In Progress` transition under the same lock, so callers should use the claim route instead of a separate status update followed by a claim:

```python
_lock_ctx = (
    self.project_store.project_write_lock(project_id)
    if project_id
    else contextlib.nullcontext()
)
with _lock_ctx:
    # Re-read claim state under lock in case a concurrent grant just arrived.
    claim = self.state.owner_claims.get(issue.id)
    if claim is not None and claim.expires_at > time.time():
        continue  # preserved
    # ... reset ...
```

### Expiry and bounded-abandonment policy

An owner claim that is never explicitly released expires after `TTL_HOURS` (default 48). Once expired:

1. The next watchdog scan removes the claim and resets the task to Open
2. The task is then available for scheduler dispatch as normal

**No silent strand:** An expired claim cannot keep a task stuck. The 48-hour TTL is the maximum time a directly-owned task can remain In Progress after the owner stops responding.

**Dashboard visibility:** The `get_snapshot()` response includes an `owner_claims` list so the dashboard can display:
- Owner login and claim age on In Progress tasks with active claims
- Expiry time as a staleness indicator
- Whether the task is covered by a scheduler agent or a direct-owner claim

---

## Required tests

Per the task acceptance criteria:

1. **Claim survives repeated scans.** Grant an owner claim on a human-only In Progress issue. Run `_reset_orphaned_in_progress()` five times in a row. The task must remain In Progress each time.

2. **Expired claim is reset.** Grant an owner claim with a very short TTL (e.g., 1 second). Sleep past expiry. Run `_reset_orphaned_in_progress()`. The task must be reset to Open and the claim removed.

3. **Explicit release triggers reset.** Grant a claim, call `DELETE /owner-claim`, run `_reset_orphaned_in_progress()`. The task must be reset to Open.

4. **Scheduler orphan behavior unchanged.** An In Progress task with no agent, no retry, no claim, and no owner claim is still reset to Open — the new guard must only apply when a live owner claim exists.

5. **Race serialization.** Simulate a concurrent claim grant and watchdog scan. After both complete, the task must be in exactly one consistent state — either preserved (grant won the lock) or reset (scan won and grant wrote a new record to an already-reset task, which is idempotent).

---

## Acceptance criteria

- A project owner who sets a task to In Progress and grants an owner claim will see the task remain In Progress through repeated watchdog ticks.
- An expired or explicitly released claim results in the task being returned to Open on the next watchdog tick.
- Scheduler-originated orphan recovery is unaffected when no owner claim exists.
- The dashboard and `get_snapshot()` API surface the owner login, claim age, and expiry for any covered task.
- `make test` passes, focused race tests pass, `make check-secrets` passes.

---

## Implementation map

| File | Change |
|---|---|
| `oompah/models.py` | Add `OwnerClaim` dataclass; add `owner_claims` field to `OrchestratorState` |
| `oompah/orchestrator.py` | `_reset_orphaned_in_progress()`: add claim guard; `_load_state()`: deserialize claims; `_save_state()` call sites: persist claims; `get_snapshot()`: include `owner_claims` in response |
| `oompah/server.py` (or API router) | `POST/DELETE/GET /api/v1/projects/{pid}/tasks/{id}/owner-claim` |
| `tests/` | New test module `tests/test_owner_claim.py` covering the five scenarios above |
| `docs/operator-runbook.md` | Add section: "Protecting direct owner work from orphan reset" |

---

## Related documents

- `plans/polling-mechanisms.md` — Describes the orchestrator main loop and maintenance lane scheduling that drives orphan reset
- `plans/terminal-transition-coordinator.md` — Pattern for per-project locking and state serialization (reference)
- `docs/task-epic-workflow.md` — Workflow context for human-only and direct-owner tasks
