---
id: OOMPAH-537
type: task
status: Archived
priority: null
title: Wake event-driven scheduler when a project resumes
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T00:05:46.463901Z'
updated_at: '2026-08-05T00:57:09.720105Z'
work_branch: OOMPAH-537
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/571
review_number: '571'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 264f8df40f31538e96ffb9b1a258e71d424985893cf6c21d4edcf3cfc96f0c51
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T00:09:25.803569+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive duplicate investigation, I have thoroughly\
    \ searched the oompah task tracker and codebase for similar issues.\n\n## Investigation\
    \ Summary\n\n**Search Scope:**\n- `.oompah/tasks/open/` \u2014 1 task found (OOMPAH-281,\
    \ unrelated: self-hosted GitHub Actions runner)\n- `.oompah/tasks/backlog/` \u2014\
    \ 1 task found (OOMPAH-282, unrelated: state branch migration error)\n- `.oompah/tasks/merged/`\
    \ \u2014 Multiple tasks reviewed (OOMPAH-271, OOMPAH-272, OOMPAH-275, etc., all\
    \ unrelated)\n- `.oompah/tasks/archived/` \u2014 Hundreds of tasks scanned for\
    \ keywords\n- Source code (`oompah/server.py`, `oompah/orchestrator.py`, etc.)\
    \ \u2014 Confirmed the `api_project_resume` endpoint exists at line 11197 but\
    \ lacks scheduler wake-up logic\n- Keyword searches: \"wake\", \"scheduler\",\
    \ \"refresh\", \"dispatch\", \"pause\", \"resume\", \"project_resume\", \"orchestrator_refresh\"\
    \ \u2014 No matching tasks found\n\n**Key Findings:**\n1. OOMPAH-537 addresses\
    \ a unique problem: the POST `/api/v1/projects/{project_id}/resume` endpoint persists\
    \ `paused=false` but does NOT wake the event-driven scheduler, causing delayed\
    \ dispatch until the 5-minute full-sync safety poll.\n2. The only open task (OOMPAH-281)\
    \ is unrelated (self-hosted GitHub Actions runner).\n3. No existing active tasks\
    \ address scheduler wake-up, event-driven tick triggering, or project-specific\
    \ refresh events.\n4. The issue mentions OOMPAH-535 and OOMPAH-536 as related\
    \ tasks discovered during verification, but these do not appear in the task tracker\
    \ yet (likely newly created in production).\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive search of `.oompah/tasks/` (open, backlog, merged, archived) and\
    \ keyword searches across source code for \"wake\", \"scheduler\", \"refresh\"\
    , \"dispatch\", \"project_resume\", and related terms yielded no active or open\
    \ tasks describing the same functionality. OOMPAH-537 is a unique production follow-up\
    \ task addressing a gap in the project resume endpoi"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 5be1b978-8654-4f81-8fca-68fc962013e7
oompah.task_costs:
  total_input_tokens: 290
  total_output_tokens: 7039
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 290
      output_tokens: 7039
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 290
    output_tokens: 7039
    cost_usd: 0.0
    recorded_at: '2026-07-29T00:09:25.803157+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/571
oompah.review_number: '571'
oompah.work_branch: OOMPAH-537
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-5c79ef58efd3: '2026-08-05T00:57:00.536072+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-537
    target_state: Archived
    evidence_fingerprint: b1695532ecad7412473792208c2a1160880cb723a664a93b6bb71ce546e8209b
    audit_ids:
    - audit-bff8f23a19bb
    kind: result
    applied: true
    retired_at: '2026-08-05T00:57:00.536084+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-537
    audit_id: audit-bff8f23a19bb
    attempt_id: attempt-5c79ef58efd3
    target_state: Archived
    evidence_fingerprint: b1695532ecad7412473792208c2a1160880cb723a664a93b6bb71ce546e8209b
    status: Archived
    audit_ids:
    - audit-bff8f23a19bb
    applied: true
    created_at: '2026-08-05T00:57:00.536100+00:00'
    applied_at: '2026-08-05T00:57:08.528753+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-bff8f23a19bb
    project_id: proj-14849f1b
    task_id: OOMPAH-537
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b1695532ecad7412473792208c2a1160880cb723a664a93b6bb71ce546e8209b
    attempts:
    - version: 1
      attempt_id: attempt-5c79ef58efd3
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b1695532ecad7412473792208c2a1160880cb723a664a93b6bb71ce546e8209b
      created_at: '2026-08-05T00:42:03.248759+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T00:42:03.248759+00:00'
      branch_key: OOMPAH-537
      verdict: pass
      completed_at: '2026-08-05T00:57:00.535885+00:00'
      ended_at: '2026-08-05T00:57:00.535885+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T00:41:33.938712+00:00'
    updated_at: '2026-08-05T00:57:00.535885+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5c79ef58efd3
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b1695532ecad7412473792208c2a1160880cb723a664a93b6bb71ce546e8209b
    created_at: '2026-08-05T00:42:03.248759+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T00:42:03.248759+00:00'
    branch_key: OOMPAH-537
