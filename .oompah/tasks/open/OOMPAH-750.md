---
id: OOMPAH-750
type: bug
status: Open
priority: 1
title: Make stalled-task watchdog prefer current evidence over handoff wording
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:46:06.960272Z'
updated_at: '2026-08-04T00:47:39.836567Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: de09fa5b7e244e1be1585a6fb3ce8f55415afaf2edb7900a917d67eaa2eca6ae
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 861a4621-a700-41ac-a705-0eb71f168daa
  claim_owner: b6e50576-eec3-4dce-bc89-fe685f70768e
  claimed_at: '2026-08-04T00:47:28.217551+00:00'
  claim_expires_at: '2026-08-04T01:17:28.217551+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 484d8670-f993-4d87-8fe9-874896cd1f26
---
## Summary

Triggered by: OOMPAH-736

Live reproduction: the 2026-08-04 stalled-task watchdog classified OOMPAH-736 and EXOCOMP-130 as human_blocked with the sole evidence that a recent comment contained an explicit question or human handoff. OOMPAH-736 already had merged PR 692, a passing full gate, and an implementation head on main; EXOCOMP-130 had a resolvable canonical epic branch and a technical terminal-audit resolver failure. The required Needs Human handoff syntax was mistaken for proof of a continuing human dependency, so the watchdog took no recovery action. Implementation scope: classify from current tracker, audit, branch, review, CI, and provider evidence before using comment wording; distinguish a required handoff comment from an unresolved human decision; recognize superseded questions and machine-remediable technical blockers; remain fail closed when evidence is ambiguous. Record the decisive evidence and why any question is still current. Relevant code is oompah/stalled_task_watchdog.py plus orchestrator evidence collection and maintenance telemetry. Required tests: merged PR plus stale handoff becomes actionable; missing audit branch with canonical ref is technical rather than human; genuinely unanswered product or authority question remains human_blocked; stale versus newer comments; provider failures; ambiguous SCM state; idempotent restart. Acceptance criteria: handoff wording alone can never prove human_blocked; stronger current evidence safely recovers or accurately classifies the task; genuine human decisions remain untouched.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 00:47
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 00:47
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
