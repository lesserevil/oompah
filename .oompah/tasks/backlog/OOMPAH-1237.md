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
updated_at: '2026-08-13T12:43:52.537888Z'
work_branch: null
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
---
## Summary

Live scheduling bug: OOMPAH-1236 created TRICKLE-141, an exact-generation rebase helper for persisted source TRICKLE-130 targeting authoritative parent branch epic-TRICKLE-127. _prepare_epic_rebase_helper_target successfully resolved and admitted that target, but the later generic release-pick validation rejects it because TRICKLE-141 parent_id is TRICKLE-130 rather than the target-owning grandparent TRICKLE-127 and the project patterns only include main/release/*/hotfix/*. Implementation scope: make dispatch branch validation recognize a server-owned epic rebase helper whose exact authority record/metadata binds the helper, parent epic, source branch, target branch, and generation; do not broadly exempt arbitrary epic-* targets or title-shaped tasks. Relevant files: oompah/orchestrator.py, oompah/release_pick_validation.py only if the pure validation contract needs a narrow authority input, and focused tests. Acceptance: TRICKLE-141 passes target validation and dispatches; a forged/wrong-target helper remains rejected; ordinary untracked targets remain rejected.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

