# Branch quality gates

Oompah separates fast specialist feedback from complete branch verification.
Agents run focused tests for the behavior they changed and directly affected
neighboring suites. When a standalone task or complete epic branch is ready
for a PR or MR, oompah runs one full quality gate before creating the review.

Configure the commands on the project:

- `test_command` is the fallback complete branch command.
- `test_command_full`, when present, is the complete branch command and takes
  precedence over `test_command`.

## Caching and reuse

The gate is keyed by repository, target branch, work branch, exact HEAD SHA,
and command. An outcome is reused for concurrent or later readiness checks of
that exact head, including after a service restart. This avoids repeatedly
running or commenting on the same failure. A new commit, rebase, target
branch, or command causes a new run.

**Important:** Passed results are always safely reused. Failed, timed_out, and
error results are cached but can be explicitly retried (see below).

## Explicit retry on unchanged head

When an integration row is explicitly retried from a blocked state (same head
SHA and branch), the quality gate cache is invalidated **only for that row's
failed, timed_out, or error results**. Passed results remain cached and are
reused. This allows operators and agents to force a fresh quality gate check
without requiring a new commit, while still benefiting from proven cached
passes.

Duplicate concurrent quality gates for the same row and head are prevented by
oompah's per-instance single-flight locking mechanism.

## Exact-head isolation

Before a non-cached command starts, oompah resolves and verifies the recorded
commit, then checks it out in a gate-owned detached worktree. The command runs
there, never in the reusable task or epic worktree. The detached worktree is
removed only after its process group exits, and its result remains attributable
to the recorded commit SHA.

Different head generations may run concurrently. A task rejection or reopen
cancels only the process group owned by the superseded generation; its result
cannot create a review, integration, or CI-fix state. Review creation also
rechecks the authoritative branch tip after the gate completes.

## Configuration and timeouts

Set the timeout in `.env`:

```dotenv
OOMPAH_QUALITY_GATE_TIMEOUT_SECONDS=3600
```

The check runs in oompah's maintenance lane, not on the scheduler event loop.
If it fails or times out, oompah does not create the PR or MR. It moves the
task or epic to `Needs CI Fix`, adds a concise diagnostic comment, and reruns
the gate after the repair produces a new branch head.

Projects without either command retain the prior behavior: review creation is
not blocked by a local full gate, and forge CI remains authoritative.
