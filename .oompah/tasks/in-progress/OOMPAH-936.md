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
updated_at: '2026-08-09T08:31:19.649550Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 07:40
---
Direct-owner implementation complete at clean pushed head 2e574619bea14021f537ab8c7c7f805e056d320d. Paused audit obligations remain durable but project as suspended/non-degrading across startup, periodic scans, persistence, restart, and resume; zero-capacity scans stay current and resume restores dispatch. Verification: 225 focused health/observability/enforcement tests + 601 audit-lane consumer tests passed; git diff --check passed. Awaiting combined protected-main integration with OOMPAH-935/OOMPAH-937.
---
author: oompah
created: 2026-08-09 08:31
---
Combined delivery is pushed at final head cafc100c4 on PR #750. Protected hosted CI is running the complete gate on Python 3.11, 3.12, and 3.13.
---
<!-- COMMENTS:END -->
