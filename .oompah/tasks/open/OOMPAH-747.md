---
id: OOMPAH-747
type: bug
status: Open
priority: 1
title: Reuse trusted patch-equivalence evidence during epic auto-close
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T00:40:39.779884Z'
updated_at: '2026-08-04T00:41:20.924739Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1f9c08d70a8de1c46153484200e417859077a231cd898475c6e870568917d478
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 0d4bc758-85fc-4583-a60b-de641cbc224f
  claim_owner: b6e50576-eec3-4dce-bc89-fe685f70768e
  claimed_at: '2026-08-04T00:41:16.932481+00:00'
  claim_expires_at: '2026-08-04T01:11:16.932481+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Triggered by: EXOCOMP-130

Live reproduction: EXOCOMP-130 cannot auto-close because child EXOCOMP-148 records integrated SHA 8400a54a, while the current epic branch contains operator-verified rebased equivalents 61141cb8 and 9663f4b2. Epic review coverage recognizes this class through OOMPAH-519, but the earlier child-landing auto-close check still requires exact ancestry and reports two unlanded commits. Implementation scope: reuse the trusted patch-equivalence proof path for child landing and epic auto-close instead of maintaining a stricter duplicate resolver; when equivalence is proven, persist or consume canonical rebased integration evidence without weakening fail-closed behavior. Relevant code includes epic auto-close, _child_landing_evidence_block_reason, shared-epic review coverage, integration metadata reconciliation, and branch evidence helpers in oompah/orchestrator.py and project storage. Required tests: reproduce EXOCOMP-148 with changed commit SHAs after a direct epic rebase; cover multi-commit docs plus implementation patches, trusted and untrusted evidence, truly missing patches, deleted private refs, restart idempotence, and no regression to OOMPAH-519. Acceptance criteria: trusted patch-equivalent completed children unblock epic auto-close; unproven or ambiguous content remains blocked with precise evidence; one canonical proof implementation serves review coverage and auto-close.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

