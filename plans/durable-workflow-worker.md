# Durable workflow worker

`DurableWorkflowWorker` consumes exact-generation rows from the workflow-job
ledger. It runs one restart-safe saga per invocation:

```mermaid
flowchart LR
    A[Durable intent] --> B[Token-fenced lease]
    B --> C[Revalidate facts, generation, and head]
    C --> D[Inspect idempotency evidence]
    D -->|not applied| E[Apply external effect]
    D -->|already applied| F[Verify effect]
    E --> F
    F --> G[Persist checkpoint]
    G --> H[Request fenced task transition]
    H --> I[Persist outcome and complete]
```

Domain handlers implement one shared interface and declare whether they act on
the tracker, Git, a forge, or terminal audits. A handler must provide fresh
revalidation, an idempotency probe, an idempotent apply call, independent
verification, and an optional `TransitionIntent`. It receives a lease-aware
context and must call `check_interrupted()` inside long operations.

Every handler and transition call has a configured timeout. A heartbeat renews
the job lease while an operation is active. Checkpoints and completion require
the opaque current lease token; an expired or reclaimed worker therefore cannot
publish late state. Stale evidence supersedes the job before effects begin.
Retryable failures return the row to durable retry wait, while policy or
permanent failures exhaust it for explicit action-required classification.

The pre-effect inspection is also the crash-recovery mechanism. If a process
dies after an external service accepted an operation but before the worker
records it, the replacement worker observes the already-applied effect and
continues at verification. `TaskTransitionService` provides the equivalent
idempotent replay boundary for a transition accepted before acknowledgement.

Graceful drain stops new claims and waits for active work. Cooperative
interruption schedules the current row for durable retry at the next safe
boundary. Process termination can leave a running lease, which startup recovery
returns to the queue or exhausts according to its persisted attempt budget.
