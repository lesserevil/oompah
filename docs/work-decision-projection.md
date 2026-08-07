# Work-decision projection

The state API and WebSocket state messages expose one redacted
`work_decision_projection` object. Its `items` entries are the canonical answer
for why a task is waiting or progressing. Board/detail issue payloads, running
and retry rows, and integration queue rows carry the matching entry as
`work_decision`.

The protected endpoint
`GET /api/v1/projects/{project_id}/tasks/{identifier}/work-decision` returns
`{"work_decision": ...}` for one task. Each projection includes the owner,
disposition, reason code and text, prerequisites, evidence revision, next
reassessment, recovery action, permitted actions, and `action_required`.

In `enforce` mode, the universal workflow controller is the only writer of
the public projection. In `shadow` mode, the shadow evaluator is the writer;
in `off` mode, the projection is unavailable. Reads are immutable cache reads:
an API or dashboard cache miss does not evaluate policy, invent an evidence
revision, or mutate controller metrics. A bounded scan exposes only the
decisions it evaluated while using the complete nonterminal task identity set
to remove deleted or lifecycle-final entries outside that scan window. Cached
decisions for omitted live tasks are hidden until a rotating future window
evaluates them. The shadow window cursor is versioned and persisted with the
availability cut, so reloads and repeated process restarts cannot continually
restart at the first sorted task. `Done` remains in
both controller and shadow scans because it can still require audit,
integration, or rollup work. If one project's tracker read fails, that
project's last decisions are retained internally but suppressed from public
reads until a successful read can prove which tasks are still live. Projection
metadata makes this explicit with
`availability` (`pending`, `ready`, `incomplete`, `partial`, `unavailable`, or
`disabled`), `complete`, `unavailable_projects`, `incomplete_projects`,
`incomplete_tasks`, and `incomplete_reason`. Failed-project and bounded-scan
availability are persisted without persisting policy or evidence payloads, so
a cold restart reports the project or task as unavailable/incomplete instead
of presenting an empty cache as healthy. Reconciliation truncation fails the
affected task decisions closed until a complete generation is durably
reconciled.

Tracker construction and reads are isolated per project. A construction or
read failure marks only that project unavailable; healthy project snapshots
continue through the same bounded pass.

Every controller and shadow sweep captures a monotonic `publication_epoch`
from the current configuration. Publication compares that epoch, producer
source, and producer generation atomically. This rejects an old sweep even if
configuration cycles back to the same mode while it is running (for example,
`enforce` to `shadow` to `enforce`).

A workflow reload constructs replacement dependencies before its authority
cut, durably records the pending cut, then swaps config, tracker, controller,
producer mode, and publication epoch together. If persistence fails, the old
public and durable cut remains authoritative and no reload notification is
sent. On success, the old projection is cleared and broadcast immediately, and
the dispatcher is awakened to populate the new epoch. Existing shadow
diagnostics remain available across the cut, but an older in-flight producer
cannot publish into it.

Producer effects participate in that publication transaction. Shadow sweeps
evaluate against an isolated registry and merge diagnostics/listener
notifications only after their public cut is accepted; the live shadow lock is
never held while acquiring publication authority. The authoritative decision is
carried separately from the size-bounded diagnostic, so even a 1024-byte
identity-only diagnostic cannot omit a task from the rotating decision
projection. Controller generations, fairness cursors, schedule cursors, jobs,
events, and metrics are staged in one SQLite `BEGIN IMMEDIATE` transaction.
Separate connections wait for that cut instead of having their commits erased
by a database restore. Controller and scheduler construction requires the same
durable store, preventing split commits. Commit and rollback failures fail the
publication closed and are reported explicitly. A failed state-file
publication or stale epoch emits no state-only notification.
The availability file is written before the SQLite commit and restored if that
commit fails; the in-memory projection becomes visible only after both succeed.
After a crash, startup deliberately does not reconstruct a source or policy
rows from availability metadata alone, so either side of that narrow commit
window recovers as pending/incomplete rather than as a false actionable cut.

`alerts` remains a compatibility stream and may contain informational task
observations. Global warning banners must use `global_alerts`; an entry appears
there only when the decision or alert explicitly sets `action_required` and
has warning/critical/error severity **and** supplies a concrete recovery
instruction. Queues, active repair, retry backoff,
audit rotation, pending CI, capacity waits, and transient authentication
observations therefore remain task-local or informational.

Queue age and backlog depth remain health metrics. They are not operator
alerts by themselves: queued and automatically retrying audit work stays
informational until a concrete recovery path is exhausted or another condition
identifies an action only an operator can perform.

Dedicated health panels follow the same rule: normal auditor rotation,
quality-gate execution, healthy repository hygiene, and sliding-window auth
observations do not reserve dashboard space. They appear globally only after
their owning recovery path produces an operator-actionable escalation.

The projection is redacted before leaving the service. WebSocket state and
`full_sync` retain their existing epoch, sequence, and revision watermarks;
clients should request `full_sync` when a state revision gap is detected. A
per-connection ordering cut serializes full-sync assembly with outgoing state
and issue messages. An update that races assembly is delivered after the
`full_sync` sequence, so the client replays it instead of hiding a newer
WorkDecision below the full-sync watermark.
State messages overlay decision revisions onto the currently rendered board;
the server also rejects detail-cache entries whose decision revision or
task-level availability no longer matches. Decision or bounded-scan
availability changes therefore refresh board cards and open detail panels even
when the tracker status and issue revision are otherwise unchanged.
Dashboard card caches and the open-detail refresh identity use
`project_id + identifier`, so equal task identifiers in different projects do
not share DOM state or redirect a refresh to the wrong project. Agent activity
WebSocket messages, activity API lookups, open/poll/refresh guards, and panel
identity use the same project-plus-identifier key (and `run_id` for sequential
runs); an activity lookup without `project_id` is rejected when the identifier
is ambiguous.

For every non-lifecycle-final card, the dashboard treats absence from a
source-bearing projection as `unavailable`; it never manufactures an
`available` or `pending` answer for that cache miss. Disabled projections,
bounded omissions, unavailable projects, and legacy/null project identities use
the same normalization and availability rules as board/detail REST payloads.

Per-project tracker construction is fenced by a reload generation. Factories
capture the matching immutable service configuration before doing slow setup,
and may populate the cache only if that generation is still current. A factory
that completes after reload cleared its generation is discarded and retried
against the new configuration.
