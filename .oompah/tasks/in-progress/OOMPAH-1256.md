---
id: OOMPAH-1256
type: bug
status: In Progress
priority: 2
title: '[backend:server] Add comment API error: ProjectError(''Unknown project'')'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- needs:backend
assignee: null
created_at: '2026-08-13T18:21:20.794310Z'
updated_at: '2026-08-21T02:22:51.110128Z'
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
  task_fingerprint: 6caf01bcb2e9059d59ea0c2824c054eb9bc69dd534f6997ed6b7fba2fe4f460a
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-20T23:09:59.480737+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: All 30 candidate tasks in the supplied corpus are in\
    \ terminal states (Archived, Merged, or Done). The most thematically related task\
    \ is OOMPAH-1015 (Merged), which represents a \"backend:terminal_audit_enforcement\"\
    \ error from a different backend component, not a duplicate of the \"backend:server\"\
    \ Add comment API error. The corpus selection process already evaluated 749 tasks\
    \ and returned the 31 most similar; the absence of any active duplicate among\
    \ those candidates confirms no active duplicate exists for OOMPAH-1256.\n# Duplicate\
    \ Screening: OOMPAH-1256\n\nI am the Duplicate Investigator. My role is to determine\
    \ whether OOMPAH-1256 is a duplicate of an existing open task. I will review only\
    \ the supplied project task corpus and return a machine-readable verdict without\
    \ mutating any task state.\n\n## Analysis\n\n**Current Task**: OOMPAH-1256 (Open)\n\
    - Title: \"[backend:server] Add comment API error: ProjectError('Unknown project')\"\
    \n- Issue Type: bug\n- Status: Open\n- Error fingerprint: 481e003699b190a0\n\n\
    **Corpus Review**: The supplied corpus contains 31 tasks total (including the\
    \ current task). Let me identify which are active (non-terminal):\n\n1. **OOMPAH-1256**\
    \ (Open) \u2014 the current task\n\n2. **All other tasks in corpus**: 30 remaining\
    \ tasks\n\nChecking statuses of the 30 other tasks:\n- OOMPAH-1, OOMPAH-10, OOMPAH-164,\
    \ OOMPAH-2: **Archived** (terminal)\n- OOMPAH-1000, OOMPAH-1001, OOMPAH-1002,\
    \ OOMPAH-1004, OOMPAH-1006, OOMPAH-1008, OOMPAH-1011, OOMPAH-1012, OOMPAH-1014,\
    \ OOMPAH-1015: **Merged** (terminal)\n- OOMPAH-1016 through OOMPAH-1030 (15 tasks):\
    \ **Archived** (terminal)\n- OOMPAH-1003, OOMPAH-1007: **Done** (terminal)\n\n\
    **Result**: Every candidate task in the corpus is in a terminal state (Done, Merged,\
    \ or Archived). Per the requirements, terminal-state tasks cannot be duplicate\
    \ targets.\n\nThe similarity selection already included 31 tasks (the 31 most\
    \ similar across the 749 candidates evaluated), and all are terminal. This indicates\
    \ no active open task shares sufficient similarity to be an active duplicate.\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: All 30 candidate tasks in the supplied corpus are\
    \ in terminal states (Archived, Merged, or Done). The most thematically related\
    \ task is OOMPAH-1015 (Merged), which represents a \"backend:terminal_audit_enforcement\"\
    \ error from a different backend component, not a duplicate of the \"backend:server\"\
    \ Add comment API error. The corpus selection process already evaluated 749 tasks\
    \ and returne"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 18cd51c5-44a1-4260-b470-ea5e0208f690
oompah.work_contributors:
  runs:
  - run_id: b1ecea5907d449078be81372d6dfdb31--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1256
    source_sha: 02bd5960434a5c65dce259894737a55ab7a8ea96
    completed_at: '2026-08-20T23:09:59.484257+00:00'
  - run_id: 9da0ae497c25490b8b80ea20073f4706--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: 9da0ae497c25490b8b80ea20073f4706--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: d06a039a9e214a4ebead05676d680f95--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: d06a039a9e214a4ebead05676d680f95--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: 1414e9ae9ba240f49892412590acb6e7--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: 1414e9ae9ba240f49892412590acb6e7--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: 4558758c384f412a8f10b244fc46eafc--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: 4558758c384f412a8f10b244fc46eafc--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: 69f4a7d3905b4d3e801bc7f836234ea0--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: 69f4a7d3905b4d3e801bc7f836234ea0--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: dc28d91e04594d68817bb3cba950d91e--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
  - run_id: db2acfd07a4a4d7b8abaa64a2daa4317--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: docs
    source_branch: OOMPAH-1256
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 840
  total_output_tokens: 2088
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 840
      output_tokens: 2088
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1876
    cost_usd: 0.0
    recorded_at: '2026-08-20T23:09:59.480055+00:00'
  - profile: default
    model: haiku
    input_tokens: 830
    output_tokens: 212
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:17:35.007387+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:server`:

> Add comment API error: ProjectError('Unknown project')

### Steps to Reproduce
1. Run oompah with `backend:server` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:server` and is recorded by oompah's `error_watcher`:

