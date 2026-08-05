---
id: OOMPAH-828
type: bug
status: Open
priority: 1
title: Treat applied Archived audit results as final lifecycle no-ops
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:24:20.492002Z'
updated_at: '2026-08-05T18:17:50.123031Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 87becaec0c8737f6d1f62cf3a5548d643724ff146f5b3c463e1e379737672048
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 86df41dc-1fd2-4608-ba37-918dc86afad3
  claim_owner: 3a62b7a5-bbb7-4494-ae8d-738d99774e0d
  claimed_at: '2026-08-05T18:17:31.293451+00:00'
  claim_expires_at: '2026-08-05T18:47:31.293451+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 60058940-825d-43ff-958a-4bc87512c331
---
## Summary

Triggered by: OOMPAH-825

Live acceptance failure after deploying OOMPAH-825 on exact main 7978ec91b5532784c5dd6f18bc028954fd3696a9: lifecycle rows OOMPAH-452/453/455/456 are currently Archived and each detail API exposes a completed PASS Archived audit plus an applied Archived result intent, but the v2 lifecycle batch retries them as lifecycle_metadata_not_finalized. Root cause is deterministic: request_archived_audit intentionally fingerprints the mandatory archival disposition via compute_evidence_fingerprint(requirements_text=reason), while _lifecycle_terminal_authorities requires every terminal PASS fingerprint to equal compute_issue_evidence_fingerprint(current issue). Those two canonical domains cannot match, so production-shaped Archived authority is rejected even though its result was already applied. Implementation scope: add target-aware lifecycle finality. For a row whose current state is Archived, accept a completed PASS Archived record only when it is joined to an applied terminal result/retirement intent for the same project/task/audit/attempt/target/fingerprint and the tracker is already Archived; classify the legacy Merged repair row not_needed without any tracker mutation. Do not generalize disposition fingerprints to authorize Done/Merged writes, and continue rejecting incomplete, failed, mismatched, retired, quarantined, or unapplied evidence. Relevant code: archived_audit_requests.py fingerprint contract; terminal_audit_enforcement.py _lifecycle_terminal_authorities and non-Merged recovery; terminal metadata/result-intent schemas. Required tests: production request_archived_audit disposition fingerprint followed by PASS/applied Archived result and current Archived state; all four live-shaped rows converge exactly once with zero status writes; mismatched audit/attempt/fingerprint, applied=false, PASS without applied intent, non-Archived current state, quarantine, restart and retry races remain fail closed. Acceptance: OOMPAH-452/453/455/456 lifecycle rows become completed/not_needed, never mutate tracker status, do not rearm on restart, and lifecycle errors/action_required clear after deployment; focused enforcement/archive/coordinator tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

