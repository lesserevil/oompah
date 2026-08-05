---
id: OOMPAH-842
type: task
status: Ready to Integrate
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
updated_at: '2026-08-05T22:07:58.407438Z'
work_branch: OOMPAH-842
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/725
review_number: '725'
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-842
  head_sha: c5c0f4029096f43c669840e3138e1317a1aa3361
  submitted_at: '2026-08-05T21:56:02.250758+00:00'
  updated_at: '2026-08-05T21:56:02.250758+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/725
oompah.review_number: '725'
oompah.work_branch: OOMPAH-842
---
## Summary

OOMPAH-841 fixes a live service-capacity deadlock on the OOMPAH-763 program branch: the native Codex npm shebang resolves node through the command validation shim and can lease the sole validation slot for the full provider session. This standalone deployment task must land the exact reviewed OOMPAH-841 production and regression changes directly on main before the larger epic closes.\n\nImplementation scope: after OOMPAH-841 is committed, independently reviewed, tested, and pushed, cherry-pick or faithfully apply only its native validation guard/Codex bootstrap changes and tests onto current origin/main. Resolve conflicts without bringing unrelated OOMPAH-763 work. Run the focused native guard and Codex backend tests plus the canonical full branch gate, integrate through the normal review path, gracefully restart with make restart, and verify the live validation_resources owner is an actual heavyweight command rather than a provider root. Confirm waiting auditors/workers advance and no provider bootstrap consumes capacity.\n\nRelevant files: oompah/native_validation_guard.py, oompah/acp_backends/codex.py, tests/test_native_validation_guard.py, tests/test_acp_codex_backend.py.\n\nAcceptance criteria: the exact OOMPAH-841 fix is deployed on main with no unrelated program commits; focused/full gates pass; a live Codex agent starts with owner_count unchanged until it launches a real heavyweight command; current waiters drain naturally; server remains healthy after graceful restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 20:46
---
Direct implementation claimed after OOMPAH-841 passed independent review and its 254-test focused gate. Cherry-picked the exact reviewed OOMPAH-841 commit onto current origin/main da53569a; the only conflict was the owner-claim test import block, resolved by preserving main's imports plus the new regression dependencies. Resulting OOMPAH-842 head is d0286b5b. git diff --check and production py_compile pass. Runtime gates are waiting behind the scheduler-owned OOMPAH-828/OOMPAH-841 validation lane.
---
author: oompah
created: 2026-08-05 21:56
---
Final reviewed head c5c0f4029096f43c669840e3138e1317a1aa3361 is pushed on OOMPAH-842, exactly one commit over current origin/main 2c7f609e. Focused native guard/Codex/owner/audit-health gate passed (252 tests); canonical full gate passed (15,721 passed, 7 skipped, 1 xfailed, exit 0); diff check, py_compile, and secret scan passed. Independent review found no blockers.
---
author: oompah
created: 2026-08-05 21:56
---
Deploy native provider bootstrap validation lease fix onto main
---
author: oompah
created: 2026-08-05 22:07
---
Branch quality gate passed for `c5c0f4029096f43c669840e3138e1317a1aa3361` using `make test` in 649.5s. Review creation may proceed.
---
<!-- COMMENTS:END -->
