# GitHub Issue Intake Workflow

This document describes how new GitHub issues enter an oompah-managed project
and advance from `Proposed` through intake validation to a dispatchable `Open`
state.

See `docs/cutover-workflow.md` for the operator steps to cut a project over
from Backlog.md to GitHub Issues, and `plans/github-issues-tracker-migration.md`
for full architecture background.

---

## Overview

oompah uses **GitHub Issues** as the canonical task tracker for managed
projects after the GitHub Issues cutover.  Anyone with access to the managed
repository can file a GitHub issue.  However, a freshly filed issue does not
immediately become eligible for agent dispatch — it must pass through the
intake workflow first.

```mermaid
flowchart TD
    A[User files GitHub issue] --> B[Issue receives oompah:status:proposed]
    B --> C{Intake validation}
    C -- Required info missing --> D[oompah comments + issue stays Proposed]
    C -- Info complete --> E{Requestor approval}
    E -- Scope approved --> F[Authorized actor applies oompah:status:backlog]
    F --> G[Issue moves to Backlog]
    G --> H{Owner review}
    H -- Accepted for work --> I[Owner applies oompah:status:open]
    I --> J[Issue is dispatchable; oompah picks it up]
    H -- Rejected / needs changes --> K[Issue moves to Needs Human or Proposed]
```

---

## Filing a GitHub Issue

### Where to file

File issues directly in the managed repository's GitHub Issues tab **or** in
the central oompah task hub repository (e.g. `lesserevil/oompah-tasks`),
depending on how the operator has configured the project.

### Required information

Every issue should include:

| Field | Required | Notes |
|-------|----------|-------|
| **Title** | Yes | Short, specific description of the work |
| **Description** | Recommended | Context, acceptance criteria, reproduction steps (bugs), or design rationale |
| **Issue type** | Recommended | `task`, `bug`, `feature`, `chore`, or `epic` — applied as a `type:*` label |
| **Priority** | Optional | `p0`–`p3` label, or set by oompah according to project defaults |
| **Target branch** | Optional | Required for release-pick or release-branch work |

Issues filed without a description will stay in `Proposed` until the requestor
adds the missing detail and an authorized actor advances them to `Backlog`.

### Issue templates

If the repository includes GitHub issue templates (`.github/ISSUE_TEMPLATE/`),
use the appropriate template to pre-fill the required fields.  oompah looks for
the `<!-- oompah:metadata ... -->` block in the issue body for structured
metadata — do not remove it if present.

---

## The Intake Workflow

### Step 1 — Proposed

When a new issue is opened, oompah's webhook handler receives the
`issues.opened` event and applies the `oompah:status:proposed` label.  The
issue is **not** yet visible to the dispatch queue.

`Proposed` signals that this issue has been seen but not yet reviewed by an
authorized project owner.

### Step 2 — Intake validation

oompah optionally comments on the new issue to confirm receipt and list any
missing required fields (e.g. no description, no issue type label, no target
branch for a release-pick request).

If required information is missing, the issue remains in `Proposed` with a
comment explaining what is needed.  The requestor should update the issue body
and reply to the oompah comment, then re-request advancement.

### Step 3 — Requestor approval

Once intake is complete, the requestor must approve the proposed scope before
the issue can leave `Proposed`. Approval may be a GitHub comment, a checked
template field, or an oompah UI action, depending on the project configuration.
For GitHub comments, the explicit `/oompah approve` command is accepted, and a
clear requestor comment such as "I approve this. Please add it to the backlog."
is also treated as scope approval. Ambiguous comments such as "looks good" or
comments asking for changes do not satisfy requestor approval.

After requestor approval, an authorized actor applies the
`oompah:status:backlog` label to move the issue into the `Backlog` queue. If
the requestor is also an authorized actor, the approval and label transition can
happen in the same action.

**Who can apply status labels?**

Status label changes are restricted to authorized actors:

1. The **oompah bot** (configured via `OOMPAH_BOT_LOGIN`, defaults to `oompah`)
2. The **project's `tracker_owner`** (the GitHub login configured in the project)
3. Any login in **`project.status_label_authorized_logins`** (per-project
   allowlist configured by the operator)

Unauthorized status-label changes are automatically reverted by oompah, and
the issue receives an explanatory comment.

To add yourself to the authorized list, ask the project operator to add your
GitHub login to the project's `status_label_authorized_logins` setting.

### Step 4 — Backlog

