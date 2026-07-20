# State Branch Migration Readiness Guide

This guide is the **operator go/no-go checklist** for migrating a project to
the Git-backed state-branch workflow. Read it before running any migration
commands.

For the full migration procedure, see
[`docs/state-branch-migration.md`](state-branch-migration.md).

---

## Overview

Migrating to a state branch moves task state from your default code branch
(`main`) to a dedicated orphan branch (`oompah/state/<project-id>`). This
eliminates routine task-metadata commits from your code history.

The migration is staged:

| Stage | What happens | Rollback? |
|---|---|---|
| **A** (shadow write) | State branch created; writes go to both branches. | ✅ Lossless |
| **B** (cutover) | Writes go to state branch only; task files on `main` kept as snapshot. | ✅ With recovery commit |
| **C** (cleanup, optional) | Task files removed from `main`. | ⚠️ Requires restore from state branch |

**Stop at Stage B** unless you have completed the recommended 30-day soak
window and are confident that rollback to Stage A is not required.

---

## Preflight Checklist

Run through this list **before** issuing any migration command.

### Environment

- [ ] oompah version ≥ 1.2.0 installed (`oompah --version`)
- [ ] `GITHUB_TOKEN` in `.env` has `repo` scope (can push branches)
- [ ] `oompah admin --help` shows the `migrate-state-branch` subcommand
- [ ] No active agent sessions on this project (check dashboard or `GET /api/v1/state`)

### Repository health

- [ ] `git -C <managed-checkout> status --porcelain` produces no output
- [ ] `git -C <managed-checkout> log --oneline origin/main..HEAD` produces no output
  (local checkout is not ahead of origin)
- [ ] No pending git rebase or merge in progress
  (`test -f <checkout>/.git/MERGE_HEAD` and `test -f <checkout>/.git/rebase-merge/` are false)

### Task data health

- [ ] `oompah admin validate-state-branch <project-id>` reports all checks PASS
- [ ] No duplicate task IDs (validation check: "no duplicate task IDs: PASS")
- [ ] No corrupt YAML front matter (validation check: "task files have valid YAML: PASS")

### Branch protection

- [ ] GitHub repository → Settings → Branches: the `oompah/state/*` pattern
  is allowed to be pushed directly (no PR required, no CI gate).
- [ ] `oompah admin validate-state-branch <project-id>` reports
  "service account can push: PASS" and "branch protection allows push: PASS".

### Timing

- [ ] No planned git repository migrations or GitHub maintenance windows in the
  next 48 hours.
- [ ] Avoid migrating during a release freeze or active incident.

---

## Validation Commands

Run these commands before each stage to confirm readiness.

### Pre-migration validation

```bash
# Full preflight check (prints pass/fail table):
oompah admin validate-state-branch <project-id>

# Quick git sanity checks:
git -C <managed-checkout> status --porcelain
git -C <managed-checkout> log --oneline origin/main..HEAD

# Confirm no duplicate task IDs:
oompah admin validate-state-branch <project-id> --check duplicate-ids

# Dry-run Stage A (shows what would happen without applying):
oompah admin migrate-state-branch <project-id> --stage A
```

### Post-Stage A validation (before advancing to Stage B)

```bash
# Check state branch was created and pushed:
git -C <managed-checkout> rev-parse oompah/state/<project-id>
git -C <managed-checkout> log --oneline oompah/state/<project-id> | head -5

# Check state endpoint for push failures (must be null):
curl -s http://localhost:8090/api/v1/state | jq '.state_branch["<project-id>"]'
# Expected: { "branch": "oompah/state/<project-id>", "push_failures": 0, "alert": null }

# Check shadow write sync (diff between main and state branch task files):
oompah admin state-branch-status <project-id> --check-sync

# Confirm task mutations are going to both branches (Stage A):
git -C <managed-checkout> log --oneline oompah/state/<project-id> | head -3
git -C <managed-checkout> log --oneline main | head -3
```

