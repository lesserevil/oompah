# Project Bootstrap

Oompah owns the managed-project bootstrap templates that used to live in the
separate `lesserevil/bootstrap` template repository. The bundled bootstrap
keeps baseline project files aligned with oompah's current native task tracker
workflow.

Projects bootstrapped with oompah 1.2.0 or later receive a dedicated **state
branch** (`oompah/state/<project-id>`) that isolates task-state commits from
code history. The state branch is created automatically during bootstrap — no
additional setup is required for new projects. See
[State Branch](#state-branch) below and `docs/state-branch-migration.md` for
background on existing projects.

## What Oompah Manages

Project bootstrap covers these files:

- `AGENTS.md`
- `Makefile`
- `.gitignore`
- `docs/README.md`
- `plans/README.md`
- `scripts/githooks/pre-commit`
- `.github/workflows/filtered-release-notes.yml`

`AGENTS.md` is special: when it already exists, oompah updates only the
oompah-managed task-tracking section and preserves the rest of the file.
That managed section distinguishes design plans from tracked implementation:
contributors may create or update documents under `plans/` without first
creating an oompah task. Tasks remain the canonical record once work is
accepted or needs status, ownership, dependencies, or orchestration.

Other files are only updated when they are missing or when they already carry
an oompah bootstrap marker. Existing project-owned files without that marker
are reported as protected and left unchanged.

The release-notes workflow refreshes a published release with GitHub-generated
notes plus a filtered commit list. Commits whose changed paths are exclusively
under `.oompah/` are omitted. For a first release or an unusual history, run it
manually and provide the preceding tag.

## Local CLI

The default GitHub install includes the bootstrap CLI. It does not require the
server runtime.

```bash
oompah project-bootstrap status /path/to/repo
oompah project-bootstrap preview /path/to/repo
oompah project-bootstrap apply /path/to/repo
```

`apply` writes files but does not commit by default. Use `--commit` or `--push`
when you want the CLI to create and optionally push the update commit:

```bash
oompah project-bootstrap apply /path/to/repo --commit
oompah project-bootstrap apply /path/to/repo --push --branch main
```

`--push` implies `--commit`.

## Managed Project API

The service exposes matching managed-project endpoints:

```text
GET  /api/v1/projects/{project_id}/bootstrap/status
GET  /api/v1/projects/{project_id}/bootstrap/preview
POST /api/v1/projects/{project_id}/bootstrap/apply
```

The API apply path commits and pushes with the managed project's configured
git identity and default branch, matching the issue-template refresh workflow.

## State Branch

Every project bootstrapped by oompah 1.2.0+ receives a state branch named
`oompah/state/<project-id>`. This branch:

- Is an **orphan** — it shares no history with `main` or any code branch and
  can never be fast-forwarded into code history.
- Carries only ``.oompah/tasks/`` content — no source code.
- Receives all task-state commits so that your `main` branch remains code-only.

The bootstrap creates this branch automatically and sets
`state_branch_enabled: true` in the project configuration. To disable the state
branch for a new project (not recommended):

```bash
# Disable globally via .env:
OOMPAH_STATE_BRANCH_ENABLED=false

# Or disable per-project via the API after creation:
curl -X PATCH http://localhost:8080/api/v1/projects/<project-id> \
     -H 'Content-Type: application/json' \
     -d '{"state_branch_enabled": false}'
```

### Re-running bootstrap

Bootstrap is safe to re-run (`oompah project-bootstrap apply`). When the state
branch already exists, the state-branch step is skipped and existing task data
is never overwritten. File-template updates are applied without touching the
state branch.

### Required permissions

The service account used by oompah (the identity behind `GITHUB_TOKEN`) must
be able to **push directly** to `oompah/state/*` branches — no pull request
required. Configure a branch protection rule in GitHub:

1. Go to **Settings → Branches** in your repository.
2. Add a rule matching `oompah/state/*`.
3. Enable **Restrict who can push** and add the service account.
4. Leave all other protections unchecked (no required CI, no required reviews).

This rule does not affect your code branches (`main`, `release/*`, etc.).

### Verifying state-branch tracking

After bootstrap, confirm the state branch is active:

```bash
curl -s http://localhost:8080/api/v1/state | jq '.state_branch'
```

A healthy response looks like:

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

`push_failures > 0` or a non-null `alert` require investigation — see
`docs/state-branch-migration.md` → Troubleshooting.

### Checkpoint timing

State commits are coalesced before pushing to reduce remote round-trips. Two
`.env` variables control the window:

| Variable | Default | Description |
|---|---|---|
| `OOMPAH_STATE_BRANCH_CHECKPOINT_DEBOUNCE_MS` | `5000` | Wait this long after the last mutation before committing. |
| `OOMPAH_STATE_BRANCH_CHECKPOINT_MAX_DELAY_MS` | `30000` | Maximum time any mutation can wait before a forced commit. |

### Code branch vs state branch

The state branch (`oompah/state/<project-id>`) is intentionally invisible to
code workflows:

- **GitHub Actions** triggered on `push` to `main` do not fire for state
  commits — the `oompah/state/*` namespace is separate.
- **Release notes** generated by the bundled
  `.github/workflows/filtered-release-notes.yml` skip commits that touch only
  `.oompah/**`, so state-branch cherry-picks (if they occur) are omitted.
- **Pull requests** between code branches never include state-branch files
  because the state branch is an orphan with no shared ancestor.

## Repository Map

Newly bootstrapped projects that have a state branch (`state_branch_enabled=True`)
are eligible for the repository-map feature. The feature is **disabled by default**
for operator safety — no map is generated and no state-branch writes occur until
explicitly activated.

To enable, add the following to your `.env` after bootstrap:

```ini
OOMPAH_REPO_MAP_ENABLED=true
```

The repository map is stored on the project's state branch
(`oompah/state/<project-id>`) under `.oompah/repo-maps/`. No extra daemon,
database, or externally hosted service is required.

See [docs/repository-map.md](repository-map.md) for full configuration,
freshness, diagnostics, privacy/trust boundaries, and rebuild procedures.

### Conditions for automatic activation

The feature is enabled **only** when all of the following are true at dispatch
time:

1. `OOMPAH_REPO_MAP_ENABLED=true` is set in `.env`.
2. The project has a Git-backed state branch
   (`project.state_branch_enabled=True`).

Projects that were bootstrapped before state branches were introduced must be
migrated first. Run `oompah project-bootstrap apply` to create the state branch,
then enable the feature via the environment variable.

## GitLab Projects

This section covers bootstrap requirements and configuration specific to GitLab.com
and GitLab 17+ self-managed projects. Existing GitHub projects are **unaffected** —
no configuration changes are required unless you are adding a GitLab project.

### Minimum GitLab token scopes

When configuring a GitLab project, the `access_token` field must be set to a
GitLab personal access token (PAT) or project access token with at minimum the
**`api`** scope. This grants the privileges oompah needs to:

- Read and create issues and merge requests
- Read pipeline and CI status
- Create and manage project-level labels
- Create, reconcile, and delete project webhook hooks
- Push state-branch commits (via the GitLab repository API)

For self-managed GitLab 17+ instances, the equivalent project-level permissions
(at minimum **Developer** role for most operations, **Maintainer** for hook
creation) are required.

To set the token for a project:

```bash
curl -X PATCH http://localhost:8080/api/v1/projects/<project-id> \
  -H 'Content-Type: application/json' \
  -d '{"access_token": "<your-gitlab-token>"}'
```

Or configure it via the dashboard: **Projects → Settings → Access Token**.

> **Security:** The token is stored on the server and masked in all API
> responses (`***`). Never include the raw token in logs, config files committed
> to source control, or task comments.

### Webhook configuration (public HTTPS endpoint required)

GitLab delivers webhook events directly to an HTTPS endpoint that must be
publicly reachable from the GitLab instance. Unlike the GitHub integration
(which uses `gh webhook forward` via a local process), the GitLab webhook
endpoint is public.

**Required:** Set `OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL` in `.env` to the base URL
where oompah is reachable over HTTPS, for example:

```ini
OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL=https://oompah.example.com
```

GitLab will POST events to `<OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL>/api/v1/webhooks/gitlab`.

**HTTPS is required** — GitLab rejects webhook endpoints that do not use HTTPS.
If running locally during initial setup, expose oompah with a tunnel:

```bash
# Using ngrok:
ngrok http 8080
# Then set OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL=https://<random>.ngrok.io

# Using cloudflared:
cloudflare tunnel --url http://localhost:8080
```

If no public URL is available, oompah falls back to polling for project
activity. Set `OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL` to an empty string or leave it
unset to run in polling-only mode. Polling introduces higher latency (up to
`OOMPAH_POLL_INTERVAL_MS`, default 2 minutes).

### Webhook secret (security requirement)

Every GitLab project **must** have a `webhook_secret` configured. The webhook
endpoint fails closed: GitLab webhooks received for a project without a
configured secret are rejected with HTTP 401, and webhooks for unregistered
repositories are silently discarded.

Generate a high-entropy secret and configure it:

```bash
SECRET=$(openssl rand -hex 32)
curl -X PATCH http://localhost:8080/api/v1/projects/<project-id> \
  -H 'Content-Type: application/json' \
  -d "{\"webhook_secret\": \"$SECRET\"}"
```

The same secret value must be set in the GitLab project hook (oompah manages
this automatically when `OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL` is configured and
the token has Maintainer role).

### Auto-merge semantics

GitLab auto-merge uses `merge_when_pipeline_succeeds`. When oompah requests an
auto-merge on a merge request, it sets this flag via the GitLab API. The MR is
merged automatically once all required pipeline jobs pass.

If GitLab rejects the auto-merge request (because approvals are required or
policy is unmet), oompah retains the MR in open state and surfaces the reason
as an alert.

**Merge trains are not supported in v1.** Oompah uses ordinary auto-merge
(`merge_when_pipeline_succeeds`) only. If the target project uses merge trains,
oompah will request an ordinary auto-merge and GitLab will execute the MR
outside the train. To disable merge trains for a specific project, go to
**Settings → Merge Requests → Merge method** and disable "Merge Trains".

### State branch push access

The oompah service account must be able to push directly to `oompah/state/*`
branches without a merge request. This is required for the state branch feature.

If the project has branch protections that prevent direct pushes, add an
exception for the `oompah/state/*` pattern:

1. Go to **GitLab → Settings → Repository → Protected branches**.
2. Add a rule for `oompah/state/*` with **Allowed to push** set to the
   oompah service account or Developers.
3. Leave **Allowed to merge** unchecked (state branches are never merged).

### Self-managed GitLab

For self-managed GitLab 17+, set `forge_base_url` to the instance's canonical
HTTPS URL:

```bash
curl -X PATCH http://localhost:8080/api/v1/projects/<project-id> \
  -H 'Content-Type: application/json' \
  -d '{
    "forge_kind": "gitlab",
    "forge_base_url": "https://gitlab.example.com"
  }'
```

The `repo_url` host must match the `forge_base_url` host — oompah validates
this at project creation and update time.

### Bootstrap dry-run (readiness check)

Before running a full bootstrap against a GitLab project, run the readiness
check to validate all required capabilities:

```python
from oompah.project_bootstrap import check_gitlab_readiness

result = check_gitlab_readiness(
    forge_base_url="https://gitlab.com",       # or your self-managed URL
    token="glpat-...",                         # your GitLab PAT
    namespace="my-group",                      # GitLab namespace
    project_name="my-project",                 # GitLab project name
    webhook_public_url="https://oompah.example.com",
    dry_run=True,                              # no state mutations
)
print(result.summary())
```

The dry-run check validates:

| Capability | What is checked |
|---|---|
| `api_access` | Token authenticates and can call `/api/v4/user` |
| `label_create` | Token can list/create project labels (Developer role) |
| `issue_access` | Token can read project issues |
| `mr_access` | Token can read project merge requests |
| `pipeline_read` | Token can read CI pipeline results |
| `state_branch_push` | Token has Developer access level (push permission) |
| `webhook_url` | `OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL` is a valid HTTPS URL |
| `hook_create` | Token can list project hooks (Maintainer role) |
| `polling_fallback` | Token can list branches (polling available as fallback) |

When a capability fails, the output identifies the exact missing permission and
the remediation step. No state is modified in dry-run mode.

### Recovery procedures

**Token expired or revoked:**
- Create a new GitLab PAT with `api` scope.
- Update the project: `PATCH /api/v1/projects/<id>` with `{"access_token": "..."}`.
- Run the readiness check to confirm all capabilities are restored.

**Webhook hook missing or incorrect:**
- Oompah reconciles project hooks on startup and each maintenance tick.
- To force reconciliation: `make restart` or `POST /api/v1/orchestrator/restart`.
- If the hook cannot be created (Maintainer role missing), configure it manually
  in GitLab → Settings → Webhooks with the URL and token shown in the dashboard.

**State branch push rejected:**
- Check GitLab → Settings → Repository → Protected branches for a rule that
  blocks `oompah/state/*`.
- Add a push exception for the service account, or disable branch protection
  for the `oompah/state/*` pattern.

**Polling degraded (no webhooks):**
- Set `OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL` in `.env` and restart.
- Verify the URL is HTTPS and publicly reachable from the GitLab instance.
- If running behind a firewall, set up a tunnel (ngrok, cloudflared, etc.).

---

## Dirty Worktree Safety

Oompah refuses to overwrite bootstrap-managed paths with uncommitted changes.
Commit or stash those changes first, then rerun the bootstrap apply operation.
