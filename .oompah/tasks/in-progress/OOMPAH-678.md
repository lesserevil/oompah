---
id: OOMPAH-678
type: bug
status: In Progress
priority: 1
title: Do not flag intentional cross-task handoff denials as auth failures
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T12:01:06.107132Z'
updated_at: '2026-08-01T14:31:45.915626Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3f434c6d149013d600af4f8593b4fdc3ec2db0f1c291658effc7086e08ab1b9b
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T14:31:18.022468+00:00'
  matched_identifiers: []
  evidence: "Based on my thorough investigation, I have completed the duplicate screening\
    \ for OOMPAH-678. Here are my findings:\n\n## Investigation Summary\n\n**Search\
    \ Strategy:**\n- Searched `.oompah/tasks/` for keywords: auth health, 403, token,\
    \ handoff, cross-task, scope, denial, regression, worker capability\n- Reviewed\
    \ all task state directories: open, merged, archived, backlog\n- Checked the ONLY\
    \ currently open task (OOMPAH-281: GitHub Actions runner setup) - completely unrelated\n\
    - Examined codebase: auth_health.py exists with related functions but they're\
    \ not called anywhere yet\n\n**Evidence:**\n1. **Open Tasks**: Only OOMPAH-281\
    \ exists (GitHub Actions runner setup) - unrelated to auth health\n2. **Codebase\
    \ State**: \n   - Functions `record_worker_403_scope()` and `record_worker_403_action()`\
    \ are defined in `auth_health.py` but NEVER called\n   - `task_handoff.py` has\
    \ scope validation logic but no 403 health recording implementation\n   - No endpoint\
    \ currently integrates these to distinguish intentional denials from auth failures\n\
    3. **No matching patterns**: Comprehensive regex searches across all task metadata\
    \ found NO existing task covering cross-task handoff auth health distinction\n\
    \n**Conclusion**: OOMPAH-678 describes a NEW feature/bug fix that requires implementing\
    \ infrastructure to distinguish intentional cross-task authorization denials from\
    \ actual authentication failures. This is not a duplicate of any existing task.\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Exhaustive search of .oompah/tasks across all states\
    \ (open, merged, archived, backlog) using 15+ keyword patterns related to auth\
    \ health, task handoff, 403 errors, and scope validation found NO matching tasks.\
    \ The single open task (OOMPAH-281) covers GitHub Actions runners. Code review\
    \ shows auth_health.py functions are defined but unused. This is a new feature\
    \ requiring integration of existing infrastructure components."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: b4477585-ed1a-46af-bc44-9bf2f59b337c
oompah.task_costs:
  total_input_tokens: 202
  total_output_tokens: 5974
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 202
      output_tokens: 5974
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 202
    output_tokens: 5974
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:31:18.021105+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-678__20260801T142816Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-678
    source_sha: 62ca0ca696d08b754e03a200d7227455786da960
    completed_at: '2026-08-01T14:31:18.033726+00:00'
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
author: oompah
created: 2026-08-01 14:31
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 62, Tool calls: 30
- Tokens: 202 in / 6.0K out [6.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 15s
- Log: OOMPAH-678__20260801T142816Z.jsonl
---
author: oompah
created: 2026-08-01 14:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 14:31
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
