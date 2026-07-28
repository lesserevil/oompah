# Branch quality gates

Oompah separates fast specialist feedback from complete branch verification.
Agents run focused tests for the behavior they changed and directly affected
neighboring suites. When a standalone task or complete epic branch is ready
for a PR or MR, oompah runs one full quality gate before creating the review.

Configure the commands on the project:

- `test_command` is the fallback complete branch command.
- `test_command_full`, when present, is the complete branch command and takes
  precedence over `test_command`.

The gate is keyed by repository, target branch, work branch, exact HEAD SHA,
and command. An outcome is reused for concurrent or later readiness checks of
that exact head, including after a service restart. This avoids repeatedly
running or commenting on the same failure. A new commit, rebase, target
branch, or command causes a new run.

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
