---
id: OOMPAH-1213
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Restart recovery persistence failed closed: restart
  recovery publication was not acknowledged'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T03:50:52.786229Z'
updated_at: '2026-08-21T00:18:19.227570Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
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
  task_fingerprint: 9b03a38e9059580321d5ab6b8701606b8b24491d7c248cc2a9b6fad3b00488c2
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-20T22:55:42.064586+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    # Duplicate Investigation: OOMPAH-1213\n\nI'm analyzing whether OOMPAH-1213 is\
    \ a duplicate of an existing active task. Let me examine the current task corpus\
    \ carefully.\n\n## Analysis\n\n**Current Task:** OOMPAH-1213\n- Error: \"Restart\
    \ recovery persistence failed closed: restart recovery publication was not acknowledged\"\
    \n- Status: Open\n- Component: backend:orchestrator\n- Fingerprint: 399be2300fdef47a\n\
    \n**Peer Tasks Review:**\n\nAll tasks with related similarity scores in the corpus\
    \ (OOMPAH-1000 through OOMPAH-1014, OOMPAH-1015, OOMPAH-1133) are in terminal\
    \ states:\n- **Merged:** OOMPAH-1000, 1001, 1002, 1004, 1005, 1006, 1008, 1009,\
    \ 1010, 1011, 1012, 1013, 1014, 1015\n- **Done:** OOMPAH-1003, 1007\n- **Archived:**\
    \ OOMPAH-1, 10, 1016-1023, 1133\n\n**Related but Distinct Issues:**\n\nThe most\
    \ closely related active-at-time tasks (now merged/done) addressed related orchestrator/workflow\
    \ publication issues but differ in scope:\n\n1. **OOMPAH-1009** (\"Prevent terminal-audit\
    \ churn from starving restart workflow publication\") - addressed restart publication\
    \ livelock when audit churn interferes with publication, not publication not being\
    \ acknowledged\n2. **OOMPAH-1014** (\"Retire orphaned terminal-audit authority\
    \ before workflow publication\") - addressed orphaned terminal-audit metadata\
    \ invalidating publication, not publication acknowledgment failure\n\nOOMPAH-1213's\
    \ error is specifically about **\"restart recovery publication was not acknowledged\"\
    ** \u2014 a distinct failure mode from starvation or invalidation by orphaned\
    \ metadata.\n\n**Conclusion:**\n\nThe error message \"Restart recovery persistence\
    \ failed closed: restart recovery publication was not acknowledged\" does not\
    \ clearly match any of the completed tasks. The peer tasks addressed related orchestrator/publication\
    \ failures but not this specific acknowledgment-failure scenario.\n\n---\n\nFocus\
    \ handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\n\
    Matches: none\n\nEvidence:\n\nOOMPAH-1213 tracks a distinct error from backend:orchestrator"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: df8a6bc6-4edd-4e84-934c-5d0b1c598837
oompah.work_contributors:
  runs:
  - run_id: 870f0c6888f64cd6a7b94e873ceffc23--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1213
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-20T22:55:42.068151+00:00'
  - run_id: 366dc2e64db34a00afe4fb85a61699d4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1213
    source_sha: null
    completed_at: ''
  - run_id: 366dc2e64db34a00afe4fb85a61699d4--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1213
    source_sha: null
    completed_at: ''
  - run_id: 8414a6ee0a5c45409dcef7115d10e61a--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1213
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2412
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2412
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2412
    cost_usd: 0.0
    recorded_at: '2026-08-20T22:55:42.063864+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Restart recovery persistence failed closed: restart recovery publication was not acknowledged

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Restart recovery persistence failed closed: restart recovery publication was not acknowledged

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 399be2300fdef47a
- dedup_fingerprint: 399be2300fdef47a

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 04:28
---
Duplicate error_watcher occurrence suppressed; this task already tracks the same dedup fingerprint.

Source: `backend:orchestrator`

Message: Restart recovery persistence failed closed: restart recovery publication was not acknowledged
---
author: oompah
created: 2026-08-20 22:54
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 22:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.4K out [2.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 37s
- Log: OOMPAH-1213__20260820T225433Z.jsonl
---
author: oompah
created: 2026-08-20 23:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 00:00
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 51s
---
author: oompah
created: 2026-08-21 00:17
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
