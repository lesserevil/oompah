---
id: OOMPAH-1250
type: task
status: Open
priority: null
title: Restore GitLab external issue intake for native Markdown projects
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T16:21:54.348846Z'
updated_at: '2026-08-21T00:19:28.970977Z'
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
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2517f579a77ef9ddf988d97408ecf08e7492118dc7bd2c3fadd51d0dbd586a34
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 31338a83a387d4e494f6e0d238bc1f513b9032a8b72a41598558d4e108e2754c:142511
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-21T00:19:14.889614+00:00'
  claim_expires_at: '2026-08-21T00:49:14.889614+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 343a2f35-0319-4101-a885-f0030ef5f555
oompah.work_contributors:
  runs:
  - run_id: c39b31ff527f433f8499e69b01c975f0--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1250
    source_sha: null
    completed_at: ''
---
## Summary

Revive the unlanded scope of archived OOMPAH-324. The current server parses and authenticates GitLab Issue/Note hooks and has GitLabIssueTracker, but github_intake_bridge.py, poll_github_issue_intake_project(), and server routing still import only GitHub issues events. Implement a forge-neutral native external-intake bridge with GitLab issue/comment import, provider-qualified oompah.external.gitlab metadata, idempotency, terminal status comment/closure, untrusted provenance, GitLab webhook routing, and polling recovery. Preserve GitHub behavior through compatibility wrappers. Acceptance: an oompah_md GitLab project imports a complete issue into Proposed, copies human comments once, archives on external close, mirrors Merged/Archived to GitLab, handles missed webhook state via poll, and passes GitHub plus GitLab regression tests. This blocks Trickle TRICKLE-132.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:03
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:03
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 55s
- Log: OOMPAH-1250__20260820T230356Z.jsonl
---
author: oompah
created: 2026-08-21 00:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
