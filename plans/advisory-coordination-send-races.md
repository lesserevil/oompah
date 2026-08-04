# Advisory coordination-send races

Status: implementation contract for OOMPAH-751.

Peer authorization is intentionally dynamic. `Orchestrator.coordination_peers`
derives same-project, non-terminal peers from the current task graph, lifecycle
states, and changed-path checkpoints. A worker may therefore observe a peer
and lose authorization before `coordination_send` revalidates the recipient.
`Ready to Integrate` and `In Review` are non-terminal: leaving the running set
does not revoke a peer that still qualifies through the graph or a durable
changed-path checkpoint. Live worktree paths can disappear with the running
entry. `Done`, `Merged`, and `Archived` are terminal and are excluded.

The send path must preserve these invariants:

- Revalidation remains fail-closed. A recipient that is no longer suggested is
  not persisted or live-delivered.
- A recipient-policy denial returns the same structured, non-disclosing,
  non-500 response whether the recipient became stale or was never authorized.
  It is not an assigned-task handoff failure, worker-token authentication
  failure, or auth-health degradation.
- The worker retains its capability for its own comment and submit operations;
  worker-exit reconciliation must not move successful work to `Needs Human`.
- Arbitrary recipients, cross-project recipients, wrong-task capabilities, and
  expired capabilities remain denied without target disclosure.
- A still-authorized recipient that is not running receives the durable inbox
  fallback. Repeating an authorized send with the same idempotency key remains
  idempotent; an unauthorized retry must not create a row.

The regression matrix should cover the following boundary transitions:

| Case | Expected result |
| --- | --- |
| Suggested peer removed before send | Structured policy denial; no handoff failure or auth-health warning |
| Recipient changes from `In Progress` to `Ready to Integrate` or `In Review`, and its peer relationship still qualifies | Authorization remains; durable message stored because the recipient is not running |
| Still-authorized recipient stops running | Durable message stored; no live-delivery requirement |
| Recipient becomes terminal (`Done`, `Merged`, or `Archived`) before send | Structured policy denial; no message stored |
| Arbitrary or cross-project recipient | Strict denial and no disclosure |
| Expired capability | Authentication failure; no mutation |
| Advisory denial followed by own comment and submit | Both own-task operations succeed; exit reconciliation preserves completion |
| Restart and idempotent retry | Durable state survives restart; authorized retry does not duplicate |

Relevant implementation and test surfaces are `oompah/server.py`,
`oompah/orchestrator.py`, `oompah/coordination.py`,
`oompah/auth_health.py`, `tests/test_task_handoff.py`,
`tests/test_server_coordination.py`, `tests/test_coordination.py`, and
`tests/test_auth_health.py`.
