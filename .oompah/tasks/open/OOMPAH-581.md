---
id: OOMPAH-581
type: task
status: Open
priority: null
title: Prune merged epic repair workspaces with task-style branch paths
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T04:35:07.041991Z'
updated_at: '2026-07-30T04:36:09.154903Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a338ea5975a877aefdcedab72f7a1b0b63004ce67dfebb4118df198b424a58e0
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: e7545969-486c-42af-8d3a-922e7c847727
  claim_owner: 4e500792-3d44-4947-bbef-0f678c7beafb
  claimed_at: '2026-07-30T04:36:03.859926+00:00'
  claim_expires_at: '2026-07-30T05:06:03.859926+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: d42f8e1b-a75c-42c8-b891-05e1fb40ce84
---
## Summary

Live cleanup after OOMPAH-459 exposed one remaining owned legacy shape: a terminal epic records work_branch=epic-<id>, but an epic repair/planner run may leave a clean task-style managed worktree at <worktree_root>/<id> on branch <id>. Implementation scope: extend terminal maintenance cleanup in oompah/projects.py/orchestrator cleanup routing to recognize this exact same-identifier repair workspace only for terminal epic records, require the managed registered path and owned exact branch, and delete its worktree plus local/remote ref only when clean and merged/ancestor-safe. Never infer arbitrary paths, shared branches, dirty worktrees, or unmerged heads. Tests: real bare-remote scenario for a terminal epic with canonical epic work_branch plus auxiliary <id> repair worktree/branch; prove cleanup removes the auxiliary workspace and refs, while dirty, unmerged, shared, and different-identifier branches remain preserved. Acceptance criteria: a future OOMPAH-459-shaped repair workspace is removed by the normal aggressive cleanup pass without weakening ownership/ancestry guards; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 04:35
---
Live residue was manually pruned after confirming the clean repair head 95581aca5 is contained in origin/main. Removed managed worktree /home/shedwards/.oompah/worktrees/oompah/OOMPAH-459 and exact local/remote OOMPAH-459 refs. Task remains to automate this exact owned repair-workspace shape for recurrence.
---
author: oompah
created: 2026-07-30 04:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 04:36
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
