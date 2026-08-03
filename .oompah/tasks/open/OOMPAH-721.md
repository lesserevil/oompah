---
id: OOMPAH-721
type: task
status: Open
priority: null
title: Do not escalate completed duplicate preflights as implementation work
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T14:39:16.938367Z'
updated_at: '2026-08-03T14:41:40.255712Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction (2026-08-03): automatically filed epic-staleness tasks EXOCOMP-240 and EXOCOMP-241 entered In Progress under Focus: Duplicate Investigator. EXOCOMP-241's screening run exited normally without closing the task, but the generic worker-exit path escalated it from standard to deep and relaunched the same Duplicate Investigator instead of recording the screening result and handing the still-active task to the rebase/merge-conflict focus. This regresses the two-stage behavior previously specified by OOMPAH-217 and wastes increasingly expensive agents on implementation work outside the duplicate-screening role.

Implementation scope:
- Route every model-backed duplicate-preflight exit through the dedicated screening completion path before generic retry/escalation logic, including auto-filed maintenance/rebase tasks and providers that return no structured duplicate verdict.
- A non-duplicate/indeterminate normal exit must atomically clear the preflight claim, persist a revision-aware screened result (or bounded retry only within the screening subsystem), return the task to Open, and dispatch a fresh implementation session with the appropriate rebase focus.
- A Duplicate Investigator must never execute the rebase or other implementation, and generic standard-to-deep escalation must never retain duplicate_preflight=true.
- Preserve confirmed-duplicate archival, changed-task fingerprint invalidation, crash retry limits, authority revocation, and concurrency accounting.

Required tests:
- Reproduce EXOCOMP-241: normal preflight exit without closing an auto-filed rebase task, then prove no generic escalation occurs and the next worker is a rebase specialist with duplicate_preflight=false.
- Cover missing/malformed structured verdicts, confirmed duplicates, changed fingerprints, provider failure, restart recovery, and exact running/preflight counters.
- Assert the duplicate prompt cannot perform implementation and task comments clearly distinguish screening from implementation handoff.
- Run focused duplicate-screening/orchestrator/maintenance suites and make test.

Acceptance criteria:
- EXOCOMP-240/241-style tasks cannot loop or escalate under Duplicate Investigator.
- Screening either archives a confirmed duplicate or hands an active task to a new correctly focused implementation agent exactly once.
- No stale preflight claim or duplicate running entry remains after handoff.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes
