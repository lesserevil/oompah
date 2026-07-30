---
id: OOMPAH-592
type: feature
status: Backlog
priority: 1
title: Alert on terminal-audit launch failures and backlog age
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:28.755226Z'
updated_at: '2026-07-30T14:14:28.755226Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Extend terminal-audit health so the operator alert surface includes auditor launch/transport failure counts, oldest pending age, retry exhaustion, and stale In Validation records. Keep the existing enforcement/quarantine signal distinct but aggregate them into truthful project/service health. Alerts must clear only after underlying recovery and must not expose provider secrets or model output. Relevant files include terminal audit health/metrics, oompah/server.py state and alerts APIs, and dashboard rendering.

Tests

Cover empty backlog, fresh normal queue, aged backlog, repeated launch failures, exhausted candidates, successful recovery/clear, restart persistence, and redaction. Run focused API/dashboard tests and make test.

Acceptance criteria

A state with failed auditor launches or materially stale pending audits cannot show an empty healthy alert list; recovered normal operation clears the alert deterministically.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

