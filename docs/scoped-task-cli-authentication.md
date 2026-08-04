# Scoped Task CLI Authentication

Oompah service-launched agents (Codex, opencode, Claude Code, and other ACP
sessions) authenticate to the tracker with a **scoped, short-lived task
capability**, not the operator's HTTP Basic credentials. This document is for
operators who need to understand what an agent process can do, verify it fails
closed when misconfigured, and diagnose a `401` or `403` from an agent that
should have been able to comment on or submit its own task.

> **Design goal.** A spawned worker must be able to complete the small
> tracker handoff mandated by `AGENTS.md` (read its task, post progress
> comments, coordinate with peers where advised, and submit its own task)
> **without** ever seeing an operator-shaped credential. The capability is
> issued per task, expires quickly, and is rejected for any other task,
> project, or action.

For internal design notes (why the mechanism exists, EXOCOMP-55 background,
and the alternative ACP `run_command` interceptor path used by in-process
sessions), see [`plans/focus-handoff-mutation-protocol.md`](../plans/focus-handoff-mutation-protocol.md).

## Terminology

- **Operator credentials** — the HTTP Basic username/password stored in
  `.htpasswd` and configured on clients via `OOMPAH_SERVER_USERNAME` +
  `OOMPAH_SERVER_PASSWORD_FILE`. Used by humans and by `make status` /
  `make restart` / `oompah task` invoked from an operator shell. See
  [`docs/authentication.md`](authentication.md).
- **Task capability** (also *task handoff token*) — an opaque, expiring
  token minted by the service just before it launches an agent worker.
  Scoped to exactly one project, one task identifier, and a fixed set of
  actions. Never appears in `.htpasswd` and never crosses to a different
  task.
- **Subprocess-backed agent** — Codex CLI (`openai-agents` Codex
  extension), opencode CLI, any ACP session that runs the agent as a
  separate process. These agents shell out to `oompah task` and rely on
  the capability being injected into their environment.
- **In-process ACP session** — a Claude Code / API agent hosted inside the
  oompah server. These sessions do not send an HTTP request at all when
  they run `oompah task …`; the ACP tool catalog intercepts the command
  and routes it directly to the tracker. See the `run_command` interceptor
  in `oompah/acp_tools.py`.

## What the agent receives

The orchestrator mints a capability with
[`issue_task_handoff_token`](../oompah/task_handoff.py) and injects two
environment variables into the agent subprocess before launch:

| Variable | Value | Notes |
|----------|-------|---|
| `OOMPAH_TASK_HANDOFF_TOKEN` | opaque URL-safe string (~32 random bytes) | The capability itself. Never log, echo, or copy this value into a commit or comment. |
| `OOMPAH_TASK_HANDOFF_PROJECT_ID` | project ID the capability is scoped to | Non-secret. The CLI uses it as the default `--project` when the caller omits one. |

At the same time, [`agent_environment()`](../oompah/client_auth.py) strips
`OOMPAH_SERVER_USERNAME`, `OOMPAH_SERVER_PASSWORD`, and
`OOMPAH_SERVER_PASSWORD_FILE` from the subprocess environment so an
operator's Basic credential can never be inherited by an agent that also
holds a capability. Both properties are enforced by the regression suites
in [`tests/test_task_handoff.py`](../tests/test_task_handoff.py) and
[`tests/test_acp_codex_backend.py`](../tests/test_acp_codex_backend.py).

When a capability is present, `oompah task` **refuses to resolve
operator credentials at all**. Broader task operations (`create`,
`child-create`, `set-dependency`, `remove-dependency`, `set-source`,
`remove-source`) exit non-zero with a clear message rather than falling
back to the Basic route.

## What the agent can do

The task-handoff endpoint (`POST /api/v1/task-handoff`) accepts exactly
these `action` values and revalidates project/task/action scope on every
call:

