---
id: TASK-61
title: Serialize MR/PR fixes by project
status: Done
assignee: []
created_date: 2026-03-08 01:54
updated_date: 2026-03-08 02:39
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-6cr
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-6cr
  target_branch: null
  url: null
  created_at: '2026-03-08T01:54:07Z'
  updated_at: '2026-03-08T02:39:40Z'
  closed_at: '2026-03-08T02:39:40Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When there are multiple issues in a project in the pipeline, all working on merges, only act on one at a time. This reduces the possibility of multiple merges conflicting with each other.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: a2446ae9-c108-40ef-838e-d44f64d02667
author: oompah
created: 2026-03-08T02:03:12Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 31d53710-4554-425d-84a9-fb733b0d84fb
author: oompah
created: 2026-03-08T02:03:13Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 953171ad-684e-414a-8e7a-cf32e38f5629
author: oompah
created: 2026-03-08T02:03:29Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4619e182-09af-46d3-af35-054c3eb80085
author: oompah
created: 2026-03-08T02:03:30Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 171f931a-e648-4d06-a057-ccc57b3e3d6d
author: Shawn Edwards
created: 2026-03-08T02:03:35Z

I understand the issue: When multiple issues in the same project have open MRs/PRs in the pipeline, the YOLO review actions (_yolo_review_actions_sync) may try to merge multiple PRs simultaneously per project. This can cause merge conflicts since each merge changes the base branch, making subsequent merges require rebasing. The fix should serialize MR/PR actions per project — only act on one MR/PR at a time per project. My plan is to modify _yolo_review_actions_sync to limit processing to the first actionable MR/PR per project per tick, preventing parallel merges for the same project.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 41402cdc-4538-4ae2-b1b9-568bc97e87bb
author: Shawn Edwards
created: 2026-03-08T02:03:55Z

Found the code: _yolo_review_actions_sync in orchestrator.py iterates through ALL open PRs/MRs for each project and potentially merges/acts on multiple simultaneously. Since each merge changes the base branch, subsequent merges may conflict. Fix: break out of the review loop after acting on the first actionable PR/MR per project, serializing actions per project to prevent race conditions.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 699850e8-37c8-4876-a30a-b2cba9172e6f
author: Shawn Edwards
created: 2026-03-08T02:03:58Z

I understand the issue: When multiple issues in the same project have open MRs/PRs (e.g., all are in 'in_progress' or in the YOLO review pipeline), we need to serialize merge operations - only act on ONE merge at a time per project. This prevents git conflicts from multiple concurrent merges into the same target branch.

My plan:
1. In _yolo_review_actions_sync: process at most one YOLO merge action per project per tick (currently it iterates all reviews and tries to merge them all)
2. In _should_dispatch: potentially gate new dispatches when a project already has an open MR/PR ready to merge (to avoid accumulating more merges while one is in-flight)
3. The key constraint is: per-project, only ONE merge operation at a time

Implementation approach: In _yolo_review_actions_sync, break after the first successful (or attempted) merge per project. For conflict resolution and CI retries, those can still be serialized similarly. The dispatch side should check if a project already has an open PR that is CI-passed and ready to merge before dispatching another issue.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1bc6c5ef-b0be-4c2e-a943-0a4d0e7b993a
author: Shawn Edwards
created: 2026-03-08T02:04:24Z

Found the key code: The _yolo_review_actions_sync method in orchestrator.py iterates ALL reviews for a project and tries to merge/rebase/retry them all in one tick. The fix: track which projects have already had a merge action taken this tick, and break after the first action per project. Additionally, _should_dispatch needs to check if a project already has a ready-to-merge PR open, and if so, skip dispatching more issues to that project (serialize the pipeline).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 62a96964-77bf-463d-bf6c-81c2d41eb827
author: Shawn Edwards
created: 2026-03-08T02:06:25Z

Implementation complete. Changed _yolo_review_actions_sync in oompah/orchestrator.py to break out of the review loop after the first actionable PR/MR per project per tick. Each 'continue' was replaced with 'break' so that after resolving conflicts, retrying CI, or merging, no further actions are taken for that project in the same tick. Draft PRs still use 'continue' (skip without acting) so the serialization only counts real actions. Added 8 new tests in TestYoloReviewSerializationByProject covering: single merge per tick, single conflict resolution, single CI retry, draft-skip behavior, independent per-project serialization, non-yolo skip, pending CI no-op, and needs-rebase no-op.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1b9049af-635c-4d43-a5b2-d292a51eb0b8
author: Shawn Edwards
created: 2026-03-08T02:06:36Z

