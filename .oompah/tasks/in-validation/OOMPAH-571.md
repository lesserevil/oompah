---
id: OOMPAH-571
type: bug
status: In Validation
priority: 1
title: Keep active terminal auditors alive in In Validation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:57:40.926693Z'
updated_at: '2026-08-06T00:25:14.341763Z'
work_branch: OOMPAH-571
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/586
review_number: '586'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 67690d03e2c474f5851485e0d398ebc37696b6a30e2956c23d75e75144c8ab89
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T00:01:03.604991+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed active OOMPAH-476, OOMPAH-478, and OOMPAH-482.\
    \ Their scopes are terminal-status interfaces, epic rollup routing, and audit-repair\
    \ planning\u2014not auditor lifetime reconciliation. OOMPAH-475 covers auditor\
    \ dispatch/recovery but is Merged and excluded. No files or tracker state were\
    \ modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c8548a53-d97b-48cb-a232-674c85fc6842
oompah.task_costs:
  total_input_tokens: 1370341
  total_output_tokens: 5760
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1370341
      output_tokens: 5760
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1370079
    output_tokens: 5697
    cost_usd: 0.0
    recorded_at: '2026-07-30T00:01:03.603876+00:00'
  - profile: default
    model: haiku
    input_tokens: 262
    output_tokens: 63
    cost_usd: 0.0
    recorded_at: '2026-07-30T00:02:41.617883+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-571__20260729T235849Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-571
    source_sha: 8483db2e3e718c1f5f6476018d954574ce5d42f9
    completed_at: '2026-07-30T00:01:03.611530+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/586
oompah.review_number: '586'
oompah.work_branch: OOMPAH-571
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-daccfe18b915
    project_id: proj-14849f1b
    task_id: OOMPAH-571
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d086f03be09cbbb3d38e5d0e9dbb5b80f1997493fd3e0c5804b97a34ef1d1629
    attempts:
    - version: 1
      attempt_id: attempt-d81be8447368
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d086f03be09cbbb3d38e5d0e9dbb5b80f1997493fd3e0c5804b97a34ef1d1629
      created_at: '2026-08-06T00:24:56.415492+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T00:24:56.415492+00:00'
      branch_key: OOMPAH-571
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-06T00:24:34.485366+00:00'
    updated_at: '2026-08-06T00:24:56.415492+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d81be8447368
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d086f03be09cbbb3d38e5d0e9dbb5b80f1997493fd3e0c5804b97a34ef1d1629
    created_at: '2026-08-06T00:24:56.415492+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T00:24:56.415492+00:00'
    branch_key: OOMPAH-571
---
## Summary

Triggered by: OOMPAH-476

Implementation scope: fix running-agent reconciliation so an entry marked is_auditor remains active while its tracker task is In Validation. Continue terminating auditors if the task leaves In Validation or reaches a configured terminal state, and preserve existing behavior for ordinary implementation, duplicate-screening, and epic-repair workers. Relevant code: Orchestrator._reconcile in oompah/orchestrator.py. Tests: reproduce the live failure where the auditor is dispatched and the next reconciliation tick logs 'no longer in_progress' and terminates it; assert an In Validation auditor's snapshot is refreshed without termination, and assert an ordinary worker in In Validation still terminates. Acceptance criteria: completion auditors can reach submit_audit_result, OOMPAH-478/OOMPAH-482 leave In Validation after audit, focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 23:57
---
Taking this direct-main deadlock fix now while the integration queue continues its current gate.
---
author: oompah
created: 2026-07-29 23:58
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 23:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 00:01
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 24
- Tokens: 1.4M in / 5.7K out [1.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 16s
- Log: OOMPAH-571__20260729T235849Z.jsonl
---
author: oompah
created: 2026-07-30 00:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 00:01
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 00:01
---
Understanding: The issue is that auditors (entries with is_auditor=True) are being terminated prematurely during reconciliation when their tracker task enters 'In Validation' state. The fix needs to keep auditors alive while In Validation so they can reach submit_audit_result, but continue terminating them if the task leaves In Validation or reaches a terminal state. Ordinary workers should still terminate when In Validation. Plan: (1) Explore Orchestrator._reconcile logic in orchestrator.py, (2) Identify the termination condition that fires for In Validation, (3) Add logic to exempt is_auditor entries from termination while In Validation, (4) Write tests to verify the fix and ensure existing behavior is preserved.
---
author: oompah
created: 2026-07-30 00:02
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 14
- Tokens: 262 in / 63 out [325 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 11s
- Log: OOMPAH-571__20260730T000132Z.jsonl
---
author: oompah
created: 2026-07-30 00:02
---
PR #586 is open with the auditor-reconciliation regression fix; focused tests pass and the full gate is running.
---
author: oompah
created: 2026-07-30 00:05
---
Implementation complete on pushed branch OOMPAH-571 (3b08a0551), PR #586. Focused reconciliation tests: 5 passed. Full make test: 13,605 passed, 7 skipped.
---
author: oompah
created: 2026-07-30 00:10
---
YOLO: merged PR #586.
---
author: oompah
created: 2026-08-06 00:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-06 00:25
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 00:25
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