| Action | Purpose |
|--------|---------|
| `view` | Read the assigned task's detail and comments. |
| `comment` | Post a progress comment authored by `oompah`. |
| `set-status` | Change status; terminal transitions are queued for audit. |
| `submit` | Move the task to `Ready to Integrate` with git evidence. |
| `add-label` / `remove-label` | Manage focus-handoff and routing labels. |
| `coordination-peers` | List advisory coordination peers. |
| `coordination-inbox` | Read durable messages addressed to the task. |
| `coordination-send` | Send a durable message to a suggested peer. |
| `coordination-checkpoint` | Publish a checkpoint with changed paths. |

Anything else is rejected with **HTTP 403** by the endpoint even if the
capability is otherwise valid. The `oompah task` CLI applies the same
allowlist client-side before sending a request.

## What the agent cannot do

The capability is **not** a project-wide service account. Every request
is checked against the exact `(project_id, task_identifier, action)`
triple that was granted; a mismatch fails closed:

- **Missing / empty `X-Oompah-Task-Capability` header** → `401`
- **Token that never existed, or that expired** → `401`
- **Token scoped to a different project** → `403`
- **Token scoped to a different task in the same project** → `403`
- **Action the token was not granted** → `403`
- **Bearing the capability header on any general API route** (e.g.
  `GET /api/v1/state`) → the header is stripped by
  `_BasicAuthMiddleware`, so the route still requires operator Basic
  auth. Reusing the capability outside the handoff endpoint provides no
  authority at all.

Genuine failed operations are recorded on the grant via
`record_task_handoff_failure` and consumed by the orchestrator when the worker
exits — a worker whose handoff failed is held for a human rather than silently
retried. An advisory `coordination-send` recipient-policy denial is the
exception. The endpoint returns the same structured, non-disclosing denial
whether the peer became stale or was never authorized, without recording a
handoff failure. The worker can still comment on and submit its own task.

Spawned workers also receive the non-secret `OOMPAH_TASK_HANDOFF_TASK_ID`
assignment identifier. The endpoint uses it only for auth-health classification:
when it matches a live running entry carrying the presented capability and the
request targets a different task, a rejected read-only `view` is an
intentional policy event. The target is never resolved, so this applies even
when it is non-running or unknown. Authorization still fails closed. For
read-only peer inspection, use `oompah task coordinate peers <task-id>` or
`oompah task coordinate inbox <task-id>`.

### Advisory coordination-send races

Peer suggestions are dynamic: a peer can leave the suggested set between a
worker listing peers and sending a message when its graph relationship,
changed-path evidence, or lifecycle eligibility changes. The send must fail
closed for that recipient, without persisting or delivering the message, but
this expected policy result must not be treated as a task-handoff
authentication failure or a worker-exit failure. It must be a structured
non-500 response so the worker can continue its own comment and submission
workflow.

Leaving the running set is not itself a lifecycle disqualifier. `Ready to
Integrate` and `In Review` are non-terminal states, so a peer in either state
remains authorized while its graph or durable changed-path relationship still
qualifies it. Because that peer is no longer running, delivery uses the durable
inbox fallback. If live worktree paths were its only qualifying evidence, the
suggestion can disappear when that evidence does; a coordination checkpoint
makes changed-path evidence durable. `Done`, `Merged`, and `Archived` are
terminal and are excluded from suggestions.

This exception does not weaken scope enforcement. Arbitrary recipients,
cross-project recipients, expired or wrong-task capabilities, and mutations of
another task remain denied without disclosing whether the target exists. The
recipient check happens before durable storage: a denied send creates no row,
while an authorized retry with the same idempotency key returns the original
durable message.

## Live least-privilege probe

Run this from an operator shell (with operator credentials for reading
`view` from the same project) to confirm a freshly launched Codex worker
gets the intended authority and only the intended authority. It exercises
the same paths that OOMPAH-575's `TestHandoffTokenFailClosed` covers, but
against a running service.

### 0. Preconditions

