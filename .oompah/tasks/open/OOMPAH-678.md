---
id: OOMPAH-678
type: bug
status: Open
priority: 1
title: Do not flag intentional cross-task handoff denials as auth failures
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T12:01:06.107132Z'
updated_at: '2026-08-01T14:28:06.034713Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3f434c6d149013d600af4f8593b4fdc3ec2db0f1c291658effc7086e08ab1b9b
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 4b071cde-8653-4683-975d-4d15e1bb619f
  claim_owner: 7946c223-6c24-4967-8291-1d20c0e47f05
  claimed_at: '2026-08-01T14:27:57.910349+00:00'
  claim_expires_at: '2026-08-01T14:57:57.910349+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8a17bfd9-c347-4492-a23a-7691cc508eea
---
## Summary

Live regression observed on 2026-08-01 after opening the Exocomp task graph. Authentication health reported five worker cross-scope failures and instructed the operator to repair token forwarding. Correlation shows the token assignment was correct: EXOCOMP-142 successfully viewed/commented on itself, then received three expected 403 denials while attempting to view sibling tasks EXOCOMP-141, EXOCOMP-171, and EXOCOMP-140; EXOCOMP-141 successfully operated on itself, then received two expected denials viewing EXOCOMP-140 and EXOCOMP-138. The current record_worker_403_scope path treats these fail-closed policy denials as degraded transport/auth health, producing a persistent misleading UI alert during normal agent exploration. Implementation scope: distinguish wrong-token propagation from intentional cross-task/project authorization denials using server-known running-entry scope and request target; count expected denials as informational policy events like action denials; preserve an actionable degraded alert for genuine mismatched environment scope; provide or direct agents to the approved read-only peer/coordination interface when sibling inspection is needed. Relevant files: oompah/server.py task-handoff validation, oompah/auth_health.py, task CLI/tool routing, dashboard auth-health rendering, and task-handoff/auth-health tests. Acceptance criteria: the five-call live pattern does not degrade auth health; a worker supplied another task's token while targeting its assigned task still alerts; all cross-scope mutations remain rejected; counters and messages identify the correct remediation without exposing tokens.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 14:28
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 14:28
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
