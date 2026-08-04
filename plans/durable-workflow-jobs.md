# Durable workflow jobs

`oompah.workflow_jobs.WorkflowJobStore` is the persistence boundary between a
pure `WorkDecision` and a worker performing its side effects. A job records one
action for one project, task, and evidence generation. Its idempotency key is
immutable: replaying identical work returns the existing row, while reusing the
key for different work is rejected.

Workers claim jobs in deterministic priority/availability/FIFO order. A claim
increments the attempt count and returns an opaque lease token. Renewals,
checkpoints, failures, and completion require that exact unexpired token. Once a
lease expires, is recovered, or is superseded, the old worker cannot mutate the
job. This is the fencing mechanism later saga handlers must use around every
external effect and transition request.

The active states are `queued`, `running`, and `retry_wait`. Terminal states are
`completed`, `exhausted`, `superseded`, and `cancelled`. Public enqueue never
revives a terminal row. A newer task generation terminally supersedes older
active jobs; bounded recovery returns abandoned or expired jobs to `queued`, or
marks them `exhausted` when their attempt budget is spent.

Job rows retain the expected facts revision and Git head, current phase,
checkpoint, failure category, retry deadline, and resulting transition. An
append-only event table preserves ownership and lifecycle history. SQLite
schema migration is versioned, claims use immediate transactions, and all scan
and recovery APIs enforce explicit bounds.

This store does not perform tracker, Git, forge, or auditor I/O. The resumable
worker will revalidate the recorded generation/evidence after claiming and use
`TaskTransitionService` for any resulting lifecycle mutation.
