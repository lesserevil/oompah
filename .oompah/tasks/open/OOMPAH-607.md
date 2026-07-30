---
id: OOMPAH-607
type: bug
status: Open
priority: 1
title: Canonicalize project aliases before terminal owner authorization
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T18:17:13.371379Z'
updated_at: '2026-07-30T18:18:36.565591Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ce6d54478b588c0237fd30bee5b1306c50341a853c166cc5852f9b78e4939340
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: eb91c914-72c2-4aab-a1e5-01c0a3ebd974
  claim_owner: ac40770c-37a8-4b2c-b040-7a7ae948f467
  claimed_at: '2026-07-30T18:18:26.135231+00:00'
  claim_expires_at: '2026-07-30T18:48:26.135231+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 91b59518-0b60-4e41-8483-9814185e200c
---
## Summary

Triggered by: OOMPAH-605

Implementation scope

Fix terminal status requests made with the supported project-name alias (for example `oompah task set-status ... --project oompah`) so the server carries the canonical managed project ID into `_stage_terminal_transition` and owner authorization. Today `_get_tracker_for_issue_or_project` can resolve the tracker through the alias while returning the alias unchanged; `_project_by_id` then returns no project and a valid configured owner receives a misleading HTTP 403. Preserve fail-closed authorization for unknown projects and unauthorized actors. Relevant files include oompah/server.py project/tracker resolution, task CLI project handling, and terminal status interfaces.

Tests

Add regressions showing a configured owner can use an audit override through both project ID and project-name alias; an unauthorized actor and unknown alias still fail closed; ordinary staged terminal requests retain the canonical project ID; error messages do not leak configuration. Run focused server terminal-interface/override/CLI tests and make test.

Acceptance criteria

Project aliases accepted by normal task CLI operations behave identically for terminal owner authorization, no valid owner sees a false 403 solely because an alias was used, and authorization is not weakened.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 18:18
---
Owner-approved liveness follow-up discovered during OOMPAH-605 recovery. Let the oompah server claim and implement this task; direct operator work is not needed while scheduler capacity is healthy.
---
author: oompah
created: 2026-07-30 18:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 18:18
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
