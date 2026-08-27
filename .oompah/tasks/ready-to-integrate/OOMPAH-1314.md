---
id: OOMPAH-1314
type: bug
status: Ready to Integrate
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=d06a039a9e214a4ebead05676d680f95
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:41:13.991341Z'
updated_at: '2026-08-27T03:55:20.941587Z'
work_branch: OOMPAH-1314
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 3
oompah.last_batch:
  batch_id: batch-1c1d234dcdd64c5ba5a90080c24b1e3a
  actor: shedwards
  committed_at: '2026-08-21T00:45:50.707738Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f1f9186ebbbdaf3ad05880fdb23c232f4a9d3176d1544a1a6282efba8ebd5305
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T08:38:04.174094+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed 28 similarity-ranked candidates from the authoritative\
    \ corpus. OOMPAH-1314's error signature (\"Pre-provider contributor evidence exceeded\
    \ its bounded task-authority deadline, timeout_seconds=5.0\") appears novel \u2014\
    \ no active open task matches this orchestrator timeout condition. Related workflow/orchestrator\
    \ tasks (OOMPAH-1000\u20131014) address different scopes (terminal audit, quality\
    \ gates, epic workflows); all are in terminal states (Done/Merged). Terminal-audit\
    \ enforcement tasks (OOMPAH-1015+) report different error types and are terminal.\
    \ No active duplicate found.\nI'm conducting a duplicate screening investigation\
    \ for OOMPAH-1314. Let me analyze the supplied task corpus carefully.\n\n**Task\
    \ Analysis**\n\nOOMPAH-1314 describes:\n- Error from `backend:orchestrator`\n\
    - Message: \"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline\"\n- Fingerprint: b261de6332143a19\n- Timeout: 5.0 seconds\n- Referenced\
    \ task: OOMPAH-1256\n\n**Corpus Review**\n\nI've examined all 28 similarity candidates\
    \ included in the authoritative task corpus. The relevant peers include:\n\n**Similar-appearing\
    \ but DISTINCT issues:**\n- OOMPAH-1000 through OOMPAH-1014 (Merged/Done): These\
    \ address terminal-audit, quality-gate, epic-workflow, and orchestrator admission\
    \ problems \u2014 different error types and scopes\n- OOMPAH-1015 through OOMPAH-1027\
    \ (Merged/Archived): These address \"pre_recovery_finalization_metadata_malformed\"\
    \ from `backend:terminal_audit_enforcement` \u2014 a different error source and\
    \ message entirely\n- OOMPAH-1, OOMPAH-10, OOMPAH-100 (Archived): CI and webhook\
    \ issues, unrelated\n\n**Key Distinctions:**\n- OOMPAH-1314 is specifically about\
    \ a bounded-deadline timeout for \"pre-provider contributor evidence\" in the\
    \ orchestrator\n- No other open (non-terminal) task in the corpus describes this\
    \ exact timeout scenario\n- The error fingerprints are unique (b261de6332143a19\
    \ vs. others like 5bb394d82599b866 for OOMPAH-1015)\n- All potentially similar\
    \ tasks are in terminal states (Done, Merged, Archived) and thus ineligible as\
    \ active duplicate targets per screening rules\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: Reviewed\
    \ 28 similarity-ranked candidates from the authoritative corpus. OOMPAH-1314's\
    \ error signature (\"Pre-provider contributor evidence exceeded its bounded task-authority\
    \ deadline, timeout_seconds=5.0\") appears novel \u2014 no active open task matches\
    \ this orchestrator timeout condition. Related workflow/orchestrator tasks (OOMPAH-1000\u2013\
    1014) address different scopes (terminal audit, quali"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: beb95e7dc23045af813b1599660138b4--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1314
    source_sha: null
    completed_at: ''
  - run_id: 38e24e035bda4f558b058d728dab7a06--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1314
    source_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
    completed_at: '2026-08-21T08:38:04.181202+00:00'
  - run_id: dbde258cf4e04eff9abe23b57e3aca34--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-1314
    source_sha: null
    completed_at: ''
  - run_id: 41555a016c9b4c9e9da8c7845fa18127--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1314
    source_sha: 445f41f2d63fd2d0e11266e8560ad0967edd5c22
    completed_at: '2026-08-21T14:24:11.075331+00:00'
