---
id: OOMPAH-1262
type: task
status: Backlog
priority: 1
title: Define structured external-prerequisite and profile capability authority
parent: OOMPAH-1231
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T02:39:20.238127Z'
updated_at: '2026-08-14T02:39:20.238127Z'
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
  creation_marker: oompah-1231-prerequisite-authority-v1
  request_fingerprint: e38becde52d97174b7098c49b23a59fd1eae8ff01d7dbaf2d7272a97f3cae836
---
## Summary

Introduce a typed durable implementation-prerequisite record and strict trusted-handoff syntax for named external prerequisites and recovery triggers. Persist it only while the exact live run, assignment, generation, task authority, and accepted head still match; arbitrary prose and ordinary uncertainty must remain normal focus handoffs. Add execution capabilities to agent profiles, distinct from tool/focus capabilities, and prove that an applicable configured profile prevents parking and is selected under final admission revalidation. Relevant areas: new implementation_prerequisite module, handoff parsing/observation in orchestrator, AgentProfile serialization/config/API surfaces, and implementation adapter admission. Required tests: parser strictness, record round-trip and stable identity, exact live-run persistence, late/replaced worker rejection, capable-profile scheduling, config-change race, and restart-safe fact projection. Acceptance: named prerequisite authority is immutable, attributable to one exact run, and cannot be fabricated from prose or used to bypass a capable profile.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

