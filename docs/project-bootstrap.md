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

## Dirty Worktree Safety

Oompah refuses to overwrite bootstrap-managed paths with uncommitted changes.
Commit or stash those changes first, then rerun the bootstrap apply operation.
