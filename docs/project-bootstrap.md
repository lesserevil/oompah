# Project Bootstrap

Oompah owns the managed-project bootstrap templates that used to live in the
separate `lesserevil/bootstrap` template repository. The bundled bootstrap
keeps baseline project files aligned with oompah's current native task tracker
workflow.

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

## Dirty Worktree Safety

Oompah refuses to overwrite bootstrap-managed paths with uncommitted changes.
Commit or stash those changes first, then rerun the bootstrap apply operation.