**Soak window criteria before Stage B:**
- ≥ 24 hours of Stage A operation with `push_failures == 0`
- Shadow sync check reports no divergence
- At least one agent cycle completed (task created, updated, closed)

### Post-Stage B validation

```bash
# Confirm task writes stopped going to main:
# Make a task update, then check that main did NOT receive a new commit:
git -C <managed-checkout> log --oneline main | head -5

# Confirm state branch received the task commit:
git -C <managed-checkout> log --oneline oompah/state/<project-id> | head -5

# Run the E2E regression test:
python -m pytest tests/test_state_branch_e2e.py -v -k "regression"

# Full state-branch test suite:
python -m pytest tests/test_state_branch_e2e.py tests/test_state_branch_migration.py \
    tests/test_checkpoint_coalescing.py -v
```

### Full test suite (required before closing the migration task)

```bash
make test
```

---

## Rollback Criteria

Roll back immediately if any of the following conditions appear:

### Mandatory rollback (data risk)

| Condition | Stage | Action |
|---|---|---|
| `push_failures > 0` for ≥ 10 minutes with no recovery | A or B | Roll back immediately; investigate token/network |
| Task data is readable on state branch but NOT on main after Stage B | B | Do NOT run Stage C; roll back to Stage A |
| `oompah admin state-branch-status --check-sync` reports divergence | A | Investigate before advancing; roll back if divergence grows |
| Any agent reports "state branch does not exist" error | A or B | Roll back; state branch was deleted or unreachable |

### Precautionary rollback

| Condition | Stage | Action |
|---|---|---|
| Push retry count (`push_failures`) climbs steadily | A or B | Roll back; investigate root cause before re-migrating |
| Dashboard shows tasks that should have moved status are stuck | B | Verify state branch is healthy; roll back if reads are broken |
| CI begins failing on PRs that only change `.oompah/tasks/` | A | Shadow writes are not fully suppressed; roll back and investigate |
| GitHub token expired during Stage A soak window | A | Refresh token, validate push access, re-run Stage A |

### Do NOT roll back for these (expected behaviors)

- `oompah/tasks/` files are still visible on `main` after Stage B — this is the
  rollback snapshot; they will not receive new commits.
- State branch commit timestamps are close together — this is checkpoint
  coalescing working correctly.
- State branch has more commits than `main` — expected; all task mutations now
  land there.

---

## Staged Production Rollout Recommendation

For organisations running multiple oompah-managed projects, we recommend the
following staged rollout:

### Phase 0: Tooling readiness (week -1)

1. Upgrade oompah to ≥ 1.2.0 on all service hosts.
2. Run `make test` on the service — confirm all state-branch tests pass.
3. Add `oompah/state/*` to branch protection exclusions in all managed repositories.
4. Create a monitoring alert for `push_failures > 0` sustained > 5 minutes.

### Phase 1: Canary project (week 1)

1. Choose a **low-traffic** project with ≤ 50 tasks and no active release work.
2. Run the full migration procedure:
   - `oompah admin validate-state-branch <canary-project-id>`
   - `oompah admin migrate-state-branch <canary-project-id> --stage A --confirm`
   - Soak for ≥ 24 hours; monitor `push_failures`.
   - `oompah admin migrate-state-branch <canary-project-id> --stage B --confirm`
   - Soak for ≥ 72 hours; monitor task operations.
3. Confirm `make test` still passes.
4. Confirm task operations (create, update, comment, dependency) work normally.
5. Confirm code commits on `main` no longer include `.oompah/tasks/` diffs in PRs.

**Go/No-Go for Phase 2:** all Phase 1 validation checks pass with zero push
failures and zero task read errors after 72 hours.

### Phase 2: Low-risk projects (week 2–3)

1. Migrate projects that are in maintenance mode or have fewer than 20 open tasks.
2. Stagger migrations: one project per day, with 24-hour soak before the next.
3. After each migration, run:
   ```bash
   python -m pytest tests/test_state_branch_e2e.py -v
   ```