- The service is running (`make status`).
- You have at least one task in a project where a Codex worker can be
  dispatched (`Open`, no unmet hard-start dependencies).
- You have operator credentials configured for the `oompah task` CLI:
  ```bash
  export OOMPAH_SERVER_USERNAME=operator
  export OOMPAH_SERVER_PASSWORD_FILE=/run/secrets/oompah-client-password
  ```

### 1. Launch a Codex worker

Dispatch through the normal path (either allow the orchestrator's tick to
pick the task up or trigger a specific run through the dashboard / API).
Confirm the launch logs show a Codex backend session for the assigned
`(project_id, task_identifier)`.

### 2. Verify the granted operations succeed

Observe the worker's task comments and status transitions. On a healthy
run you will see, in the assigned task only:

- A comment authored by `oompah` (the worker's own progress update).
- A status change or `focus-complete:<focus-name>` label indicating the
  worker completed its phase.
- Optionally, a `Ready to Integrate` transition when the worker submits.

If any of these operations return `401` in the worker log, the launch or
environment propagation is broken; **do not** paper over it by giving the
worker operator credentials. Instead, capture the log, file the finding
against the launch path, and add the failing case to
`tests/test_task_handoff.py` before resubmitting.

### 3. Verify the fail-closed cases

The following are performed against the live service using a token you
obtain from the running orchestrator's grant registry (for automated
probing) or by adding an assertion inside the worker itself. Because the
opaque token must never be printed to a log or comment, prefer the
existing regression suites rather than an ad-hoc CLI capture:

```bash
# Focused suites cover exactly these fail-closed cases.
uv run pytest tests/test_task_handoff.py
uv run pytest tests/test_acp_codex_backend.py -k "handoff or Handoff"
```

The relevant `test_task_handoff.py` classes are:

- `TestTaskHandoffGrantStore` — scope, expiry, and revoke behavior on the
  in-memory grant store.
- `TestTaskCliHandoff` — the CLI never falls back to operator
  credentials when a capability is present and never combines the two.
- `TestTaskScopeDirectPath` — the ACP `run_command` interceptor rejects
  cross-task or ungranted operations.
- `TestTaskHandoffEndpoint` — the endpoint rejects cross-project /
  cross-task tokens with `403`, and a capability header cannot bypass
  Basic auth on any other route.
- `TestAgentCredentialBoundary` — `agent_environment()` strips operator
  credentials before an agent subprocess inherits them.
- `TestFailedHandoffLifecycle` — a failed handoff is held for a human,
  not silently retried.

`test_acp_codex_backend.py` additionally verifies that the Codex
subscription-CLI subprocess receives `OOMPAH_TASK_HANDOFF_TOKEN` +
`OOMPAH_TASK_HANDOFF_PROJECT_ID` and does not receive the operator
credential variables. When OOMPAH-575's focused regression suites land
(`TestHandoffTokenFailClosed`, `TestCodexHandoffAuth`) they extend this
coverage with explicit fail-closed cases keyed to the `403` matrix
above.

Each case must pass:

- **Missing capability header** → endpoint returns `401`.
- **Unknown / expired token** → endpoint returns `401` (no information
  leak about whether the token was ever valid).
- **Cross-project token** → `403`.
- **Cross-task token in same project** → `403`.
- **Ungranted action** (e.g. `view` succeeds but `set-status` was not
  granted) → `403`.
- **General API route with a capability header** → `401`; the header is
  stripped before the router sees it.

### 4. Record only safe evidence

When you report the probe outcome (in a comment on the driving task or in
an incident write-up), record only these fields:

- ✅ Whether each action returned the expected status code.
- ✅ Task and project identifiers (public).
- ✅ Timestamps and worker identifiers (public).
- ❌ **Never** the value of `OOMPAH_TASK_HANDOFF_TOKEN` — not in a log,
  not in a screenshot, not in a comment, not in a commit.
- ❌ **Never** any operator username/password, even redacted.

