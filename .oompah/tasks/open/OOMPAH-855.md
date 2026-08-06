---
id: OOMPAH-855
type: task
status: Open
priority: null
title: Preserve auditor candidate eligibility across operator pause retirement
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-854
labels: []
assignee: null
created_at: '2026-08-06T06:52:17.206143Z'
updated_at: '2026-08-06T16:30:39.849128Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Live regression on OOMPAH-853 on 2026-08-06. A Done auditor using the second eligible candidate was retired by the global operator pause used to fence a duplicate implementation writer. The retirement was recorded as a consumed attempt. After resume, both configured candidates were considered attempted and the exact unchanged audit moved to Needs Human for no independent candidate. An owner override was required even though the exact-head gate had passed and the interrupted auditor reported no code defect. Implementation scope: classify scheduler pause and graceful quiesce retirement separately from provider, policy, verdict, transport, timeout, and operator-cancel failures; preserve or immediately requeue the same candidate eligibility when no structured verdict was committed; fence late output from the retired runtime; keep genuine policy denials and repeated provider failures consuming or rotating attempts as configured; make recovery idempotent across pause, resume, and restart. Relevant code includes orchestrator pause and worker retirement, auditor dispatch attempt persistence, terminal audit workflow recovery, and exhaustion classification. Required tests: barrier-pause an auditor before verdict, resume, and prove one retry without Needs Human or attempt-budget consumption; repeat across restart; cover pause after durable verdict finalization without duplicate apply; cover mixed first-candidate policy denial plus second-candidate pause; prove explicit owner cancellation and genuine policy or transport failure retain current semantics. Acceptance criteria: routine pause or graceful drain cannot turn an otherwise healthy unchanged audit into no-independent-candidate exhaustion; exact evidence and candidate independence remain fail-closed; focused pause, auditor lifecycle, durable workflow, and terminal-transition tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 16:30
---
Promoted for the systemic completion program with an explicit hard-start on OOMPAH-854. The pause-retirement eligibility repair depends on OOMPAH-854 durable pre-provider audit fencing and must dispatch from that accepted lineage, avoiding a second overlapping quiesce/restart implementation.
---
<!-- COMMENTS:END -->
