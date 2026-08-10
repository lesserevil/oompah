---
id: OOMPAH-988
type: bug
status: In Progress
priority: 1
title: Reuse exact branch gates after the accepted head lands and its branch is deleted
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T05:18:40.854524Z'
updated_at: '2026-08-10T05:19:02.387915Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression after deployed OOMPAH-980 on server revision 2dde7ad. OOMPAH-983 exact accepted head 2a10a77a32b2b38e11b78b3137e13d289dc866d9 has a durable passing make test gate in .oompah/quality_gates.json (169.47 seconds) and is contained in origin/main through merge commit 0b1b035c882ffc5f1fe411168b425f3eaf127bae. Its terminal Done audit nevertheless reran the complete suite (19,279 tests), and the following Merged audit launched a second complete suite. Root cause: Orchestrator._terminal_audit_quality_gate_evidence resolves issue_exact_head correctly after OOMPAH-980, but requires the mutable work branch to still resolve to that accepted head. Normal post-merge branch cleanup deletes the remote branch, so exact immutable gate evidence is rejected even though the accepted SHA is durably bound to the audit and contained in the target branch. OOMPAH-981 is another live post-landing audit exposed to the same failure. Implementation scope: add a narrow repository-backed post-integration authority path that accepts the exact persisted branch-gate result when the work branch is absent only if the audit target is a post-review terminal transition, the accepted head and immutable audit binding agree, and git proves the accepted head is contained in the authoritative target/default branch. Preserve the existing branch-head equality proof while a work branch exists. Never reuse for an advanced mismatching branch, missing/invalid accepted SHA, stale fingerprint/attempt, absent gate record, failed gate, unlanded/non-ancestor commit, unavailable target branch, or ambiguous repository state. Relevant code: oompah/orchestrator.py terminal-audit gate evidence and live reuse revalidation, terminal audit revision binding/dispatch context only if needed, and tests/test_quality_gate.py. Required tests: OOMPAH-983-shaped deleted branch plus exact accepted head contained in target reuses make test for Done and Merged; existing branch exact match still reuses; advanced branch remains fail-closed; deleted branch with non-ancestor remains full_gate_required; stale fingerprint/attempt and incompatible gate remain denied; live authority recheck preserves the same proof; no extra full-suite command launches. Acceptance: post-landing OOMPAH-983/OOMPAH-981-shaped audits reuse the exact authoritative gate without a redundant complete run, while every unlanded or ambiguous case remains fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

