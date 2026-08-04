---
id: OOMPAH-791
type: feature
status: Open
priority: 1
title: Cut epic and nested-epic rollup over to LandingFact-driven jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:17.853130Z'
updated_at: '2026-08-04T20:23:06.318660Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: fb3aa3abc582ec1af953ebc1e286b3a58b83eabb84d54e02ce3789f58c3182cb
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 3bd8d11b-1c0f-453a-b7eb-1dcff9cb55b1
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T20:22:51.457911+00:00'
  claim_expires_at: '2026-08-04T20:52:51.457911+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: ddc8845e-c594-4cd3-b909-15b857f238ad
---
## Summary

Migrate epic readiness, child landing verification, rollup review creation, nested target resolution, auto-close, terminal validation, rebase/repair, cleanup, and restart reconciliation to shared facts/decisions/jobs. Enforce acyclic containment; require normal child Done plus landing proof and nested epic landing on immediate parent; never make child eligibility depend on a parent status derived from that child. Preserve patch-equivalence and durable evidence after source pruning. Required real-Git scenarios: multi-level nested epics, parent open to main while child landed to parent, deleted refs, rebase, direct maintenance, new/reopened child during review creation, and OOMPAH-731/739/748. Acceptance: no parent-child proof cycle, all epic consumers share target/landing facts, and rollups converge without manual status overrides.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