Once the `oompah:status:backlog` label is applied by an authorized actor, the
issue appears in the oompah dashboard but is still **not dispatched** to an
agent.  `Backlog` is the holding state for reviewed work that has not yet been
prioritized for active development.

Project owners can use the oompah dashboard or `oompah task set-status` to
manage the backlog:

```bash
# Move an issue from Proposed to Backlog (if you are an authorized actor)
oompah task set-status owner/repo#123 Backlog

# View the current state of an issue
oompah task view owner/repo#123
```

### Step 5 — Open (dispatchable)

When the project owner is ready for oompah to work on the issue, they advance
it to `Open` by applying `oompah:status:open`:

```bash
oompah task set-status owner/repo#123 Open
```

Once `Open`, the issue enters the dispatch queue.  oompah will claim it during
the next orchestrator tick, assign it to an agent based on the issue's focus
labels and type, and begin work in an isolated git worktree.

---

## Status Reference

| Status | `oompah:status:*` label | Dispatchable | Description |
|--------|-------------------------|:------------:|-------------|
| Proposed | `oompah:status:proposed` | No | Newly filed; awaiting intake review |
| Backlog | `oompah:status:backlog` | No | Reviewed; not yet prioritized |
| Open | `oompah:status:open` | **Yes** | Ready for agent dispatch |
| In Progress | `oompah:status:in-progress` | — | Agent is actively working |
| In Review | `oompah:status:in-review` | — | PR is open; under review |
| Needs CI Fix | `oompah:status:needs-ci-fix` | **Yes** | Agent re-dispatched to fix CI |
| Needs Rebase | `oompah:status:needs-rebase` | **Yes** | Agent re-dispatched to rebase |
| Needs Answer | `oompah:status:needs-answer` | — | Agent is blocked, waiting for human input |
| Needs Human | `oompah:status:needs-human` | — | Requires human intervention; not dispatched |
| Done | `oompah:status:done` | — | Work complete; PR merged or closed |
| Merged | `oompah:status:merged` | — | PR merged into the target branch |
| Archived | `oompah:status:archived` | — | Permanently closed; not to be re-opened |

---

## Authorization Model

oompah guards all `oompah:status:*` label changes.  Any label change fired
through the GitHub webhook is checked against the project's authorized-actor
list.  Unauthorized changes are reverted within seconds of the webhook
delivery.

**Authorized actors** for status label changes:

1. **oompah bot** — identified by `OOMPAH_BOT_LOGIN` (default: `oompah`).
   This covers all lifecycle transitions performed by oompah itself (claim,
   merge, archive, reopen, etc.).

2. **Tracker owner** — the GitHub login stored in `project.tracker_owner`.
   In most deployments this is the organization or user that owns the task hub
   repository.

3. **Per-project allowlist** — `project.status_label_authorized_logins`.
   Project operators can add individual GitHub logins here to grant them the
   ability to advance issues through the intake flow and into the backlog.

To configure the allowlist, update the project via the oompah UI or API:

```bash
curl -X PATCH http://localhost:8000/api/v1/projects/<project-id> \
  -H 'Content-Type: application/json' \
  -d '{"status_label_authorized_logins": ["alice", "bob"]}'
```

---

## Operator Notes

### Configuring the initial status for new issues

When oompah creates an issue on behalf of an agent (e.g. `oompah task create`),
the initial status defaults to the first configured `active_state` (`Open`
unless otherwise configured).  Issues filed directly by users through GitHub's
interface will start without any `oompah:status:*` label until the webhook
handler applies `oompah:status:proposed`.

To enable automatic `Proposed` labeling for externally filed issues, ensure
the GitHub webhook for `issues` events is configured and the `OOMPAH_BOT_LOGIN`
credential has write access to apply labels on the task hub repository.

### Disabling the Proposed stage

Some projects prefer that authorized users file issues directly at `Backlog`
or `Open` without a `Proposed` review step.  This is supported — authorized
actors can apply any status label directly, bypassing `Proposed` entirely.
The `Proposed` stage is a convention enforced only when the project operator
uses it as part of their intake process.

### Legacy Backlog.md projects

For projects still using `Backlog.md` as the task tracker (i.e.
`tracker_kind` is not `github_issues`), this intake workflow does not apply.
Use the Backlog.md CLI to manage issue status for those projects.  See
`docs/cutover-workflow.md` to migrate a project to GitHub Issues.