Verification: all 217 tests pass (8 new tests added for the serialization behavior). The 6 warnings are pre-existing from other tests (asyncio coroutine never awaited in pause tests), not from our changes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 78aa87cc-9956-48c9-a4ab-26a3939f3781
author: Shawn Edwards
created: 2026-03-08T02:10:16Z

Implementation complete. Made two changes to oompah/orchestrator.py:

1. Added _project_has_open_review(project_id) method: Returns True if a project has any open non-draft MR/PR in the reviews cache. Uses the per-tick _reviews_cache that's already populated.

2. Added serialization gate in _should_dispatch: Before dispatching a new agent to a project, checks if that project already has an open review. If yes, dispatch is blocked (P0 issues bypass this gate). This prevents accumulating multiple concurrent merges that would conflict.

The YOLO merge serialization (one merge per project per tick via break statements) was already in place.

Tests added in tests/test_orchestrator_merged.py:
- TestProjectHasOpenReview (7 tests) for the new method
- TestDispatchSerializationByProject (6 tests) for the dispatch gate

Total: 230 tests pass (was 217).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7d8ea9dd-2a37-4ae9-aa6a-f0ad82256fa3
author: Shawn Edwards
created: 2026-03-08T02:11:34Z

PR created: https://github.com/lesserevil/oompah/pull/15

Summary of changes:
- Added _project_has_open_review() method to check if a project has open non-draft MRs/PRs
- Added dispatch gate in _should_dispatch: if project already has open review, don't dispatch more agents (P0 bypass)
- YOLO serialization was already in place (one action per project per tick)
- 13 new tests added, all 230 tests pass
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0036851b-ccfd-4310-8be4-86ee1ff01abe
author: oompah
created: 2026-03-08T02:11:45Z

