---
id: OOMPAH-499
type: chore
status: In Progress
priority: 2
title: Remove exact duplicate tests and resolve shadowed definitions
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels: []
assignee: null
created_at: '2026-07-28T13:53:34.407060Z'
updated_at: '2026-07-28T16:38:49.852092Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 0f30f032-68f1-41ba-af34-df39a755ea45
oompah.work_branch: epic-OOMPAH-490
---
## Summary

Implementation scope

Remove proven one-off duplicates and resolve Python name shadowing in the test sources. Delete or merge the duplicate empty approval case in `tests/test_intake_approval.py`, shared-strategy assertion in `tests/test_epic_strategy.py`, empty-candidate validation in `tests/test_role_store.py`, no-policy shell assertion in `tests/test_authority_boundary.py`, exception-hierarchy copies in `tests/test_error_watcher.py`, and any equally exact clone confirmed by AST comparison. In `tests/test_label_auth.py`, remove the earlier duplicate `test_proposed` definitions. In `tests/test_orchestrator_merged.py`, compare both definitions of `TestProjectHasOpenReview` and `TestDispatchSerializationByProject`; merge any unique case into the surviving class, then remove the shadowed class bodies. In `tests/test_epic_strategy.py`, the two same-named dirty-worktree methods exercise different inputs, so rename or merge the intended unique `.oompah/tasks` case instead of blindly deleting it. Resolve the duplicate `_FakeProjectStore` helper in `tests/test_webhooks.py` with one unambiguous helper name.

Tests

Add a small AST-based test or repository check that fails when a module or class body defines the same test name twice. Run every changed file, then `--collect-only` to prove intended formerly shadowed cases are actually collected. Run `make test`.

Acceptance criteria

No test module contains shadowed test classes/methods, no unique intended case remains dead, the named exact duplicates are removed, and the duplicate-name guard produces an actionable file, line, scope, and symbol on failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 16:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 16:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 16:37
---
Understanding: I will screen this issue for duplicate work first by searching the oompah task/docs corpus for the shared OOMPAH topic and duplicate-test wording, then inspect each plausible candidate's full description and comments. If no duplicate is confirmed, I will document the evidence and hand off to an implementation focus without changing code.
---
author: oompah
created: 2026-07-28 16:38
---
Discovery: No confirmed duplicate. The parent OOMPAH-490 uniquely assigns exact duplicate removal and Python test-name shadowing to OOMPAH-499. Reviewed in full: OOMPAH-490 (parent scope), OOMPAH-491 (Git remote safety), OOMPAH-492 (live-tracker isolation), OOMPAH-493 (retry sleeps), OOMPAH-494 (Granian scenarios), OOMPAH-495 (state-branch design tests), OOMPAH-496 (retired UI contracts, explicitly retaining backend shared-strategy coverage), OOMPAH-497/498 (Release Delivery UI ownership/assertion grouping), and OOMPAH-500 (downstream final audit). Archived OOMPAH-168 is a completed production shared-epic-strategy refactor, not this test-source cleanup. No code changes made.
---
<!-- COMMENTS:END -->
