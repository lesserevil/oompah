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
updated_at: '2026-07-30T18:28:45.484451Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
