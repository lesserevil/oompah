# Service Throughput Recovery Plan

## Context

The production service on `doorman:8090` is responsive but degraded. A live
inspection on 2026-08-26 found that full workflow reconciliation takes roughly
239–334 seconds, with integration fact collection accounting for 176–310
seconds. During those long passes the state snapshot becomes stale, durable
publication can miss its 120-second convergence deadline, and otherwise-ready
work waits behind repeated reconciliation.

The same inspection found several reinforcing problems:

- 67 tasks were `Ready to Integrate`, while review creation and review
  reconciliation repeatedly queried forge state.
- A 10,000-line log sample contained 7,708 forge HTTP requests, including over
  4,000 duplicate status/check-run requests and hundreds of identical epic
  branch review lookups.
- `GET /api/v1/reviews` blocked for more than 20 seconds instead of returning a
  bounded cached response.
- The workflow database was 5.0 GB, with 19,978,498 cold
  `publication_rollback` rows left after the historical rollback storm.
- Oompah's runtime directory occupied about 140 GB. Trickle worktrees accounted
  for about 123 GB, overwhelmingly duplicated Cargo `target/` trees, and test
  temporary directories accounted for another 8.6 GB.
- The deployment's protected workflow evidence pin still described the old
  three-version matrix and old workflow blob, while current CI has one
  `test (3.12)` job and blob `269db57c687e533bfaa90d961cf4c53f4069a7a8`.
- Seven workflow decisions required operator action, including stale exhausted
  jobs for already-terminal tasks and recoverable integration failures.

The active projects and global scheduler were paused before implementation so
Oompah cannot dispatch these recovery tasks.

## Objectives

1. Restore useful throughput without weakening lifecycle, audit, or CI safety.
2. Make reconciliation cost proportional to distinct external evidence rather
   than the number of tasks referencing it.
3. Make operator-facing read APIs return promptly from bounded snapshots.
4. Put durable history, logs, temporary test data, and build products under a
   deliberate retention policy.
5. Repair current deployment configuration and stale operator-action records,
   then verify recovery with the production rollout gate.

## Tracked implementation

- `OOMPAH-1343` — stabilize production and clear current workflow blockers.
- `OOMPAH-1344` — bound workflow reconciliation and deduplicate forge observations.
- `OOMPAH-1345` — serve the reviews API from a bounded generation-aware snapshot.
- `OOMPAH-1346` — bound workflow history and workspace storage growth.

These are children of `OOMPAH-1342`. During recovery they are protected by
explicit direct-owner claims and the service is globally paused so no managed
implementation worker can take them over.

## Workstreams

### 1. Stabilize and recover the deployment

Keep all projects paused while changing configuration or maintenance state.
Update the protected-workflow allowlist to the reviewed current workflow blob
and job set. Land already-green recovery changes in dependency-aware order,
apply them with a graceful restart, resolve stale exhausted jobs using their
supported owner actions, and resume projects only after health and throughput
checks pass.

Acceptance evidence:

- no active provider processes during maintenance;
- protected CI evidence exactly matches the current workflow;
- current exhausted decisions are either rearmed with fresh evidence or
  explicitly retained as terminal provenance;
- `make workflow-rollout-check` passes before normal dispatch resumes.

### 2. Bound reconciliation and forge observations

Profile and eliminate repeated provider calls during a single authoritative
world scan. Cache review lookup, CI status, branch-head, parent, and landing
observations within the generation-bound reconciliation scope. Avoid evaluating
terminal tasks that already have complete durable landing/provenance evidence.
Preserve fail-closed behavior and invalidate all caches at authority changes.

Acceptance evidence:

- production-shaped tests with hundreds of Done/Ready tasks assert bounded SCM
  calls by distinct branch/review/target, not task count;
- mutation during collection still supersedes publication;
- exact-head and project-scope fences remain intact;
- the Trickle-sized reconciliation fixture completes within the configured
  restart budget.

### 3. Make reviews API bounded and snapshot-backed

Stop `GET /api/v1/reviews` from synchronously refreshing every forge on a cache
miss. Publish a generation-aware review snapshot from background/event-driven
collection and return it immediately. Represent stale or unavailable projects
explicitly without replacing good sibling project data with a false empty.

Acceptance evidence:

- API tests prove a cold request does not perform network I/O;
- stale/error metadata is visible and bounded;
- webhook and successful refreshes invalidate or advance the snapshot;
- a slow or failed provider cannot block the endpoint.

### 4. Add bounded storage retention and cleanup

Introduce explicit, configurable retention for cold workflow audit events and
safe cleanup for logs, pytest temporary roots, and terminal worktree build
products. Cleanup must preserve active, dirty, unmerged, audit-protected, and
shared-owner work. SQLite compaction must be offline or incrementally bounded;
no unbounded `VACUUM` may run on the scheduler path.

Acceptance evidence:

- tests prove protected artifacts are never removed;
- cleanup has batch/time budgets, durable metrics, and dry-run diagnostics;
- old cold events are summarized or deleted according to configured retention;
- the scheduler remains responsive while cleanup executes.

## Rollout order

1. Keep all projects paused and capture backups/metrics.
2. Apply the protected CI evidence correction.
3. Land existing reviewed recovery fixes, especially canonical remote handling
   and rollback-storm regression coverage.
4. Deploy reconciliation and reviews-API performance fixes.
5. Run bounded storage cleanup and reclaim inactive build products.
6. Resolve or rearm the seven current operator-action records.
7. Run focused tests, the complete branch gate, and
   `make workflow-rollout-check`.
8. Resume one project at a time, observe at least two complete reconciliation
   generations, then restore normal operation.

## Safety and rollback

- Use `make graceful`; do not force-restart while work is active.
- Back up each SQLite database together with its WAL/SHM files before offline
  compaction.
- Do not hand-edit native task files or durable job rows.
- Keep workflow modes in `enforce`; changing them to `shadow` is a fail-safe
  pause, not a migration mechanism.
- If a new change fails the rollout gate, restore the matching binary,
  configuration, and SQLite backup as one unit.
