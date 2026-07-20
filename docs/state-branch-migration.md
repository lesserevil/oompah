# State Branch Migration Guide

This guide is for operators who manage an oompah service that uses the native
Markdown tracker (`tracker_kind=oompah_md`). It explains how to migrate an
existing project's task state from the project's default branch (`main`) to a
dedicated `oompah/state/<project-id>` branch.

If you have not read the internal design, you do not need to — this guide is
self-contained for operators. Engineers implementing the feature should read
`plans/state-branch-design.md` instead.

---

## Why migrate?

When oompah stores task state on your default branch, every task update (status
change, comment, metadata edit) creates a git commit on `main` and pushes it.
On busy projects this:

- **Pollutes your git history** with service metadata between code commits.
- **Slows your merge queue** because GitHub's merge queue builds CI against
  the exact tip of `main` — oompah commits shift that tip constantly.
- **Creates PR noise** when task metadata files appear in code diffs.

A state branch (`oompah/state/<project-id>`) isolates all task state from code
history entirely. Your `main` branch becomes code-only.

---

## Prerequisites

Before starting, confirm:

- You are running oompah **1.2.0 or later** (state branches require the new
  `state_branch_enabled` project field and the checkpoint coalescing engine).
- The `oompah admin` subcommand is available:
  ```bash
  oompah admin --help
  ```
- You have a GitHub personal access token (or `gh auth login` session) that
  can push to the project's repository — specifically, can create a new branch
  `oompah/state/<project-id>`.
- You have operator access to your oompah dashboard or service host.

---

## Step 1: Validate the project

Run the pre-migration validation check:

```bash
oompah admin validate-state-branch <project-id>
```

Replace `<project-id>` with the identifier shown in the oompah dashboard or
returned by `GET /api/v1/projects`. Example: `proj-14849f1b`.

The command prints a table like:

```
Check                           Result
default branch is clean         PASS
default branch up-to-date       PASS
no conflicting state branch     PASS
service account can push        PASS
branch protection allows push   PASS
task files have valid YAML      PASS (12 tasks, 0 corrupt)
no duplicate task IDs           PASS

All checks passed. Safe to migrate.
```

Fix every `FAIL` before proceeding. Common failures and fixes:

| Failure | Fix |
|---|---|
| `default branch not clean` | The managed checkout has uncommitted changes. Run `make restart` to trigger the service's automatic repo-heal pass. |
| `default branch not up-to-date` | Run `git -C <checkout> pull --ff-only origin main` manually, then restart. |
| `conflicting state branch (stale)` | The state branch exists but has not been pushed to in over 24 hours. Re-run the migration with `--force-reseed` to overwrite it from the current default branch. |
| `service account cannot push` | The GitHub token in `.env` does not have write access to the repository. Update `GITHUB_TOKEN` and restart. |
| `branch protection blocks push` | See the Branch Protection section below. |
| `task files have N corrupt stubs` | See the Corrupt Task Files section below. |

---

## Step 2: Configure branch protection

The state branch requires that your GitHub service account can push directly
without a pull request. This is different from your code branches, which should
require PR-based review.

In GitHub, go to your repository → **Settings → Branches** and check your
branch protection rules:

1. Confirm there is **no** rule matching `oompah/state/*` that requires a PR
   or passing CI.
2. If you have a rule that matches all branches (e.g. `**`), add an exclusion
   or a specific override for `oompah/state/*`:
   - Create a new rule with pattern `oompah/state/*`.
   - Enable **Restrict who can push** and add the service account (the GitHub
     user whose token is in `GITHUB_TOKEN`).
   - Leave all other protections unchecked.

After saving, re-run `oompah admin validate-state-branch <project-id>` to
confirm `branch protection allows push: PASS`.

---

## Step 3: Run Stage A migration (shadow write)

Stage A creates the state branch and starts writing task updates to it. For
safety, it also continues writing to the default branch (shadow write) so you
can roll back instantly without losing data.

