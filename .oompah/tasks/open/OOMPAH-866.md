---
id: OOMPAH-866
type: bug
status: Open
priority: 1
title: Honor canonical child mappings after direct epic conflict rebases
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T20:39:34.818552Z'
updated_at: '2026-08-06T20:39:48.645499Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Fix the shared-epic landing gate regression reproduced by OOMPAH-740 PR 731: child OOMPAH-741 original head d3cc87e was authoritatively conflict-rebased to canonical 0321c898 while preserving current-main validation telemetry, but child validation recognizes only ancestry or git-cherry patch equivalence and reports both OOMPAH-741 and descendant OOMPAH-745 as unlanded. During direct epic rebase, persist durable per-affected-child old range to canonical range evidence with project, epic, child, base, source, target, and generation fencing; consume and validate that evidence in _child_has_durable_landing_evidence and _child_landing_evidence_block_reason without accepting stale, tampered, foreign-epic, tree-only, or unverified mappings. Preserve original SHA provenance and do not require child-ref rewrites. Relevant code: oompah/orchestrator.py direct rebase/canonical landing evidence and shared-child landing validators; existing tests/test_canonical_landing_evidence.py and epic landing suites. Required tests: conflict-resolved direct epic rebase maps the affected child; a descendant shared child does not inherit a false unlanded ancestor; exact unchanged commits still use normal evidence; restart persists mapping; stale/tampered/wrong project or epic evidence fails closed; OOMPAH-740 d3cc87e to 0321c898 scenario allows the epic PR only when every child range is accounted for. Acceptance: PR 731 topology passes landing validation without rewriting child branches, while any genuinely missing child work still blocks merge with an actionable identity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

