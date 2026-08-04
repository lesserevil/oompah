---
id: OOMPAH-779
type: task
status: In Progress
priority: 1
title: Run WorkDecision in shadow mode and expose divergence diagnostics
parent: OOMPAH-765
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-777
labels: []
assignee: null
created_at: '2026-08-04T13:58:55.460558Z'
updated_at: '2026-08-04T15:51:45.084048Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Integrate fact collection/evaluation as a no-mutation shadow path controlled by .env/.env.example OOMPAH_* modes. Compare WorkDecision with legacy dispatch, integration, audit, review, watchdog, and UI classifications; record structured divergences with task/evidence versions and expected owner, without global warning spam. Add a project/task diagnostic API returning current facts, decision, and legacy comparison with secret-safe evidence. Required tests: feature mode reload, zero side effects in shadow, divergence dedup/clearing, API auth/redaction, stale snapshot generations, and WebSocket/state visibility. Acceptance: production can soak shadow evaluation and every divergence is actionable and reproducible before enforcement.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