```bash
oompah admin migrate-state-branch <project-id> --stage A --confirm
```

Without `--confirm`, the command does a dry-run and prints what would happen.
Add `--confirm` only when you are ready to apply the change.

What Stage A does:

1. Creates an orphan branch `oompah/state/<project-id>` with task state seeded
   from `.oompah/tasks/` on your default branch.
2. Pushes the new branch to `origin`.
3. Sets `state_branch_enabled=true` and `state_branch_shadow_write=true` on
   the project.
4. Restarts the tracker for this project (no service restart required).

You can verify Stage A is active:

```bash
curl -s http://localhost:8080/api/v1/state | jq '.state_branch'
```

Expected output:

```json
{
  "proj-14849f1b": {
    "branch": "oompah/state/proj-14849f1b",
    "last_push_at": "2026-07-20T16:05:00Z",
    "pending_mutations": 0,
    "push_failures": 0,
    "alert": null
  }
}
```

**Monitor this for at least 24 hours** before advancing to Stage B. Watch for:
- `push_failures > 0` — indicates a network or authentication problem.
- `alert` field populated — surface this in your monitoring.
- Differences between `.oompah/tasks/` on `main` and on the state branch (the
  shadow write sync check reports these automatically).

To check shadow write sync manually:

```bash
oompah admin state-branch-status <project-id> --check-sync
```

This compares the file trees and lists any divergence.

---

## Step 4: Run Stage B migration (stop writing to default branch)

Once Stage A has been stable for at least 24 hours with no push failures and
no sync divergence, advance to Stage B:

```bash
oompah admin migrate-state-branch <project-id> --stage B --confirm
```

What Stage B does:

1. Clears `state_branch_shadow_write`.
2. The tracker now reads and writes exclusively from/to the state branch.
3. The `.oompah/tasks/` files on the default branch are left in place as a
   rollback snapshot. They are not deleted.

After Stage B, your `main` branch will receive no new task-state commits. Verify
by watching the git log on `main` — task files should stop appearing after the
Stage B cutover commit.

---

## Step 5: Monitor

After Stage B, monitor for the recommended soak window (30 days minimum):

- Check `GET /api/v1/state` → `state_branch` for push failures or alerts daily.
- Confirm that `make test` still passes on your oompah service.
- Confirm that your merge queue throughput has improved (fewer out-of-date base
  branch rejections).

If you encounter problems, see the Troubleshooting section below or roll back
(see Rollback).

---

## Step 6 (optional): Clean up the default branch

After the soak window, you may delete the `.oompah/tasks/` files from your
default branch. This step is optional and irreversible without restoring from
git history.

Only do this if you are confident that rollback to the pre-migration state is
not required:

```bash
# Run from the managed checkout (OOMPAH_WORKSPACE_ROOT/<project-id>)
git checkout main
git rm -r .oompah/tasks/
git commit -m "Remove migrated oompah task state from main branch"
git push origin main
```

---

## Rollback

### Rollback from Stage A

Stage A shadow-writes every task update to both branches. Rollback is
lossless:

```bash
oompah admin migrate-state-branch <project-id> --rollback --confirm
```

This clears `state_branch_enabled` and `state_branch_shadow_write`. The
service reverts to reading and writing from the default branch immediately.
No data is lost because every write went to both branches during Stage A.

### Rollback from Stage B

Stage B stopped shadow-writing to the default branch. To roll back:

```bash
oompah admin migrate-state-branch <project-id> --rollback --confirm
```

This:
1. Copies `.oompah/tasks/` from the state branch HEAD back to the default
   branch.
2. Commits and pushes to the default branch.
3. Clears `state_branch_enabled`.
4. Restarts the tracker for this project.

The state branch is left intact. You can delete it manually after confirming
the rollback is stable:

```bash
git push origin --delete oompah/state/<project-id>
```

