---
id: OOMPAH-289
type: task
status: Open
priority: 1
title: Harden focus triage and other model-only decisions against external instructions
parent: OOMPAH-285
children: []
blocked_by:
- OOMPAH-288
labels: []
assignee: null
created_at: '2026-07-21T14:51:55.684579Z'
updated_at: '2026-07-21T15:45:07.228365Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Update focus triage and every model-only decision path found in the threat model. Pass untrusted title/body/comment text only through the shared safe renderer, use structured output validation, and retain deterministic validation/fallbacks. Ensure injections cannot select arbitrary foci, alter priority, bypass approval, or create follow-up work.

Dependency: Render untrusted content in explicit prompt data boundaries.

Tests: mock model calls with injected content and malicious model output; verify invalid outputs are rejected, deterministic fallback is used, and no unauthorized side effect occurs.

Acceptance criteria: triage remains constrained to configured foci and server-side eligibility rules regardless of external text.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

