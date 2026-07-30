---
id: OOMPAH-630
type: task
status: Backlog
priority: null
title: Fetch rollup targets before judging child landing evidence
parent: OOMPAH-584
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T23:37:58.090708Z'
updated_at: '2026-07-30T23:37:58.090708Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: eliminate the post-merge race where reconcile_merged_epic_children compares child branches against a stale local remote-tracking ref and demotes genuinely landed Done children to Needs Human. Before _child_landing_evidence_block_reason evaluates ancestry or patch equivalence, refresh the exact authoritative rollup target ref with a bounded non-interactive fetch, or otherwise use the merge event's authoritative target SHA. Fail closed on an actual fetch/containment error without mutating a Done child based solely on stale cached refs. Preserve redacted diagnostics and the existing runtime budget. Relevant code: oompah/orchestrator.py rollup landing-evidence helpers and merged-label reconciliation. Tests: reproduce a stale origin/<parent-epic> ref that does not contain the child while the remote target does; prove refresh recognizes direct ancestry and patch equivalence; cover fetch failure/timeouts, nested epics, and genuinely unlanded work. Acceptance criteria: a child head that is an ancestor of the just-merged target cannot be demoted; genuinely unlanded children still become Needs Human; focused epic-strategy tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