### Rollback from Stage C

Stage C deleted `.oompah/tasks/` from the default branch. To restore:

```bash
# Run from the managed checkout
git checkout main
git checkout oompah/state/<project-id> -- .oompah/
git commit -m "Restore oompah task state from state branch"
git push origin main
```

Then clear `state_branch_enabled` via the API or dashboard and restart.

---

## Troubleshooting

### `push_failures > 0` in the state endpoint

The service failed to push a checkpoint to the state branch. Common causes:

1. **Network issue** — Transient. The service retries automatically. Check
   `oompah.log` for `state_branch Push retry` lines.
2. **Token expired** — Update `GITHUB_TOKEN` in `.env` and run `make restart`.
3. **Branch protection blocked push** — Confirm the `oompah/state/*` protection
   rule allows the service account to push (see Step 2).
4. **Concurrent writer** — Another process pushed to the state branch. This
   should not happen in normal operation. Investigate and eliminate the rogue
   writer. The service will rebase and retry automatically, but the underlying
   cause must be fixed.

### State branch alert in dashboard

When `alert` is non-null in the `state_branch` block, the dashboard shows a
warning banner. The alert message identifies the cause. Resolve it and the
alert clears automatically on the next successful push.

If push has failed for more than 10 minutes, the service stops dispatching new
tasks for the affected project to prevent data loss. Existing running agents
are not killed.

### Task file appears corrupt after migration

If `oompah admin validate-state-branch <project-id>` reports corrupt task
files, repair them before migrating:

```bash
# Restore the file from git history
git -C <checkout> show HEAD:.oompah/tasks/<status>/<task-id>.md > \
    .oompah/tasks/<status>/<task-id>.md
```

Then re-run validation.

### Duplicate task IDs after migration

If the same task ID appears in two status directories (the existing
`OompahMarkdownTracker._read_records` warning case), the tracker uses the most
recently updated copy and ignores the stale one. To repair:

```bash
# Remove the stale copy
git -C <checkout> rm .oompah/tasks/<old-status>/<task-id>.md
git -C <checkout> commit -m "Remove stale duplicate of <task-id>"
git -C <checkout> push origin <default-branch>
```

Then re-run validation before migrating.

---

## New-project setup

Projects created after oompah 1.2.0 use the state branch by default. No
migration steps are needed — the bootstrap process creates the state branch
automatically during project creation.

To disable the state branch for a new project (not recommended):

```bash
# In .env, set the global default:
OOMPAH_STATE_BRANCH_ENABLED=false

# Or disable per-project via the API after creation:
curl -X PATCH http://localhost:8080/api/v1/projects/<project-id> \
     -H 'Content-Type: application/json' \
     -d '{"state_branch_enabled": false}'
```

---

## Tuning checkpoint intervals

The state branch coalesces multiple task mutations into a single git commit
before pushing. Two intervals control this:

| Variable | Default | Description |
|---|---|---|
| `OOMPAH_STATE_BRANCH_CHECKPOINT_DEBOUNCE_MS` | `5000` (5 s) | How long to wait for more mutations before committing. Mutations that arrive within this window are batched together. |
| `OOMPAH_STATE_BRANCH_CHECKPOINT_MAX_DELAY_MS` | `30000` (30 s) | The longest any mutation can sit unbatched before a forced commit. |

On projects with very high task activity (many parallel agents), reducing the
debounce to 2000 ms reduces the risk of losing the last few seconds of updates
if the service crashes. On projects with low activity, the defaults are fine.

Change these in `.env` and run `make graceful` to apply without a full restart.

Certain task events always commit immediately, regardless of these timers:
- A task moves to `Done`, `Merged`, or `Archived`.
- A task moves to `In Review` (PR URL must be committed before the poller
  tries to find it).
- An agent session exits.
- The service receives a shutdown signal (`SIGTERM`).
- A human operator changes a task via the API or dashboard.
