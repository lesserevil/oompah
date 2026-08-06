---
id: OOMPAH-784
type: task
status: Open
priority: 1
title: Add workflow liveness SLO metrics and evidence-backed recovery health
parent: OOMPAH-770
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-796
labels: []
assignee: null
created_at: '2026-08-04T13:59:04.299718Z'
updated_at: '2026-08-06T03:46:13.827834Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5404dc70da5f7e3380399fb9e43136f5867ac0014f98c08fe05d8ac977291778
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 61a1d622-ceaa-43b6-99ad-bd550c8de5e9
  claim_owner: 11468835-7c49-48df-a46d-b143af3a940a
  claimed_at: '2026-08-06T03:45:58.604011+00:00'
  claim_expires_at: '2026-08-06T04:15:58.604011+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 3ec9cb63-b4a2-4e0f-85e6-baf527364b4e
---
## Summary

Instrument time-to-owner/explanation for Open, Ready, In Validation, In Review, recovery, and post-restart reconstruction. Track decision age, reassessment lateness, lease/retry deadlines, recoveries, escalations, and unexplained divergences with bounded cardinality. Add health thresholds via OOMPAH_* .env configuration and expose project/global summaries. Required tests: fake-clock boundaries, resets on progress, no false overdue during active jobs, restart timestamp handling, cardinality bounds, and health/alert integration. Acceptance: configured SLO violations are measurable and attributable; healthy means every nonterminal task satisfies the liveness invariant, not merely that the server loop responds.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 03:19
---
Promoted from Backlog to Open after hard-start prerequisite OOMPAH-796 reached Done. Project is temporarily paused for the graceful cutover; dispatch normally on resume.
---
author: oompah
created: 2026-08-06 03:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