oompah.task_costs:
  total_input_tokens: 380
  total_output_tokens: 13257
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 380
      output_tokens: 13257
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2464
    cost_usd: 0.0
    recorded_at: '2026-08-21T08:38:04.172296+00:00'
  - profile: default
    model: haiku
    input_tokens: 370
    output_tokens: 10793
    cost_usd: 0.0
    recorded_at: '2026-08-21T14:24:11.069485+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1314
  base_branch: main
  base_sha: 859aa8a5a9fcf82063f312f6d16f8eb4ae288631
  head_sha: 445f41f2d63fd2d0e11266e8560ad0967edd5c22
  submitted_at: '2026-08-21T14:23:38.952622+00:00'
  updated_at: '2026-08-21T14:23:38.952622+00:00'
oompah.work_branch: OOMPAH-1314
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-890c21213489
    project_id: proj-14849f1b
    task_id: OOMPAH-1314
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f1c7e2d2b384efa8a537e3566d7a8c1f30880f9384957338c281839138e9729a
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Superseded during recovery cleanup. The underlying contributor-evidence/worker-dispatch
      incident is already fixed on main: persistence uses the 60-second configured
      bound, expected bounded retirement and pre-request worker failures are below
      error-intake severity, and provider-retirement behavior has regression coverage.
      This duplicate auto-filed task must not consume integration capacity or resurrect
      its stale branch.'
    created_at: '2026-08-27T03:55:19.402902+00:00'
    selected_ref: 445f41f2d63fd2d0e11266e8560ad0967edd5c22
    selected_sha: 445f41f2d63fd2d0e11266e8560ad0967edd5c22
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=d06a039a9e214a4ebead05676d680f95 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1256 identifier=OOMPAH-1256 run_id=d06a039a9e214a4ebead05676d680f95 timeout_seconds=5.0

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
- fingerprint: b261de6332143a19
- dedup_fingerprint: b261de6332143a19

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 03:58
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 03:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 03:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 30s
- Log: OOMPAH-1314__20260821T035851Z.jsonl
---
author: oompah
created: 2026-08-21 08:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 08:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 08:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 4s
- Log: OOMPAH-1314__20260821T083644Z.jsonl
---
author: oompah
created: 2026-08-21 13:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 13:21
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 13:22
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 31s
- Log: OOMPAH-1314__20260821T132153Z.jsonl
---
author: oompah
created: 2026-08-21 14:08
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 14:09
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 14:09
---
Starting investigation: Issue is a timeout error in backend:orchestrator where 'pre-provider contributor evidence exceeded its bounded task-authority deadline' with 5.0 second timeout. Will search codebase for error message and timeout handling logic.
---
author: oompah
created: 2026-08-21 14:16
---
DISCOVERY: Found root cause in oompah/orchestrator.py:58067. The 'Pre-provider contributor evidence exceeded its bounded task-authority deadline' error is being logged at ERROR level, which triggers error_watcher. However, this is a gracefully-handled scenario - the persistence task is shielded and continues in background, provider is not started, and task is retried. The same timeout in the CancelledError handler (line 58102) uses logger.warning() instead, which is the correct pattern for expected/graceful failures. Fix: downgrade logger.error to logger.warning to match other timeout patterns in codebase.
---
author: oompah
created: 2026-08-21 14:22
---
IMPLEMENTATION: Changed logger.error() to logger.warning() at oompah/orchestrator.py:58066 for the pre-provider contributor evidence timeout. This gracefully-handled scenario no longer triggers error_watcher. The log message remains the same; only the level changed from ERROR to WARNING, consistent with similar timeout patterns (focus.py:1294, orchestrator.py:3143) and the CancelledError handler on line 58102. All 158 related tests pass.
---
author: oompah
created: 2026-08-21 14:23
---
VERIFICATION: All tests pass (158 tests across provider_retirement, error_watcher, and error_watcher_orchestrator modules). The fix is minimal (1-line change) and backwards compatible. The error message content, extra structured data, and return value remain unchanged; only the log level changed from ERROR to WARNING. This prevents error_watcher from auto-filing this gracefully-handled timeout scenario. Commit: OOMPAH-1314 445f41f2d. Branch pushed to origin/OOMPAH-1314.
---
author: oompah
created: 2026-08-21 14:23
---
Fixed pre-provider contributor evidence timeout error not triggering error_watcher by downgrading log level from ERROR to WARNING. The timeout is a gracefully-handled scenario where persistence continues in background, provider is not started, and task is retired for retry. Change is consistent with similar timeout patterns elsewhere in codebase.
---
author: oompah
created: 2026-08-21 14:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 137, Tool calls: 45
- Tokens: 370 in / 10.8K out [11.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 15m 42s
- Log: OOMPAH-1314__20260821T140922Z.jsonl
---
<!-- COMMENTS:END -->
