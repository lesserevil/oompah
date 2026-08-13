---
id: OOMPAH-1250
type: task
status: Backlog
priority: null
title: Restore GitLab external issue intake for native Markdown projects
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T16:21:54.348846Z'
updated_at: '2026-08-13T16:21:54.348846Z'
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
  creation_marker: b14bdf4d-7f07-48e7-bea5-bd9a4c15a754
  request_fingerprint: 35c587882c8a948f1f7683918040d652db1c9e5eb82d33f59e8351c7a160037b
---
## Summary

Revive the unlanded scope of archived OOMPAH-324. The current server parses and authenticates GitLab Issue/Note hooks and has GitLabIssueTracker, but github_intake_bridge.py, poll_github_issue_intake_project(), and server routing still import only GitHub issues events. Implement a forge-neutral native external-intake bridge with GitLab issue/comment import, provider-qualified oompah.external.gitlab metadata, idempotency, terminal status comment/closure, untrusted provenance, GitLab webhook routing, and polling recovery. Preserve GitHub behavior through compatibility wrappers. Acceptance: an oompah_md GitLab project imports a complete issue into Proposed, copies human comments once, archives on external close, mirrors Merged/Archived to GitLab, handles missed webhook state via poll, and passes GitHub plus GitLab regression tests. This blocks Trickle TRICKLE-132.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

