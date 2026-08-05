---
id: OOMPAH-842
type: task
status: Open
priority: null
title: Bootstrap native validation guard provider fix onto main
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-841
labels: []
assignee: null
created_at: '2026-08-05T18:52:26.995790Z'
updated_at: '2026-08-05T18:52:40.896459Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

OOMPAH-841 fixes a live service-capacity deadlock on the OOMPAH-763 program branch: the native Codex npm shebang resolves node through the command validation shim and can lease the sole validation slot for the full provider session. This standalone deployment task must land the exact reviewed OOMPAH-841 production and regression changes directly on main before the larger epic closes.\n\nImplementation scope: after OOMPAH-841 is committed, independently reviewed, tested, and pushed, cherry-pick or faithfully apply only its native validation guard/Codex bootstrap changes and tests onto current origin/main. Resolve conflicts without bringing unrelated OOMPAH-763 work. Run the focused native guard and Codex backend tests plus the canonical full branch gate, integrate through the normal review path, gracefully restart with make restart, and verify the live validation_resources owner is an actual heavyweight command rather than a provider root. Confirm waiting auditors/workers advance and no provider bootstrap consumes capacity.\n\nRelevant files: oompah/native_validation_guard.py, oompah/acp_backends/codex.py, tests/test_native_validation_guard.py, tests/test_acp_codex_backend.py.\n\nAcceptance criteria: the exact OOMPAH-841 fix is deployed on main with no unrelated program commits; focused/full gates pass; a live Codex agent starts with owner_count unchanged until it launches a real heavyweight command; current waiters drain naturally; server remains healthy after graceful restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