---
## Summary

Production follow-up discovered while verifying OOMPAH-535 and OOMPAH-536. POST /api/v1/projects/{project_id}/resume persists paused=false, but unlike global orchestrator unpause it does not request a refresh or post a REFRESH_REQUESTED event. With event-driven scheduling, the project can remain undispatched and the dashboard snapshot can continue showing paused=true until the five-minute full-sync safety poll.\n\nImplementation scope:\n- After a successful project resume, wake the active orchestrator so it runs an immediate poll/reconciliation/dispatch cycle.\n- Preserve 404/validation behavior and project-scoped pause semantics. Do not globally unpause the orchestrator.\n- Ensure the dashboard snapshot refreshes promptly from the resulting tick.\n\nRequired tests:\n- Project resume clears the project pause and requests exactly one scheduler refresh/wake-up.\n- Unknown-project and failed updates do not request a refresh.\n- Project pause does not accidentally wake or globally change scheduler state unless explicitly intended.\n- Run focused tests and make test.\n\nAcceptance criteria:\nA resumed project becomes dispatchable without waiting for the periodic full-sync interval; the next event-driven tick sees paused=false; other project/global pause state is unchanged; and production verification can observe OOMPAH-469 dispatched under a non-duplicate implementation focus.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 00:05
---
Claimed directly during live verification. The project pause is already persisted as false, but no refresh event was posted, so no agent can be dispatched before this fix or the periodic full sync.
---
author: oompah
created: 2026-07-29 00:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 00:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 00:09
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 81, Tool calls: 41
- Tokens: 290 in / 7.0K out [7.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 51s
- Log: OOMPAH-537__20260729T000736Z.jsonl
---
author: oompah
created: 2026-07-29 00:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 00:09
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 00:10
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 11
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 2s
- Log: OOMPAH-537__20260729T000936Z.jsonl
---
author: oompah
created: 2026-07-29 00:37
---
Merged in PR #571 as 8792cea7 and deployed to service instance f4d00fa0-7632-4aaf-969a-6ff8237892b3. Live proof: a refreshed paused snapshot at 00:36:47 showed paused=true; POST project resume then produced a new event-driven snapshot at 00:36:51 with paused=false, without waiting for the five-minute safety poll or interrupting the running OOMPAH-470 worker.
---
author: oompah
created: 2026-08-05 00:41
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 00:42
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 00:42
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 00:57
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 8792cea7e9d9549431b9348511753f1f5e70896a
- implementation_commit: d04c47ae2deeb353773e8d03d230e139935f001a
- head: e1b0f4846054bacac48e667295e2c00733d86d8c
- ancestor_of_head: true
- server_code_line_request_refresh: oompah/server.py:15903
- server_code_line_comment: oompah/server.py:15900
- resume_endpoint_line: oompah/server.py:15884
- test_file: tests/test_project_pause.py
- test_resume_refresh: test_resume_endpoint_sets_paused_false (line 349)
- test_pause_no_refresh: test_pause_endpoint_does_not_request_refresh (line 365)
- test_unknown_no_refresh: test_resume_unknown_project_returns_404 (line 374)
- test_validation_no_refresh: test_resume_validation_failure_does_not_request_refresh (line 381)
- focused_test_result: 10 passed in 1.38s
- pr_number: 571
- merge_age_days: ~7
---
<!-- COMMENTS:END -->
