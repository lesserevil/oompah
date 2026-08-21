---
id: OOMPAH-1200
type: bug
status: Open
priority: 2
title: '[backend:orchestrator] ACP worker failed issue_id=TRICKLE-120'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T23:57:33.669681Z'
updated_at: '2026-08-21T09:14:47.075463Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 1
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
  task_fingerprint: 59e66775c6aa1e847a26d8ef6fdb80e2ec5b490c64658963e7c6c04c34ac9c93
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T04:49:52.426956+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: The supplied corpus contains 29 reviewed similarity candidates,\
    \ all in terminal states. No active task matches OOMPAH-1200. The closest candidates\
    \ (OOMPAH-1015, 1014, 1012) are error-watcher auto-filed issues from different\
    \ backend subsystems (terminal_audit_enforcement, workflow enforcement) and are\
    \ already completed (Merged/Done/Archived). OOMPAH-1200 reports a specific orchestrator\
    \ worker failure distinct from the audit/workflow issues handled by those tasks.\
    \ Terminal tasks cannot serve as duplicate targets per project policy.\n## Duplicate\
    \ Screening Analysis\n\nI'm analyzing OOMPAH-1200 to determine if it's a duplicate\
    \ of an existing active task. Let me examine the supplied task corpus systematically.\n\
    \n**Current Task Summary:**\n- OOMPAH-1200: `[backend:orchestrator] ACP worker\
    \ failed issue_id=TRICKLE-120`\n- Status: Open (active)\n- Type: Bug auto-filed\
    \ by error_watcher\n- Fingerprint: 4fb1f057c62f8a55\n- Project: proj-14849f1b\n\
    \n**Corpus Analysis:**\n\nI've reviewed all 29 similar candidates in the supplied\
    \ corpus. The key findings:\n\n1. **Terminal State Candidates:** All candidates\
    \ in the corpus are in terminal states:\n   - 8 tasks are Merged (OOMPAH-1000,\
    \ 1001, 1002, 1004, 1005, 1006, 1011, 1012, 1014, 1015)\n   - 2 tasks are Done\
    \ (OOMPAH-1003, 1007)\n   - 20 tasks are Archived (OOMPAH-1, 10, 1016-1030, 100)\n\
    \n2. **Similarity Pattern:** The closest candidates are error-watcher auto-filed\
    \ tasks from related backend systems:\n   - OOMPAH-1015: `[backend:terminal_audit_enforcement]`\
    \ error (Merged)\n   - OOMPAH-1014, 1012, 1011: Workflow/audit system bugs (Merged)\n\
    \   - OOMPAH-1001, 1000: Terminal audit issues (Merged)\n\n3. **Critical Distinction:**\
    \ OOMPAH-1200 reports an error from `backend:orchestrator` specifically. While\
    \ OOMPAH-1015 and related tasks report errors from `backend:terminal_audit_enforcement`\
    \ and workflow systems\u2014different backend systems addressing different failure\
    \ modes.\n\n4. **No Active Candidates:** The corpus contains zero active (non-terminal)\
    \ tasks besides OOMPAH-1200 itself that could serve as a duplicate target.\n\n\
    ---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: The supplied corpus contains 29 reviewed similarity\
    \ candidates, all in terminal states. No active task matches OOMPAH-1200. The\
    \ closest candidates (OOMPAH-1015, 1014, 1012) are error-watcher auto-filed issues\
    \ from different backend subsystems (terminal_audit_enforcement, workflow enforcement)\
    \ and are already completed (Merged/Done/Archived). OOMPAH-1200 reports a sp"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d85a2e23-6317-4f1c-b7a2-ee8bdd5514dd
oompah.work_contributors:
  runs:
  - run_id: 53198fee540b4369bdaab12be3f8441b--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1200
    source_sha: null
    completed_at: ''
  - run_id: 10058cc3def64b7d87f976e6c1a98882--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1200
    source_sha: null
    completed_at: ''
  - run_id: cdc92fe9ae4942f9aff1c4d8d5d14fe6--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1200
    source_sha: null
    completed_at: ''
  - run_id: cdc92fe9ae4942f9aff1c4d8d5d14fe6--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1200
    source_sha: null
    completed_at: ''
  - run_id: 23b4337365314a088eb1522e691e9a6d--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1200
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T04:49:52.429401+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1958
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1958
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1958
    cost_usd: 0.0
    recorded_at: '2026-08-21T04:49:52.426604+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> ACP worker failed issue_id=TRICKLE-120

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> ACP worker failed issue_id=TRICKLE-120

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
- fingerprint: 4fb1f057c62f8a55
- dedup_fingerprint: 4fb1f057c62f8a55
- source_issue: TRICKLE-120

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 22:42
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 22:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 22:43
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 31s
- Log: OOMPAH-1200__20260820T224308Z.jsonl
---
author: oompah
created: 2026-08-20 23:39
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:40
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 52s
- Log: OOMPAH-1200__20260820T234022Z.jsonl
---
author: oompah
created: 2026-08-21 01:11
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 01:12
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 12s
---
author: oompah
created: 2026-08-21 01:12
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-1200/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-21 04:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 04:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 04:49
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.0K out [2.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 48s
- Log: OOMPAH-1200__20260821T044908Z.jsonl
---
author: oompah
created: 2026-08-21 09:14
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
