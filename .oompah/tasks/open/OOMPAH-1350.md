---
id: OOMPAH-1350
type: task
status: Open
priority: null
title: Correct GitLab merge queue semantics and stale Trickle MR handling
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
- priority:p0
assignee: null
created_at: '2026-08-27T19:29:03.022770Z'
updated_at: '2026-08-27T20:40:43.577727Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 782737cb-2e24-4b6d-8b3f-f7499ae4e544
  request_fingerprint: a28c72be488724c2d094a1252a00e1084bb0ce87b25f541009301b04c8b11756
oompah.lifecycle_revision: 1
---
## Summary

Fix GitLab merge queue semantics exposed by Trickle. Implement exact-head enqueue, normalize queue state, fence stale wrong-target MRs, safely reconcile superseded reviews, add Trickle-shaped regression tests, and update docs/UI. Acceptance: merge-train policy is respected, no unfenced enqueue occurs, stale MRs cannot mutate lifecycle, and all gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-27 19:40
---
Deep production audit confirms multiple defects:
1. Trickle GitLab project has merge_pipelines_enabled=true and merge_trains_enabled=true, but Oompah project merge_queue_enabled=false, so current review merge policy selects direct PUT /merge rather than train enrollment.
2. GitLabProvider does not implement enable_auto_merge_exact; queue mode in durable review workflow would call the abstract fail-closed stub. Legacy enable_auto_merge is unfenced (no sha) and uses merge_when_pipeline_succeeds, which docs explicitly say runs outside merge trains.
3. GitLab ReviewRequest normalization never sets auto_merge_enabled or mergeable_state, so queued/enqueued state cannot be observed or verified.
4. Six open Trickle MRs are not in a merge train and have MWPS=false. !7,!8,!19 are green; !15,!20 failed; !14 conflicts.
5. More seriously, !7,!8,!14,!15 are stale MRs targeting main while current accepted task authority targets shared epic branches. For TRICKLE-136, exact head 904d3683 is already integrated into epic-TRICKLE-127, yet !14 remains open against main and now conflicts. Existing wrong-target reviews are preserved but not closed, and stale durable capacity reservations for !7,!8,!14,!15 remain active, defeating max_in_flight_prs=1.
6. The stale !7/!8/!14/!15 MRs can still be seen by broad review polling/legacy YOLO paths, although durable task review reconciliation is absent after tasks left In Review.
Implementation needs separate provider queue policy/capability, GitLab exact-head merge-train enrollment (or explicit fail-closed unsupported behavior), normalized queue state, and exact-authority cleanup/quarantine of stale wrong-target reviews plus capacity reservations.
---
author: oompah
created: 2026-08-27 19:41
---
Additional production proof: GitLab project API reports merge_pipelines_enabled=true and merge_trains_enabled=true. Historical Oompah review_merge jobs directly merged Trickle !6 and !9; neither appears in GitLab merge-train history. In contrast, manually merged !4 and !5 do have merge-train records and refs/merge-requests/*/train pipelines. Therefore Oompah is demonstrably bypassing Trickle merge trains. Current !7,!8,!14,!15,!19,!20 all report merge_when_pipeline_succeeds=false and none is in the train. Also, the review capacity ledger still has unreleased reservations for stale !7,!8,!14,!15, so the configured max_in_flight_prs=1 is not effective. Keep Oompah project paused while fixing; Trickle should be paused before any implementation rollout that can affect MR lifecycle.
---
author: oompah
created: 2026-08-27 19:51
---
Correction/additional finding: /api/v1/reviews currently shows 7 open Trickle MRs (new external !23 plus !7,!8,!14,!15,!19,!20), while max_in_flight_prs=1. Durable capacity has four active old reservations (!7,!8,!14,!15). The limit currently counts open reviews but does not cap their already-existing population; because stale reviews are deliberately preserved open, they permanently block new Oompah review delivery and keep obsolete artifacts actionable in broad YOLO review scans. The required fix should atomically retire capacity and close (or explicitly quarantine/exclude) a superseded open review only after exact task/branch/head/target authority proves it obsolete.
---
author: oompah
created: 2026-08-27 19:54
---
Root cause of the stale-MR state is now traced: parent landing evidence was recorded for TRICKLE-117/127 using old epic heads already contained in main. That temporarily reclassified children from queue mode (target epic branch) to standalone mode (target main), creating/adopting !7,!8,!14,!15. Later, fresh live parent-source head evidence invalidated the old landing fact and `_reclassify_invalid_parented_standalone` moved the task metadata back to queue mode, but the inverse compensation only rewrites tracker target/integration metadata; it never closes/retargets/releases the now-obsolete open MR. History shows repeated queue↔standalone route oscillation for TRICKLE-119 and TRICKLE-136. This is the direct source of stranded MRs and leaked capacity.
---
author: oompah
created: 2026-08-27 20:32
---
Operator-approved containment applied: paused Trickle in Oompah and disabled GitLab merge trains for omniverse/devplat/trickle. Verified GitLab merge_trains_enabled=false; Oompah merge_queue_enabled was already false and remains false. No MRs were merged or closed.
---
author: oompah
created: 2026-08-27 20:35
---
Implementation is now underway in dedicated branch OOMPAH-1350-gitlab-merge-queue. Trickle remains paused and GitLab merge trains remain disabled during repair.
---
author: oompah
created: 2026-08-27 20:40
---
Implementing directly now. Dedicated clone: /tmp/oompah-1350.AOtPdi/repo, branch OOMPAH-1350-gitlab-merge-queue. Initial code changes are focused on GitLab provider exact train enrollment/observation and route-compensation cleanup; Trickle remains paused.
---
<!-- COMMENTS:END -->
