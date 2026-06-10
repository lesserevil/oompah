# GitHub Issues Tracker Cutover Workflow

This document describes the operator workflow for cutting a managed project
over from Backlog.md to GitHub Issues, verifying the new tracker, and rolling
back if needed.

See `plans/github-issues-tracker-migration.md` for the full migration plan and
architecture background.

---

## Prerequisites

Before cutting over any project, complete the preparation steps described in
the migration plan:

1. Create the central GitHub task hub repository (e.g. `lesserevil/oompah-tasks`).
2. Enable GitHub Issues on the hub repository.
3. Create the required issue types, labels, and custom fields.
4. Install the oompah GitHub App on the hub and all managed code repositories.
5. Configure oompah with the GitHub App credentials (see `.env.example` for
   `OOMPAH_GITHUB_*` variables).
6. Verify oompah can create, update, comment on, and close a test issue in the
   hub repository.

---

## Per-Project Cutover Steps

### Step 1 — Pause the project

Open the **Projects** page in the oompah UI (`/projects-manage`) and click
**Pause** next to the project you want to cut over. This prevents the
orchestrator from dispatching new agents while the cutover is in progress.

Alternatively, via the API:

```bash
curl -X POST http://localhost:8000/api/v1/projects/<project-id>/pause
```

### Step 2 — Let running agents finish (or cancel them)

Check the dashboard for any agents currently running against this project. You
can either:

- **Wait** for them to complete naturally, or
- **Cancel** them by closing or setting the corresponding tasks to `Needs Human`
  through the oompah UI.

No new agents will start because the project is paused.

### Step 3 — Initiate the cutover

Click **Cut over to GitHub Issues** in the project card, or call the API:

```bash
curl -X POST http://localhost:8000/api/v1/projects/<project-id>/cutover \
  -H 'Content-Type: application/json' \
  -d '{
    "tracker_owner": "lesserevil",
    "tracker_repo": "oompah-tasks",
    "legacy_backlog_enabled": false,
    "legacy_backlog_dispatch": false
  }'
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tracker_owner` | string | (global env) | GitHub owner/org of the central task hub |
| `tracker_repo` | string | (global env) | Repository name of the central task hub |
| `legacy_backlog_enabled` | bool | `false` | Keep existing Backlog.md tasks **visible** in the dashboard |
| `legacy_backlog_dispatch` | bool | `false` | Keep existing Backlog.md tasks **dispatchable** (requires `legacy_backlog_enabled=true`) |

The call:
1. **Pauses** the project (if not already paused).
2. Sets `tracker_kind = github_issues`.
3. Records `cutover_at` (UTC ISO-8601 timestamp).
4. Optionally sets `tracker_owner` / `tracker_repo`.
5. Sets the legacy Backlog flags as specified.

The project remains **paused** after this call.

### Step 4 — Verify GitHub tracker connectivity

Run a source sync and confirm it completes without Backlog conflict repair:

```bash
# oompah logs should show: "Skipping Backlog compatibility check (github_issues)"
# and: "tracker_status: github_issues: ok"
```

### Step 5 — Create a test task and verify the full flow

Create a new task through the oompah UI or API and confirm it appears as a
GitHub Issue in `tracker_owner/tracker_repo`:

```bash
curl -X POST http://localhost:8000/api/v1/issues \
  -H 'Content-Type: application/json' \
  -d '{"project_id": "<project-id>", "title": "Cutover smoke test", "description": "Verify GitHub Issues tracker after cutover."}'
```

1. Confirm the issue appears in GitHub with the correct fields and labels.
2. Dispatch the test task (resume the project temporarily, let one agent run).
3. Verify the agent's status updates and comments appear in the GitHub issue.
4. Verify the PR is linked to the GitHub issue.
5. Close or archive the test task.

### Step 6 — Unpause the project

Once you are satisfied the GitHub tracker is working correctly:

```bash
curl -X POST http://localhost:8000/api/v1/projects/<project-id>/resume
```

Or click **Resume** in the Projects UI.

