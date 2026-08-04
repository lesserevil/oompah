# Pure work decision evaluator

`oompah.work_decision.evaluate_task(task, facts)` is the canonical answer to
what can advance a task. It is pure: the evaluator performs no tracker, Git,
forge, job-store, or clock I/O and writes no status. Its only time input is an
explicit value, defaulting to the immutable facts collection time.

Every result includes the task disposition, stable reason code, responsible
owner type, named unmet prerequisites, facts revision, bounded next
reassessment, permitted actions, durable jobs, optional recommended status,
and alert level. Serialization is stable and the complete result has its own
decision revision.

The evaluator centralizes dependency semantics. Hard-start dependencies gate
dispatch; finish-order dependencies wait until integration. Missing, stale,
malformed, and error observations schedule bounded evidence recovery instead
of becoming false negatives. Immediate-target landing is independent of
parent status, and lifecycle-final Merged/Archived work never auto-reopens.

Normal queues, capacity waits, leases, and retries produce `none` or `info`
presentation. A `warning` or `critical` result is structurally legal only
when the disposition is `action_required`; this prevents routine recovery
from filling the operator dashboard with false emergencies.