4. Document any deviations from expected behavior as follow-up tasks.

**Go/No-Go for Phase 3:** zero rollbacks in Phase 2; all validation commands
pass for all migrated projects.

### Phase 3: Active projects (week 3–4)

1. Migrate high-traffic projects during a low-activity window (weekend, post-release).
2. Coordinate with agents — notify them that the migration is happening so they
   don't start long sessions immediately before Stage B.
3. Run validation immediately after Stage B:
   ```bash
   oompah admin state-branch-status <project-id> --check-sync
   curl -s http://localhost:8090/api/v1/state | jq '.state_branch["<project-id>"]'
   ```
4. Monitor for 30 days before proceeding to Stage C (cleanup).

### Phase 4: Stage C cleanup (month 2+)

Run Stage C only after:

- 30-day soak window post-Stage B for every project.
- Confirmed that no rollback was needed in any phase.
- Verified that `git log --oneline main | grep -c "oompah task"` returns 0
  (no new task commits on main since Stage B).
- Operators understand that Stage C is irreversible without restoring from git
  history.

```bash
# Stage C for a single project (irreversible):
git -C <managed-checkout> checkout main
oompah admin migrate-state-branch <project-id> --stage C --confirm
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────────┐
│  STATE BRANCH MIGRATION — OPERATOR QUICK REFERENCE                 │
├──────────────────────┬──────────────────────────────────────────────┤
│ Validate             │ oompah admin validate-state-branch <id>      │
│ Stage A (dry-run)    │ oompah admin migrate-state-branch <id> -s A  │
│ Stage A (apply)      │ oompah admin migrate-state-branch <id> -s A --confirm │
│ Stage B (apply)      │ oompah admin migrate-state-branch <id> -s B --confirm │
│ Stage C (apply)      │ oompah admin migrate-state-branch <id> -s C --confirm │
│ Rollback             │ oompah admin migrate-state-branch <id> --rollback --confirm │
│ Status               │ oompah admin state-branch-status <id>        │
│ Sync check           │ oompah admin state-branch-status <id> --check-sync │
│ Health endpoint      │ curl .../api/v1/state | jq .state_branch     │
│ Run E2E tests        │ make test (or pytest tests/test_state_branch_e2e.py) │
├──────────────────────┼──────────────────────────────────────────────┤
│ Rollback Stage A     │ Lossless — all writes were shadow-duplicated │
│ Rollback Stage B     │ Copies task state back from state branch      │
│ Rollback Stage C     │ Manual: git checkout state_branch -- .oompah/ │
└──────────────────────┴──────────────────────────────────────────────┘
```

---

## Automated Test Coverage

The migration workflow is validated by automated tests that run without an
external service or database:

| Test file | What is covered |
|---|---|
| `tests/test_state_branch_e2e.py` | End-to-end: new project, legacy migration, commit history regression, failed push, release branch isolation, orchestration continuity, checkpoint coalescing |
| `tests/test_state_branch_migration.py` | Stage A/B/C per-stage contracts, rollback, idempotency, concurrent writes |
| `tests/test_checkpoint_coalescing.py` | Debounce/max-delay timers, mandatory flush, concurrent writers |
| `tests/test_oompah_md_tracker_state_branch.py` | Tracker routing: state branch vs. default branch reads/writes |
| `tests/test_project_bootstrap_state_branch.py` | Bootstrap: orphan branch creation, seed from main |
| `tests/test_state_branch_project_config.py` | Project model fields, ProjectStore validation |

Run the full suite with:

```bash
make test
```

Or run only the state-branch tests:

```bash
python -m pytest tests/test_state_branch_e2e.py tests/test_state_branch_migration.py \
    tests/test_checkpoint_coalescing.py tests/test_oompah_md_tracker_state_branch.py \
    tests/test_project_bootstrap_state_branch.py tests/test_state_branch_project_config.py \
    -v
```

Expected result: all tests pass. The `make test` target will report any
regressions.