The project is now live on GitHub Issues. New tasks and follow-up tasks created
by agents will be GitHub Issues. Existing Backlog.md task files remain in the
git tree as historical artifacts.

---

## Legacy Backlog Tasks

Existing Backlog.md tasks have three paths after cutover:

| Option | Flags | Description |
|--------|-------|-------------|
| **Ignore** (default) | `legacy_backlog_enabled=false` | Old tasks are hidden and cannot dispatch. They remain on disk as historical files. |
| **Read-only** | `legacy_backlog_enabled=true`, `legacy_backlog_dispatch=false` | Old tasks appear in the dashboard but cannot dispatch. Useful for reference during transition. |
| **Keep dispatching** | `legacy_backlog_enabled=true`, `legacy_backlog_dispatch=true` | Old tasks are still dispatched. All *new* tasks and follow-ups go to GitHub Issues. |

To change the flags after cutover, use the PATCH API:

```bash
curl -X PATCH http://localhost:8000/api/v1/projects/<project-id> \
  -H 'Content-Type: application/json' \
  -d '{"legacy_backlog_enabled": true, "legacy_backlog_dispatch": true}'
```

---

## Rollback

If the cutover fails or you need to revert for any reason:

```bash
curl -X POST http://localhost:8000/api/v1/projects/<project-id>/rollback \
  -H 'Content-Type: application/json' \
  -d '{}'
```

**What rollback does:**

1. Clears `tracker_kind` (project falls back to the global config, which
   defaults to Backlog.md).
2. Sets `legacy_backlog_enabled=true` and `legacy_backlog_dispatch=true` so
   existing Backlog.md tasks are both visible and dispatchable.
3. Clears `cutover_at`.
4. Unpauses the project (pass `"keep_paused": true` to skip this).
5. Optionally clears `tracker_owner` and `tracker_repo` (default: yes; pass
   `"clear_tracker_owner": false` to retain them).

**What rollback does NOT do:**

- GitHub Issues created after the cutover are **not** deleted. They remain in
  GitHub and can be managed there directly.
- Existing Backlog.md task files are never touched by the rollback.

### Rollback parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keep_paused` | bool | `false` | Leave the project paused after rollback |
| `clear_tracker_owner` | bool | `true` | Clear `tracker_owner` and `tracker_repo` |

### UI rollback

In the Projects page, click **Rollback to Backlog** next to the project. A
confirmation dialog explains what will happen before proceeding.

---

## GitHub-Only Mode

Once all legacy Backlog tasks have reached a terminal state (Done, Merged, or
Archived):

1. Set `legacy_backlog_dispatch=false` and `legacy_backlog_enabled=false`:

   ```bash
   curl -X PATCH http://localhost:8000/api/v1/projects/<project-id> \
     -H 'Content-Type: application/json' \
     -d '{"legacy_backlog_enabled": false, "legacy_backlog_dispatch": false}'
   ```

2. The dashboard will no longer show Backlog.md tasks for this project.
3. Backlog.md files remain in git history. They can be pruned in a separate
   cleanup PR if the project owner wishes.

---

## Troubleshooting

**New Backlog.md task files appear after cutover**

The completion verifier and source sync will warn if new `backlog/tasks/*.md`
files are committed after the `cutover_at` timestamp. This indicates an agent
ran with an old prompt that still references `backlog task create`. Check the
agent prompt and ensure the tracker-neutral task tools are in scope for
GitHub-backed tasks.

**GitHub Issues tracker returns errors**

Check `OOMPAH_GITHUB_TOKEN` or `OOMPAH_GITHUB_APP_*` credentials in `.env`.
Run a manual connectivity check:

```bash
gh api repos/lesserevil/oompah-tasks/issues --jq '.[0].title'
```

If GitHub is unreachable, use rollback to restore Backlog.md dispatch while you
investigate.

**Agents not picking up GitHub Issues**

Ensure the project's `tracker_kind` is set to `github_issues` and the task hub
coordinates (`tracker_owner` / `tracker_repo`) match the repository where
oompah creates issues. Check that `legacy_backlog_enabled=false` is not causing
all visible tasks to be filtered out.
