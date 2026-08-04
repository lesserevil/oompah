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
updated_at: '2026-08-04T00:46:17.530608Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-736

Live reproduction: the 2026-08-04 stalled-task watchdog classified OOMPAH-736 and EXOCOMP-130 as human_blocked with the sole evidence that a recent comment contained an explicit question or human handoff. OOMPAH-736 already had merged PR 692, a passing full gate, and an implementation head on main; EXOCOMP-130 had a resolvable canonical epic branch and a technical terminal-audit resolver failure. The required Needs Human handoff syntax was mistaken for proof of a continuing human dependency, so the watchdog took no recovery action. Implementation scope: classify from current tracker, audit, branch, review, CI, and provider evidence before using comment wording; distinguish a required handoff comment from an unresolved human decision; recognize superseded questions and machine-remediable technical blockers; remain fail closed when evidence is ambiguous. Record the decisive evidence and why any question is still current. Relevant code is oompah/stalled_task_watchdog.py plus orchestrator evidence collection and maintenance telemetry. Required tests: merged PR plus stale handoff becomes actionable; missing audit branch with canonical ref is technical rather than human; genuinely unanswered product or authority question remains human_blocked; stale versus newer comments; provider failures; ambiguous SCM state; idempotent restart. Acceptance criteria: handoff wording alone can never prove human_blocked; stronger current evidence safely recovers or accurately classifies the task; genuine human decisions remain untouched.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

