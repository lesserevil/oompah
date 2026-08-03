# Automatic container-cycle repair

`oompah.container_cycle_repair.ContainerCycleRepairExecutor` is the execution
boundary for the container reachability cycle selected by the graph analyzer.
The analyzer remains read-only; the orchestrator supplies a persisted exact
plan containing the common authoritative container, prerequisite SHA closure,
dependent containers, and fenced private queue rows.

The executor fetches under the project Git lock, verifies every selected SHA is
a descendant of the current authoritative head and that the intervening
commits are in the declared closure, then pushes the parent with
`--force-with-lease`. Each dependent container is synchronized only from that
parent. Fast-forward children are updated directly; diverged children are
preflighted and merged in an isolated worktree. Conflicts and CAS races are
recorded per container, so successful peers can proceed without importing a
sibling head.

The service-state `container_cycle_repairs` journal is updated after each
durable parent or child push. Queue restoration uses a second exact-head CAS,
then reopens the tracker row and rewrites its integration metadata to `ready`.
Alerts are removed only after reachability, queue state, and tracker state have
all been confirmed. Re-running a plan uses remote refs as authority and is
therefore safe after a restart or repeated execution.

Set `OOMPAH_CONTAINER_CYCLE_REPAIR_ENABLED=false` in `.env` to retain the
diagnostic/fencing behavior while disabling the policy-authorized executor.
