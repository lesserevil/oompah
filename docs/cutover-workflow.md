# GitHub Issues Tracker Cutover Workflow

This document describes the operator workflow for cutting a managed project
over from Backlog.md to GitHub Issues, verifying the new tracker, and rolling
back if needed.

See `plans/github-issues-tracker-migration.md` for the full migration plan and
architecture background. After a project is cut over, use
`docs/github-issue-intake.md` for the operator workflow that moves newly filed
GitHub issues from `Proposed` through intake validation and requestor approval
to `Backlog`, then to owner-approved `Open` work.

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

### Step 3 — Configure tracker settings and record the cutover

In the Projects page, open the project edit form, set the tracker hub fields
and legacy Backlog flags, then save the project. After that, click **Cut over
to GitHub Issues** in the project card; the button sets
`tracker_kind=github_issues` and records `tracker_cutover_at`.

To do the same operation in one API call:

```bash
curl -X PATCH http://localhost:8000/api/v1/projects/<project-id> \
  -H 'Content-Type: application/json' \
  -d '{
    "tracker_kind": "github_issues",
    "tracker_owner": "lesserevil",
    "tracker_repo": "oompah-tasks",
    "tracker_cutover_at": "2026-06-10T00:00:00Z",
    "legacy_backlog_enabled": false,
    "legacy_backlog_dispatch": false,
    "paused": true
  }'
```

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tracker_kind` | string | `null` | Set to `github_issues` to route new tasks to GitHub Issues |
| `tracker_owner` | string | (global env) | GitHub owner/org of the central task hub |
| `tracker_repo` | string | (global env) | Repository name of the central task hub |
| `tracker_cutover_at` | ISO datetime string | omitted | Timestamp used as the cutover marker |
| `legacy_backlog_enabled` | bool | `false` | Keep existing Backlog.md tasks **visible** in the dashboard |
| `legacy_backlog_dispatch` | bool | `false` | Keep existing Backlog.md tasks **dispatchable** (requires `legacy_backlog_enabled=true`) |
| `paused` | bool | unchanged | Set `true` during verification to prevent dispatch |

The call:
1. Sets `tracker_kind = github_issues`.
2. Records `tracker_cutover_at` when supplied.
3. Optionally sets `tracker_owner` / `tracker_repo`.
4. Sets the legacy Backlog flags as specified.
5. Pauses the project when `paused=true` is supplied.
6. Updates the managed repository's `AGENTS.md` oompah task-tracking section
   so new agents use `oompah task ...` commands instead of Backlog.md.

Keep the project **paused** until the verification steps pass.

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

New GitHub issues filed directly by users enter the intake workflow before they
are dispatchable. They receive `oompah:status:proposed`, remain there while
oompah validates required information, advance to `Backlog` only after
requestor approval and an authorized status-label transition, and move to
`Open` only when a project owner accepts them for agent work. See
`docs/github-issue-intake.md` for the full filing and approval rules.

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
curl -X PATCH http://localhost:8000/api/v1/projects/<project-id> \
  -H 'Content-Type: application/json' \
  -d '{
    "tracker_kind": null,
    "tracker_cutover_at": null,
    "tracker_owner": null,
    "tracker_repo": null,
    "legacy_backlog_enabled": true,
    "legacy_backlog_dispatch": true,
    "paused": false
  }'
```

**What rollback does:**

1. Clears `tracker_kind` (project falls back to the global config, which
   defaults to Backlog.md).
2. Sets `legacy_backlog_enabled=true` and `legacy_backlog_dispatch=true` so
   existing Backlog.md tasks are both visible and dispatchable.
3. Clears `tracker_cutover_at`.
4. Unpauses the project when `"paused": false` is supplied.
5. Clears `tracker_owner` and `tracker_repo` when they are set to `null`.

**What rollback does NOT do:**

- GitHub Issues created after the cutover are **not** deleted. They remain in
  GitHub and can be managed there directly.
- Existing Backlog.md task files are never touched by the rollback.

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
files are committed after the `tracker_cutover_at` timestamp. This indicates an agent
ran with an old prompt that still references `backlog task create`. Check the
agent prompt and confirm the managed repository's `AGENTS.md` contains the
`OOMPAH GITHUB ISSUES INTEGRATION` section. If the cutover log reported an
`AGENTS.md` update failure, repair that file before unpausing dispatch.

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