> Add comment API error: ProjectError('Unknown project')

### Expected Behavior
The operation in `backend:server` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:server` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 481e003699b190a0
- dedup_fingerprint: 481e003699b190a0

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.9K out [1.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 10s
- Log: OOMPAH-1256__20260820T230933Z.jsonl
---
author: oompah
created: 2026-08-21 00:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 00:20
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 00:21
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 21s
- Log: OOMPAH-1256__20260821T002042Z.jsonl
---
author: oompah
created: 2026-08-21 00:40
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 00:41
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 00:42
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 53s
- Log: OOMPAH-1256__20260821T004149Z.jsonl
---
author: oompah
created: 2026-08-21 00:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 00:55
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 15s
---
author: oompah
created: 2026-08-21 01:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 01:12
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 01:13
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 31s
- Log: OOMPAH-1256__20260821T011237Z.jsonl
---
author: oompah
created: 2026-08-21 01:18
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 01:18
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 40s
---
author: oompah
created: 2026-08-21 01:48
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 01:49
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 01:50
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 12s
- Log: OOMPAH-1256__20260821T014937Z.jsonl
---
author: oompah
created: 2026-08-21 02:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 02:02
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-21 02:15
---
**Understanding & Initial Investigation:**

The error 'Add comment API error: ProjectError("Unknown project")' occurs in the backend:server's api_add_comment endpoint (oompah/server.py line 17416). 

**Initial Findings:**
1. The POST /api/v1/issues/{id}/comments endpoint resolves project_id via _get_tracker_for_issue_or_project
2. This calls _canonical_managed_project_id which validates the project exists in the managed project store
3. If the project isn't found in managed projects, ProjectError('Unknown project') is raised
4. The error message is intentionally generic (line 8273) to avoid leaking config details

**Next Steps:**
- Trace why proj-14849f1b project lookup is failing
- Check if this is about missing name-based fallback in _canonical_managed_project_id
- Verify project_store.find_by_name() is being called
- Investigate if this is a race condition or misconfiguration
---
author: oompah
created: 2026-08-21 02:16
---
**HANDOFF: Backend Fix Required**

**What I Found:**
The error 'Add comment API error: ProjectError("Unknown project")' originates from the HTTP POST /api/v1/issues/{id}/comments endpoint in oompah/server.py (line 17416).

**Root Cause Analysis:**
1. api_add_comment (line 17242) resolves tracker via _get_tracker_for_issue_or_project
2. This calls _canonical_managed_project_id (line 8323) to validate the project
3. _canonical_managed_project_id only checks managed projects in the project_store, using name-based fallback
4. When project resolution fails, ProjectError("Unknown project") is raised with a generic error message
5. Similar name-based fallback exists in orch._tracker_for_project but is never reached due to early failure

**Key Files:**
- oompah/server.py: api_add_comment (17242), _get_tracker_for_issue_or_project (8319), _canonical_managed_project_id (8232)
- oompah/orchestrator.py: _tracker_for_project (10277) - has working name-based fallback
- tests/test_tracker_for_project_name_fallback.py - validates fix for OOMPAH-161 (similar issue)

**Requirements for Backend Fix:**
- Ensure _canonical_managed_project_id applies name-based fallback like _tracker_for_project does
- OR ensure project_id is properly canonicalized before calling _canonical_managed_project_id
- Verify no regression in project store lookups
- Update error message to include project_id for debuggability (if appropriate for security policy)

**Not Documentation Work:** This is a backend logic error, not a docs gap. My role is limited to documentation.
---
author: oompah
created: 2026-08-21 02:17
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 48
- Tokens: 830 in / 212 out [1.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 15m 40s
- Log: OOMPAH-1256__20260821T020219Z.jsonl
---
<!-- COMMENTS:END -->
