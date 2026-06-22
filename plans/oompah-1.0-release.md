# Oompah 1.0 Release Plan

Status: planned

## Release Shape

Oompah 1.0 should be a GitHub-hosted release with a stable branch, tag, and
installation story. The release train uses:

- Release branch: `release/1.0`
- Draft release tag: `v1.0.0-draft`
- Final release tag: `v1.0.0`
- Package version: `1.0.0`

The release should not publish to PyPI. The supported install paths are GitHub
tag installs and GitHub Release wheel installs.

## Goals

- Make the native `.oompah` markdown tracker the default 1.0 task system.
- Keep optional GitHub Issues intake working for managed projects that accept
  customer or external issue reports.
- Ship an installable lightweight `oompah` CLI that does not require installing
  or configuring the full service runtime.
- Keep the service runtime installable for operators from a clone with the
  server extra.
- Provide a repeatable release branch, draft release, final release, and
  post-release verification process.
- Document the minimum operator and managed-project workflows needed to run 1.0
  without relying on historical Backlog.md or beads behavior.

## Non-Goals

- Publishing packages to PyPI.
- Replacing the current service architecture before 1.0.
- Adding a daemon manager or OS package for the service.
- Migrating historical Backlog.md or beads tasks.
- Redesigning the UI beyond release-blocking correctness and workflow clarity.

## Workstreams

### 1. Release Train and Packaging

Prepare the repository for a `release/1.0` branch, `v1.0.0-draft` test release,
and final `v1.0.0` release. The current release automation validates tags
strictly against `project.version`, so it must learn the draft tag convention
without weakening final release validation.

Acceptance criteria:

- CI runs on `release/*` branches.
- The release workflow accepts `v1.0.0-draft` for draft validation and
  `v1.0.0` for final validation.
- Draft tags produce GitHub draft or prerelease output as appropriate.
- Final tags require exact agreement with `project.version`.
- Release notes and tests use 1.0 examples.

### 2. CLI and API Contract

Lock the 1.0 behavior of the lightweight CLI and the API surface it depends on.
The CLI must remain installable without pulling the service runtime dependency
set into contributor machines.

Acceptance criteria:

- `oompah --help`, `oompah task --help`, and `oompah project-bootstrap --help`
  work from a wheel install.
- The CLI uses `OOMPAH_SERVER_URL` as the single server locator.
- The wheel contains all modules needed by the lightweight CLI.
- The server-only dependency set remains behind the server extra.
- Release smoke tests cover the CLI commands expected in managed-project
  `AGENTS.md` files.

### 3. Managed-Project Workflow Readiness

Validate that managed projects can use the native tracker and optional GitHub
Issues intake cleanly in 1.0.

Acceptance criteria:

- Native `.oompah` tasks are created only on the default branch.
- GitHub Issues intake creates internal native tasks in `proposed`.
- Closed external GitHub issues archive non-terminal internal tasks.
- Reopened external GitHub issues return their internal tasks to `proposed`.
- Decomposition happens only in native oompah tasks, not in GitHub Issues.
- Managed-project bootstrap status, preview, and apply flows work on active
  managed repos.

### 4. Operator and Project Documentation

Update the user-facing docs and managed-project instructions for the 1.0
workflow. The docs should not tell users to use Backlog.md or beads.

Acceptance criteria:

- 1.0 release docs explain the `release/1.0`, `v1.0.0-draft`, and `v1.0.0`
  workflow.
- Install docs explain GitHub tag and GitHub Release wheel installs.
- Operator docs explain how to run, restart, configure, and verify the service.
- Managed-project docs explain the native tracker and optional GitHub Issues
  intake flow.
- Project bootstrap templates generate current `AGENTS.md` instructions.

### 5. Release Execution and Verification

Run the release train end to end after the release-blocking work lands.

Acceptance criteria:

- `release/1.0` is cut from a clean `main`.
- The full test suite passes on the release branch.
- `v1.0.0-draft` is created and its artifacts are verified from GitHub.
- Any draft findings are fixed on `release/1.0` and merged back to `main`.
- `v1.0.0` is created only after draft verification passes.
- The final GitHub Release includes install commands and a concise changelog.
- Post-release smoke tests verify Git tag install, wheel install, CLI help, task
  command help, and project bootstrap help.

## Epic and Task Breakdown

### Epic A: Define and Harden the 1.0 Release Train

- A1. Update release docs, tests, and workflow examples to the 1.0 branch and
  tag convention.
- A2. Teach release validation to accept `v1.0.0-draft` while preserving strict
  final tag validation.
- A3. Add CI coverage for `release/*` branches.
- A4. Add a release branch cut checklist for `release/1.0`.

### Epic B: Lock the 1.0 CLI and Package Contract

- B1. Bump release-branch package metadata to `1.0.0`.
- B2. Expand release smoke tests to cover `oompah project-bootstrap --help`.
- B3. Verify the lightweight wheel contains the CLI modules but excludes server
  runtime dependency requirements.
- B4. Document the 1.0 CLI and API compatibility surface.

### Epic C: Validate Managed-Project Workflow Readiness

- C1. Audit native tracker state transitions for 1.0 readiness.
- C2. Audit GitHub Issues intake state reconciliation for closed and reopened
  external issues.
- C3. Validate decomposition boundaries so GitHub Issues do not explode into
  duplicate external issue graphs.
- C4. Validate project bootstrap status, preview, and apply flows against the
  current managed projects.

### Epic D: Finish 1.0 Operator and Project Docs

- D1. Refresh install and release docs for the GitHub-only 1.0 release.
- D2. Write the 1.0 service operator runbook.
- D3. Write the managed-project onboarding checklist.
- D4. Remove any remaining user-facing Backlog.md and beads instructions from
  current docs and bootstrap templates.

### Epic E: Execute and Verify the 1.0 Release

- E1. Cut `release/1.0` from a clean `main` and run the full quality gate.
- E2. Create and verify the `v1.0.0-draft` release.
- E3. Fix any draft-release findings and merge them back to `main`.
- E4. Create and verify the final `v1.0.0` release.
- E5. Run post-release install and managed-project bootstrap smoke checks.

## Dependency Order

1. Epic A must finish before the draft release can be attempted.
2. Epic B must finish before managed-project docs can claim the CLI install path
   is stable.
3. Epic C should finish before final docs are frozen.
4. Epic D should finish before `v1.0.0-draft`.
5. Epic E starts after Epics A through D are complete.

## Release Readiness Checklist

- No release-blocking tests are skipped or failing without an explicit documented
  reason.
- The service can restart cleanly from the documented command path.
- The UI shows native oompah tasks consistently across status columns.
- Existing managed projects have current bootstrap-generated instructions or a
  documented reason for drift.
- GitHub Issues intake has a reconciliation path for open, closed, and reopened
  external issues.
- Release artifacts can be installed on a clean machine using only GitHub URLs.
