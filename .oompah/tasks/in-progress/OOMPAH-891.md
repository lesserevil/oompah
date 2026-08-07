---
id: OOMPAH-891
type: task
status: In Progress
priority: null
title: Isolate epic-rebase workers from all remote-write credentials
parent: OOMPAH-879
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T13:30:11.042474Z'
updated_at: '2026-08-07T13:32:50.043972Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Implement worker-launch isolation for epic-rebase helpers across CLI, API, and ACP paths. Remove forge/Git write tokens, SSH agent/socket/key access, credential-helper and user Git config, and reject embedded remote credentials before dispatch. Preserve task-handoff capability only. Add tests proving each launch path cannot inherit or reconstruct remote-write authority. Acceptance: no epic-rebase worker process has a usable remote-write credential or route.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

