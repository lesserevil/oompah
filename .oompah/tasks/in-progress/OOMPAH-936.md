---
id: OOMPAH-936
type: bug
status: In Progress
priority: 1
title: Suspend paused-project terminal audits consistently in health projections
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T07:23:37.669062Z'
updated_at: '2026-08-09T07:24:28.203097Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-935

Problem: ten authoritative pending terminal audits on intentionally paused Trickle and Exocomp projects are preserved correctly, but startup terminal-audit health counts them as stale/degraded while the periodic lane skips paused issues before observation and later reports zero. Persisted service state can therefore disagree with live health, and an intentional project pause appears as operator failure. Scope: retain paused-project audit records/jobs and enforcement discovery, but represent them as suspended/excluded from active backlog age and degradation; make startup, periodic, persisted, and API health projections use the same pause-aware model; expose bounded suspended_count and excluded project IDs without leaking details. Relevant code: oompah/orchestrator.py terminal audit scopes/startup/periodic scan, oompah/terminal_audit_health.py, state projection, and associated tests. Tests: startup with pending audits on paused/unpaused projects; periodic scan parity; restart preserves suspended obligations; resume makes the same jobs dispatchable and active without duplication; active unpaused stale audits still degrade. Acceptance: intentionally paused projects do not degrade service health or produce contradictory pending counts, their audits are never retired/lost, resuming restores normal audit eligibility, and focused/full gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

