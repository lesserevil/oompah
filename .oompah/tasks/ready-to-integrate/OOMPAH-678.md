---
id: OOMPAH-678
type: bug
status: Ready to Integrate
priority: 1
title: Do not flag intentional cross-task handoff denials as auth failures
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T12:01:06.107132Z'
updated_at: '2026-08-01T14:45:26.291333Z'
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
  total_input_tokens: 10685887
  total_output_tokens: 39763
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10685887
      output_tokens: 39763
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 202
    output_tokens: 5974
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:31:18.021105+00:00'
  - profile: default
    model: haiku
    input_tokens: 10685685
    output_tokens: 33789
    cost_usd: 0.0
    recorded_at: '2026-08-01T14:45:20.342453+00:00'
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
  - run_id: OOMPAH-678__20260801T143147Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: frontend
    source_branch: OOMPAH-678
    source_sha: f4e334dc5545267d6b143858ee09f95972f13641
    completed_at: '2026-08-01T14:45:20.346560+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-678
  base_branch: main
  base_sha: 62ca0ca696d08b754e03a200d7227455786da960
  head_sha: f4e334dc5545267d6b143858ee09f95972f13641
  submitted_at: '2026-08-01T14:44:56.184638+00:00'
  updated_at: '2026-08-01T14:45:25.407259+00:00'
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
author: oompah
created: 2026-08-01 14:32
---
Understanding: cross-task 403s made during approved read-only exploration should be informational policy events, while a mismatched token targeting the worker's assigned task must continue to degrade auth health. I will trace server scope validation, auth-health aggregation, task routing, and dashboard rendering, then add regression tests and verify the focused Makefile checks.
---
author: oompah
created: 2026-08-01 14:35
---
Discovery: api_task_handoff currently sends every scope-validation 403 to record_worker_403_scope(), and the dashboard treats that counter as degraded. RunningEntry already stores the server-owned task_handoff_token, but spawned requests carry only token/project. The fix will propagate a non-secret assigned-task identifier, verify it against the live running entry and presented token, count verified peer denials as informational policy events, and retain degraded health for mismatched-token/unknown-scope cases.
---
author: oompah
created: 2026-08-01 14:42
---
Implementation: added verified live-peer scope classification in api_task_handoff. Spawned CLI/ACP workers now carry non-secret OOMPAH_TASK_HANDOFF_TASK_ID; the server matches it to the live RunningEntry token before recording a peer 403 as policy_denial_count. Expected denials remain HTTP 403, skip worker-failure reconciliation, and direct read-only inspection to coordinate peers/inbox. Genuine copied-token, missing-token, expired, revoked, and unknown-scope cases retain actionable auth counters. Dashboard/docs/tests were updated.
---
author: oompah
created: 2026-08-01 14:44
---
Verification: focused suite passed (258 tests): tests/test_auth_health.py, tests/test_task_handoff.py, tests/test_server_auth.py, tests/test_acp_codex_backend.py, and tests/test_dashboard_credential_warning.py. Also passed bash -n scripts/run-tests.sh, git diff --check, and make check-secrets. make terminal-audit-scan could not start because uv failed to create its transient scope (DBus kernel-thread error) before scanning.
---
author: oompah
created: 2026-08-01 14:44
---
Completion: pushed f4e334dc5. Intentional verified live-peer 403s remain rejected but are informational policy events, no longer degrade worker auth health or trigger handoff-failure holding, and direct workers to coordination peers/inbox. Genuine mismatched scope/auth failures remain actionable; UI, docs, propagation, and regression tests are included.
---
author: oompah
created: 2026-08-01 14:45
---
Classify intentional live-peer task-handoff denials as informational policy events while preserving genuine auth-scope alerts; add propagation, dashboard guidance, docs, and regression coverage.
---
author: oompah
created: 2026-08-01 14:45
---
Agent completed successfully in 818s (10719474 tokens)
---
author: oompah
created: 2026-08-01 14:45
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 104
- Tokens: 10.7M in / 33.8K out [10.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 38s
- Log: OOMPAH-678__20260801T143147Z.jsonl
---
<!-- COMMENTS:END -->
