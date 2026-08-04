# Task transition service

`oompah.task_transition_service` is the durable status-mutation boundary for
the unified workflow engine. It preserves current tracker and terminal-audit
behavior while supplying the missing compare-and-swap and restart contract.

Every mutation begins as an immutable `TransitionIntent`. Its project/task,
expected canonical status and authority version, requested status, actor and
authority class, reason code, idempotency key, originating durable job,
evidence generation, and exact head are hashed into one intent revision.
Reusing an idempotency key with different bytes is rejected.

The SQLite journal has three responsibilities:

- append the request and every processing phase without updates or deletes;
- atomically deduplicate `(project_id, idempotency_key)`;
- lease one transition per `(project_id, task_id)` and require recovery of an
  expired ambiguous owner before a different intent may proceed.

The authority version intentionally excludes generic tracker timestamps,
labels, prose, and comments. It changes only with lifecycle state,
implementation generation/head, delivery branches, or integration authority.
This prevents benign metadata churn from invalidating status ownership.

Nonterminal writes are verified by a fresh tracker read. A raised transport
error after the tracker applied the write is recorded as recovered, while a
failure before the effect remains retryable under the same idempotency key.
Terminal intents never write `Done`, `Merged`, or `Archived`; the coordinator
adapter fingerprints current evidence and stages the target through the
existing independent-audit state machine. `In Validation` is the verified
staging result.

Later migration tasks must construct intents from versioned `WorkflowFacts`
and route each production status call through this service. Direct-write
enforcement is deliberately deferred until all call sites have compatibility
coverage.
