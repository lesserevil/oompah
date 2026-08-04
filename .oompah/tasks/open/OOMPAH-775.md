---
id: OOMPAH-775
type: task
status: Open
priority: 1
title: Route API and auxiliary status writes through TaskTransitionService and enforce
  the boundary
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-776
labels: []
assignee: null
created_at: '2026-08-04T13:58:48.205609Z'
updated_at: '2026-08-04T21:24:21.691400Z'
work_branch: epic-OOMPAH-769--task-OOMPAH-775
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e4b3c9e4e57affbaade0b5587360810bc864502d6a3197b59d93a3869052f197
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 800f53a5-468c-4e5f-ac32-dc42d6c5e9c6
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T21:23:47.769297+00:00'
  claim_expires_at: '2026-08-04T21:53:47.769297+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8f1095d7-edf5-4423-bdee-85244b8786fd
oompah.work_branch: epic-OOMPAH-769--task-OOMPAH-775
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-769--task-OOMPAH-775
  base_branch: epic-OOMPAH-769
  base_sha: 6561d52e5a879375ea3587582f335419ed49310e
  updated_at: '2026-08-04T21:24:14.385412+00:00'
---
## Summary

Migrate server API/CLI handoff paths, stalled_task_watchdog, terminal_audit_enforcement, ACP tools, intake bridges, project maintenance, and remaining production modules to TaskTransitionService. Retain tracker adapter implementations but forbid direct production status calls with an AST/static architectural test and terminal-audit scan integration. Preserve authenticated principal/owner rules and response compatibility. Required tests: REST/CLI transitions, actor mismatch, owner claim, intake promotion, Needs Human instructions, terminal aliases, auxiliary recovery, and architectural boundary violations. Acceptance: only TaskTransitionService and tracker adapters may write status; every transition is journaled and reason-coded.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 21:22
---
Prerequisite OOMPAH-776 is Done and the later duplicate OOMPAH-803 has been archived. Promoting the canonical task so the server can dispatch the remaining OOMPAH-769 boundary work.
---
author: oompah
created: 2026-08-04 21:24
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 21:24
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
