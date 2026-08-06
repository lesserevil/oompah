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

`alerts` remains a compatibility stream and may contain informational task
observations. Global warning banners must use `global_alerts`; an entry appears
there only when the decision or alert explicitly sets `action_required` and
has warning/critical/error severity. Queues, active repair, retry backoff,
audit rotation, pending CI, capacity waits, and transient authentication
observations therefore remain task-local or informational.

The projection is redacted before leaving the service. WebSocket state and
`full_sync` retain their existing epoch, sequence, and revision watermarks;
clients should request `full_sync` when a state revision gap is detected.