Agent completed successfully in 495s (4404485 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 975072d2-9ed0-45c3-aa6f-f4268f1fe155
author: oompah
created: 2026-03-08T02:12:00Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bd21a702-3c32-4242-acf7-5ab4fcf1b536
author: oompah
created: 2026-03-08T02:12:01Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0abdf3eb-f131-484f-bd61-105a8fcafe25
author: oompah
created: 2026-03-08T02:12:38Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3f2c1a93-4414-40db-84c7-b099f783dbc2
author: oompah
created: 2026-03-08T02:12:38Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e3a60280-7379-4c13-b575-e14dfcef4ccd
author: oompah
created: 2026-03-08T02:13:15Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8ff12e08-047e-425c-948e-e0a39e4e4a3a
author: oompah
created: 2026-03-08T02:13:16Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 305e639c-f384-4b59-b028-d97ca5b712b6
author: oompah
created: 2026-03-08T02:13:52Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b4e1b5f9-0005-46ee-8e74-ceba597e2760
author: oompah
created: 2026-03-08T02:13:53Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6b2a6bbe-4e4c-4593-bbcb-7e6380fc9f31
author: oompah
created: 2026-03-08T02:14:29Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 114a2a39-1f1e-4475-8ad9-41562b1bfb0e
author: oompah
created: 2026-03-08T02:14:30Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8db1aef4-8a5f-4e6e-8b72-a3ae08ab60cc
author: oompah
created: 2026-03-08T02:15:06Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 94546130-ab9a-43e1-b938-163273833021
author: oompah
created: 2026-03-08T02:15:07Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 07b3c4c1-591b-4f43-8368-c3aee30d32ae
author: oompah
created: 2026-03-08T02:15:45Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b8303e62-48a2-466e-a3a2-9f0878c01727
author: oompah
created: 2026-03-08T02:15:45Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9c9cd22a-7166-473d-bdd2-e450c446736c
author: oompah
created: 2026-03-08T02:16:23Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 591251f6-eeeb-4113-ab2f-99bf0719326a
author: oompah
created: 2026-03-08T02:16:24Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 06e25f51-4d22-4cb6-b164-c3aa42502469
author: oompah
created: 2026-03-08T02:17:02Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b1a90c4a-ccd8-485d-a19d-f6a5cde0321c
author: oompah
created: 2026-03-08T02:17:03Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 30b845df-c1a0-438b-ba10-5d3f9d3785a3
author: oompah
created: 2026-03-08T02:17:40Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bb762304-7847-4925-9ed9-d40867756f1d
author: oompah
created: 2026-03-08T02:17:41Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 831be337-373a-4228-a96a-b9ffa11a9aaf
author: oompah
created: 2026-03-08T02:18:18Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 89fed3cd-d96a-47b9-a38a-38656b730448
author: oompah
created: 2026-03-08T02:18:19Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b6086698-f792-46ee-834b-2e52feb49d3d
author: oompah
created: 2026-03-08T02:18:57Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f2141b21-a6d1-46d4-ad3c-457fb6b80bb5
author: oompah
created: 2026-03-08T02:18:58Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7ca24f7b-bdde-4eae-9650-50f17f6a2069
author: oompah
created: 2026-03-08T02:19:35Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: dcf9fd6d-abe1-4ae6-bdd9-5e8f16c8755a
author: oompah
created: 2026-03-08T02:19:36Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1c81e94b-292f-49d6-9b99-4281a3528dac
author: oompah
created: 2026-03-08T02:20:14Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9a5b7d1a-8986-40a9-9dc7-0582d8e7f8c3
author: oompah
created: 2026-03-08T02:20:14Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1b877d2c-e041-4567-84b1-8820f752b578
author: oompah
created: 2026-03-08T02:21:30Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7b3c3334-6b9c-4b12-87d9-b5b330f7aa83
author: oompah
created: 2026-03-08T02:21:31Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: fc23f090-689e-4ee2-86c8-c8082489bac6
author: oompah
created: 2026-03-08T02:22:46Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: eef0b821-2303-4207-b123-5efc963870f4
author: oompah
created: 2026-03-08T02:22:47Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 505aa4d6-1a8e-45d7-87eb-030775339fb3
author: oompah
created: 2026-03-08T02:24:04Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ea8e3bc8-741d-46ff-b7d1-568cdeeccdfe
author: oompah
created: 2026-03-08T02:24:04Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bddd562d-9496-45c1-8587-a5fb7afd6726
author: oompah
created: 2026-03-08T02:25:23Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: eaa8d9eb-7ae4-47be-bb3c-2fa8b7111f2d
author: oompah
created: 2026-03-08T02:25:24Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 06922797-8788-482a-83c2-dbc246c72466
author: oompah
created: 2026-03-08T02:26:41Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: fb3e4121-c43f-41f0-a045-1e7c13137636
author: oompah
created: 2026-03-08T02:26:42Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 22f620ec-b861-4c81-ad97-f3d3304e3361
author: oompah
created: 2026-03-08T02:27:59Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e2c3e2e9-2f7b-4bcf-8610-c676d3f6094f
author: oompah
created: 2026-03-08T02:28:00Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1349d145-1066-4384-935b-6de482613993
author: Shawn Edwards
created: 2026-03-08T02:28:47Z

I understand the issue: Previous agents have already implemented the fix (commits cdb518c and d5e81ca on branch oompah-6cr). All 230 tests pass. My task is to verify the implementation is complete, tests pass, and create the PR.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9c079068-7c19-45f8-ad9c-caaa9d340d6d
author: Shawn Edwards
created: 2026-03-08T02:28:53Z

Discovery: The implementation is already complete with two commits on branch oompah-6cr:
1. d5e81ca: Changed _yolo_review_actions_sync to break after first actionable PR/MR per project (conflict resolve, CI retry, or merge all use break instead of continue)
2. cdb518c: Added _project_has_open_review() method and dispatch gate in _should_dispatch to prevent dispatching new agents when project already has an open review (P0 bypass included)

13 new tests cover all scenarios. All 230 tests pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e851eb2c-a142-4670-a077-8072adb4b30a
author: Shawn Edwards
created: 2026-03-08T02:29:06Z

Verification: All 230 tests pass (including 13 new serialization tests). The 6 warnings are pre-existing from pause tests, not related to our changes.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: acdfb0fb-b8a5-4aee-b714-d527cddde616
author: oompah
created: 2026-03-08T02:29:16Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 046843f9-0da5-4e4f-a2d9-8f504003a2b0
author: oompah
created: 2026-03-08T02:29:17Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3741a9f2-3ae2-4519-92df-9b6e5d954813
author: Shawn Edwards
created: 2026-03-08T02:30:27Z

Verification complete. Implementation was already done by previous agents. All 230 tests pass (13 new tests for serialization behavior).

Summary of implementation on branch oompah-6cr (already pushed):

1. _yolo_review_actions_sync: Changed from 'continue' to 'break' after first actionable PR/MR per project — conflict resolution, CI retry, and merge all use break so only ONE action per project per tick.

2. _project_has_open_review(project_id): New method that checks _reviews_cache for any non-draft open MR/PR for a project.

3. _should_dispatch: Added serialization gate — if a project already has an open review, don't dispatch more agents to it (P0 issues bypass this).

Tests: TestYoloReviewSerializationByProject (8 tests) + TestProjectHasOpenReview (7 tests) + TestDispatchSerializationByProject (6 tests) = 13 new tests covering all scenarios.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2872c65a-8b8b-4c97-b146-7c490d5b7129
author: oompah
created: 2026-03-08T02:30:34Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 999e6074-98b6-4859-b2a1-d99c967b942e
author: oompah
created: 2026-03-08T02:30:35Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 522ee588-4526-4e87-941b-874ccb596887
author: oompah
created: 2026-03-08T02:31:55Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5b724bf2-0849-4b47-9de1-49264ba0bdfa
author: oompah
created: 2026-03-08T02:31:56Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f8fa1b39-ce3c-4379-8b6d-a785a0319dd0
author: Shawn Edwards
created: 2026-03-08T02:33:07Z

Verification complete. All 230 tests pass. The implementation was already complete from previous agents on branch oompah-6cr (pushed to origin).

Summary of what was implemented:
1. _yolo_review_actions_sync: Uses 'break' after first actionable PR/MR per project (conflict resolve, CI retry, merge) — serializes to ONE action per project per tick
2. _project_has_open_review(project_id): Checks _reviews_cache for non-draft open reviews for a project
3. _should_dispatch: Gates new dispatches when project already has open review (P0 bypass included)

13 new tests cover all scenarios. Branch is up to date with origin/oompah-6cr.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: fb2eaf86-d49b-447f-a7d8-0ad72bcd5aed
author: oompah
created: 2026-03-08T02:33:15Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3f05d56c-e1a8-4adf-8af4-c919d6015153
author: oompah
created: 2026-03-08T02:33:16Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 48337867-f80d-4c37-b7ee-a8e795208b7d
author: oompah
created: 2026-03-08T02:34:37Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5f84f215-ceaa-4076-a1e9-2fe39ed151ae
author: oompah
created: 2026-03-08T02:34:38Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 38fdb742-3b7c-47cb-b262-b4cbdf846d94
author: Shawn Edwards
created: 2026-03-08T02:35:52Z

Verification complete. The implementation was already fully merged into main via PR #15 (commit 2644589). All 230 tests pass including the 13 new serialization tests.

Summary of what was delivered:
1. _yolo_review_actions_sync: Uses 'break' after first actionable PR/MR per project (conflict resolve, CI retry, merge) — serializes to ONE action per project per tick
2. _project_has_open_review(project_id): Checks _reviews_cache for non-draft open reviews for a project
3. _should_dispatch: Gates new dispatches when project already has open review (P0 bypass included)

PR merged: https://github.com/lesserevil/oompah/pull/15
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 28bf84e8-37dc-41f5-9061-59bbbd76814c
author: oompah
created: 2026-03-08T02:35:57Z

Agent completed successfully in 80s (181850 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: fbb6b819-79c2-4246-9f39-68ab084e3cf8
author: oompah
created: 2026-03-08T02:36:06Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 953a9d5e-f22a-430c-ba2a-db39bdde94bc
author: oompah
created: 2026-03-08T02:36:07Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ba5dc21a-5648-412c-ad67-ec069b240418
author: oompah
created: 2026-03-08T02:37:26Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ac173a34-ac50-4518-8af7-212102018a2e
author: oompah
created: 2026-03-08T02:37:27Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e548953c-2229-4e03-93a8-d356494966cf
author: oompah
created: 2026-03-08T02:38:48Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: dcef4cdb-dc3c-4f7e-963c-9a1001f4a09b
author: oompah
created: 2026-03-08T02:38:49Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 445dabc4-56ba-4891-a649-259a46c5d6cd
author: Shawn Edwards
created: 2026-03-08T02:39:35Z

Verification complete. The implementation is fully merged to main (PR #15, commit 2644589). All 230 tests pass including 13 new serialization tests.

Summary of what was delivered:
1. _yolo_review_actions_sync: Uses 'break' after first actionable PR/MR per project — serializes to ONE action per project per tick
2. _project_has_open_review(project_id): Checks _reviews_cache for non-draft open reviews for a project
3. _should_dispatch: Gates new dispatches when project already has open review (P0 bypass included)

All tests: 230 passed, 6 warnings (pre-existing). Ready to close.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: af49d865-5cd4-4331-bd25-721cea5080a1
author: oompah
created: 2026-03-08T02:39:41Z

Agent completed successfully in 53s (120921 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
