---
id: OOMPAH-1237
type: task
status: Backlog
priority: null
title: Allow authoritative nested epic targets through dispatch validation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T12:43:52.537888Z'
updated_at: '2026-08-13T12:50:31.641648Z'
work_branch: OOMPAH-1237
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: f788c095-e3fa-4d7f-be3b-44e4bdc9e3bc
  request_fingerprint: ee2eb9d578855aecbf2a73a9611af791e584337300fb41ec49274338137d5a89
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1237
  head_sha: 6232cba0fb65d5099259424d7b5b298f37054a45
  submitted_at: '2026-08-13T12:50:17.846536+00:00'
  updated_at: '2026-08-13T12:50:17.846536+00:00'
oompah.work_branch: OOMPAH-1237
---
## Summary

Live scheduling bug: OOMPAH-1236 created TRICKLE-141, an exact-generation rebase helper for persisted source TRICKLE-130 targeting authoritative parent branch epic-TRICKLE-127. _prepare_epic_rebase_helper_target successfully resolved and admitted that target, but the later generic release-pick validation rejects it because TRICKLE-141 parent_id is TRICKLE-130 rather than the target-owning grandparent TRICKLE-127 and the project patterns only include main/release/*/hotfix/*. Implementation scope: make dispatch branch validation recognize a server-owned epic rebase helper whose exact authority record/metadata binds the helper, parent epic, source branch, target branch, and generation; do not broadly exempt arbitrary epic-* targets or title-shaped tasks. Relevant files: oompah/orchestrator.py, oompah/release_pick_validation.py only if the pure validation contract needs a narrow authority input, and focused tests. Acceptance: TRICKLE-141 passes target validation and dispatches; a forged/wrong-target helper remains rejected; ordinary untracked targets remain rejected.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 12:44
---
Claimed directly from live TRICKLE-141 dispatch failure. The helper has exact server-owned rebase authority and authoritative target epic-TRICKLE-127, but generic release-pick pattern validation rejects it. Implementing the narrow authority-backed exemption now; Oompah remains paused and only Trickle is resumed.
---
author: oompah
created: 2026-08-13 12:50
---
Implemented exact-authority recognition for nested epic rebase helpers without weakening ordinary untracked-target validation. Focused tests: 154 passed. Terminal mutation and secret scans passed. Commit 6232cba0f pushed.
---
author: oompah
created: 2026-08-13 12:50
---
Exact server-issued nested-epic rebase authority now bypasses only the incompatible generic branch-pattern fence; forged legacy-title helpers and ordinary untracked targets remain rejected. Tests and scans pass; commit 6232cba0f is pushed.
---
<!-- COMMENTS:END -->
