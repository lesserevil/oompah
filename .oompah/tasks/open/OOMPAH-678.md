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
updated_at: '2026-08-01T12:01:09.794090Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live regression observed on 2026-08-01 after opening the Exocomp task graph. Authentication health reported five worker cross-scope failures and instructed the operator to repair token forwarding. Correlation shows the token assignment was correct: EXOCOMP-142 successfully viewed/commented on itself, then received three expected 403 denials while attempting to view sibling tasks EXOCOMP-141, EXOCOMP-171, and EXOCOMP-140; EXOCOMP-141 successfully operated on itself, then received two expected denials viewing EXOCOMP-140 and EXOCOMP-138. The current record_worker_403_scope path treats these fail-closed policy denials as degraded transport/auth health, producing a persistent misleading UI alert during normal agent exploration. Implementation scope: distinguish wrong-token propagation from intentional cross-task/project authorization denials using server-known running-entry scope and request target; count expected denials as informational policy events like action denials; preserve an actionable degraded alert for genuine mismatched environment scope; provide or direct agents to the approved read-only peer/coordination interface when sibling inspection is needed. Relevant files: oompah/server.py task-handoff validation, oompah/auth_health.py, task CLI/tool routing, dashboard auth-health rendering, and task-handoff/auth-health tests. Acceptance criteria: the five-call live pattern does not degrade auth health; a worker supplied another task's token while targeting its assigned task still alerts; all cross-scope mutations remain rejected; counters and messages identify the correct remediation without exposing tokens.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