The `_BasicAuthMiddleware` and `_http` helpers deliberately never echo
the `Authorization` header or the capability header; do not undo that by
copy-pasting a raw HTTP transcript.

## Troubleshooting

### The worker exits with `401` from `oompah task`

**Cause.** The subprocess did not receive `OOMPAH_TASK_HANDOFF_TOKEN`,
or received it empty. Because the CLI refuses to fall back to operator
credentials when a capability is expected, the fallback code path is
absent and the request goes out unauthenticated.

**Fix.**

1. Confirm the ACP backend session was constructed with both
   `task_handoff_token` and `project_id`
   (`oompah/acp_backends/codex.py` and `.../opencode.py`).
2. Confirm the orchestrator's `_issue_task_handoff_token` returned a
   non-empty token — a `None` result means the grant registry was not
   ready at launch time.
3. Reproduce the failure with the regression test that matches your
   launch path and extend that test if the coverage is missing.

Do **not** widen the CLI's fallback to operator credentials as a "fix";
that would break the least-privilege invariant.

### The worker exits with `403` on its own task

**Cause.** The capability was minted for a different task or with a
different action set than the worker attempted. The action allowlist is
in `oompah/server.py::api_task_handoff`; the granted set is in the
`allowed_actions=` argument passed to `issue_task_handoff_token` when the
orchestrator launches the worker.

**Fix.** Reconcile the two lists. If a legitimately needed action is
missing from the grant, extend the orchestrator's grant, not the
endpoint's allowlist alone.

### A cross-task or cross-project attempt succeeded

**Cause.** This is a regression — the endpoint or the CLI is not
revalidating scope on every call.

**Fix.** Run the regression suites listed above; they will fail. File a
security-labeled task and do not restart normal dispatch until the
cross-scope path is closed.

### The capability header leaked into an operator API request

**Cause.** A client bug — the header should only be sent to
`POST /api/v1/task-handoff`. The `_BasicAuthMiddleware` strips it before
any other route sees it, so the request will 401 rather than authorize,
but the leak still needs to be fixed at the source.

**Fix.** Audit the client that emitted the header. In the shipped CLI,
`_http` sets the header only when the caller passes an explicit
`task_capability=`; there is no path that inherits it into a generic
request.

## Environment reference

| Variable | Set by | Consumed by |
|----------|--------|---|
| `OOMPAH_TASK_HANDOFF_TOKEN` | orchestrator | subprocess-backed agents' `oompah task` CLI, sent via `X-Oompah-Task-Capability` header |
| `OOMPAH_TASK_HANDOFF_PROJECT_ID` | orchestrator | subprocess-backed agents' `oompah task` CLI, used as default `--project` |
| `OOMPAH_SERVER_USERNAME` | operator | operator CLI + Makefile lifecycle commands. **Never** inherited by an agent subprocess. |
| `OOMPAH_SERVER_PASSWORD` | operator | operator CLI (limited alternative). **Never** inherited by an agent subprocess. |
| `OOMPAH_SERVER_PASSWORD_FILE` | operator | operator CLI (preferred). **Never** inherited by an agent subprocess. |

The stripping of the three operator variables from every agent
subprocess is enforced by `agent_environment()` in
`oompah/client_auth.py`; regressions live in
`tests/test_task_handoff.py::TestAgentCredentialBoundary`.

## See also

- [`docs/authentication.md`](authentication.md) — operator HTTP Basic
  authentication (the `.htpasswd` path used by humans and Makefile
  targets).
- [`docs/cli-install.md`](cli-install.md) — installing the standalone
  task CLI and configuring operator credentials.
- [`plans/focus-handoff-mutation-protocol.md`](../plans/focus-handoff-mutation-protocol.md)
  — internal design notes for the ACP `run_command` interceptor and the
  EXOCOMP-55 background that led to the scoped capability.
- `oompah/task_handoff.py` — the capability registry and grant type.
- `oompah/server.py::api_task_handoff` — the endpoint that enforces
  scope on every call.
