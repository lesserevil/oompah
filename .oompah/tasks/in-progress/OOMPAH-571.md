---
id: OOMPAH-571
type: bug
status: In Progress
priority: 1
title: Keep active terminal auditors alive in In Validation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T23:57:40.926693Z'
updated_at: '2026-07-30T00:01:32.476459Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
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
  total_input_tokens: 1370079
  total_output_tokens: 5697
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1370079
      output_tokens: 5697
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1370079
    output_tokens: 5697
    cost_usd: 0.0
    recorded_at: '2026-07-30T00:01:03.603876+00:00'
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
<!-- COMMENTS:END -->
