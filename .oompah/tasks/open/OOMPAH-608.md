---
id: OOMPAH-608
type: bug
status: Open
priority: 1
title: Let auditors submit redacted verdicts for credential-safety tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T18:28:42.855708Z'
updated_at: '2026-07-30T18:33:14.522914Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ef12ac2904da500cd91278580a257ce30ddc47870aa7b46535ed56f7ecbd6334
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 3e21d1c9-33f3-4fe7-8228-2bfbf4c78a4e
  claim_owner: ac40770c-37a8-4b2c-b040-7a7ae948f467
  claimed_at: '2026-07-30T18:33:02.591697+00:00'
  claim_expires_at: '2026-07-30T19:03:02.591697+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 3e8c12b5-d36a-4b8a-b493-1c4f9ef29a4d
---
## Summary

Triggered by: OOMPAH-589

Implementation scope

Fix the completion-auditor result boundary so a credential-safety task can record a verdict without weakening secret protection. OOMPAH-589 completed its audit and attempted a PASS three times, but the verdict prose summarized intentionally documented credential-pattern examples and `submit_audit_result` rejected the entire result as matching a known credential pattern. The identical tool errors triggered the productivity stall and left the dependency root In Validation. Apply deterministic field-aware redaction or safe normalization to auditor result message/safe-evidence before persistence, and return actionable field-specific feedback when a value still cannot be made safe. Real credentials must remain rejected and must never enter logs, task comments, metadata, or retry prompts. Relevant areas include completion auditor tool validation, redaction helpers, audit result persistence/comments, and tool-error retry behavior.

Tests

Reproduce a PASS verdict for a task whose requirements and findings discuss credential syntax using inert examples; verify it is safely redacted and accepted. Verify actual bearer/API/password values remain rejected without echoing them, safe evidence is recursively handled, repeated submissions are idempotent, and three identical validation errors cannot strand an otherwise valid verdict. Run focused auditor contract/result/redaction/coordinator tests and make test.

Acceptance criteria

Credential-safety work can pass terminal audit without copying credential-shaped examples into durable state; genuine secrets remain fail-closed and non-observable; the auditor receives enough safe feedback to correct a result; OOMPAH-589 can complete a fresh audit rather than cycling on deterministic submission rejection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 18:28
---
Owner-approved liveness blocker discovered from OOMPAH-589 fresh audit attempt audit-a142ebf4b6d8. Let the oompah server implement it while the scheduler is healthy.
---
author: oompah
created: 2026-07-30 18:33
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 18:33
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
