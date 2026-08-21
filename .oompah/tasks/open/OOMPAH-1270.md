---
id: OOMPAH-1270
type: task
status: Open
priority: null
title: Investigate bulk 'Needs Human' escalation of trickle epic-127 children
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-20T03:44:19.586130Z'
updated_at: '2026-08-21T00:45:50.707738Z'
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
  creation_marker: dd8f06f8-0514-4fde-bea0-18833a1f604c
  request_fingerprint: 1fb15da2e64a50b2b029ff1148c8e4aabbad8da4f132224527fa16b749acfae8
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-1c1d234dcdd64c5ba5a90080c24b1e3a
  actor: shedwards
  committed_at: '2026-08-21T00:45:50.707738Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
---
## Summary

SYMPTOM: ~8-9 trickle (proj-3e4e9214) shared-epic children under epic-TRICKLE-127 sit in 'Needs Human' (TRICKLE-124/131/132/135/137/138/139/142/143). They dominate the workflow action_required decisions and mean there is no runnable trickle work.

EVIDENCE (oompah.log):
- On 2026-08-13 ~18:21:00 a GitLab 'Push Hook' for omniverse/devplat/trickle arrived, immediately followed (18:21:01-18:22:09) by a burst of transitions applied via 'oompah.server Update issue' -> durable transition engine: TRICKLE-124/131/132/135/137 from 'Ready to Integrate' -> 'Needs Human'; TRICKLE-138/139 from 'In Progress' -> 'Needs Human'; TRICKLE-142/143 from 'Open' -> 'Needs Human'. Two were first rejected (transition.illegal_edge / transition.generation_required) then re-applied, confirming they arrived as external Update-issue requests, not an internal orchestrator escalation.
- Internal escalation paths did NOT fire for these tasks: no 'Container dependency cycle detected' log; no 'lacks landing evidence after epic ... merged' log for any TRICKLE-* (that path DID fire for many oompah-project epics: OOMPAH-691/521/765/584 children, indicating a separate recurring landing-evidence escalation worth its own review); require_epic_for_tasks is false for trickle.
- Preceding context (18:07-18:13): repeated 'Deferred standalone review for TRICKLE-131/132: remote branch epic-TRICKLE-127--task-... advanced from accepted submitted head X to Y; submit the new exact head before review' — the epic-127 child branches kept advancing after submission.

HYPOTHESIS: The GitLab status-label sync (oompah/gitlab_tracker.py _ensure_status_label/_set_status_label + status_label_authorized_logins) applied externally-authored 'status:Needs Human' labels pushed by an agent/human/CI to the epic-127 issues, and oompah faithfully applied them. Either an agent is incorrectly setting Needs Human on shared-epic children whose branches keep moving, or the status-label authorization is too permissive for push-hook-driven changes.

INVESTIGATE:
1. Confirm the push author/label source at 18:21 (GitLab issue label events for TRICKLE-124 etc.) and whether it passed status_label_authorized_logins in gitlab_tracker.
2. Determine whether these should have auto-recovered (resubmit new exact head) instead of going to Needs Human, given the earlier 'submit the new exact head before review' deferrals on the same epic.
3. Decide the correct guard: reject/quarantine unauthorized push-hook status-label promotions to Needs Human for shared-epic children, and/or auto-resubmit the advanced head rather than escalating.

ACCEPTANCE: root cause of the bulk escalation identified with the exact label/authorization source; a guard or auto-recovery so routine shared-epic head-advances no longer mass-escalate children to Needs Human; regression test covering a push-hook-driven Needs Human label on an epic child. Reference OOMPAH-1269 (same epic-127 churn fed the publication_rollback storm).

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 17:16
---
IMMEDIATE REMEDIATION DONE: All 9 stuck tasks (TRICKLE-124/131/132/134/137/138/139/142/143) were transitioned Needs Human -> Open via 'oompah task set-status'. Verified: the Needs Human bucket is now empty and the transitions held (no immediate revert). This clears the operational impact.

CORRECTED ROOT-CAUSE DIRECTION (supersedes the initial GitLab status-label hypothesis):
- trickle (proj-3e4e9214) is tracker_kind=oompah_md on forge_kind=gitlab, with a state branch (oompah/state/proj-3e4e9214). Task status lives in git under .oompah/tasks, NOT in GitLab issue status labels.
- Therefore _is_status_label_governed_tracker_kind() is False for trickle, so the existing forge status-label authorization/revert guard in server.py (~23468-23529) never runs for it. That guard only covers github_issues/gitlab_issues trackers.
- The 08-13 18:21 bulk escalation was applied through the API/native update path ('oompah.server Update issue' -> durable transition engine), immediately after a GitLab Push Hook, moving TRICKLE-124/131/132/135/137 (Ready to Integrate), 138/139 (In Progress), 142/143 (Open) -> Needs Human. Two arrived as external Update-issue requests that were first rejected (illegal_edge/generation_required) then applied, confirming external origin.
- Internal escalation paths were ruled out for these tasks: no 'Container dependency cycle detected' log; no 'lacks landing evidence after epic ... merged' log for any TRICKLE-* (that landing-evidence path DID fire for oompah-project epics OOMPAH-691/521/765/584 and is worth a SEPARATE review).

STILL TO PIN (needs a targeted repro): the exact writer that set these md-tracker tasks to Needs Human on the push — candidates: (a) an agent working the epic committing task-file status into the state branch / pushed branch, (b) webhook intake correlating pushed commits/branches to tasks, (c) an operator/script. Recommended next step before any behavior change: instrument the durable transition engine to record authority/actor/source for every transition INTO Needs Human, restart, and capture the next occurrence with an exact culprit. Then decide the guard (authorize external/push-driven Needs Human promotions, or auto-recover advanced shared-epic heads instead of escalating). No code change made yet per owner decision.
---
author: oompah
created: 2026-08-20 22:28
---
DISPATCH UNBLOCKED. Root cause of the post-restart stall was NOT DB size: it was liveness coverage. OOMPAH_WORKFLOW_LIVENESS_MAX_TASK_RECORDS defaulted to 256 while there were 265 nonterminal tasks. In workflow_controller (~line 1132) full-coverage evaluation only happens when nonfinal_count <= max_task_records, so the universal totality scan evaluated 262/265 with 9 omitted every sweep, scan_complete stayed False, and the post-restart audit-priority boundary stayed 'restart_overdue', gating all dispatch. Raised OOMPAH_WORKFLOW_LIVENESS_MAX_TASK_RECORDS and OOMPAH_WORKFLOW_RUNTIME_DECISION_LIMIT to 1000 in the running service .env and restarted; scan now completes (evaluated=265/265, omitted=0), worker reports accepting=true active=3, and codex/opencode agents are running. Documented the coverage>=nonterminal-task-count requirement in .env.example via PR #891. Note: the earlier rollback-event drain (PRs #888/#890) still cleaned up ~19.9M publication_rollback rows and prevents the livelock recurring, but it relocated them into workflow_job_events_archive in the same DB file, so the file did NOT shrink (~4.4G); pruning/separate-file for the audit archive remains a separate follow-up.
---
<!-- COMMENTS:END -->
