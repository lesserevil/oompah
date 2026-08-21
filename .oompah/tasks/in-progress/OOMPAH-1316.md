---
id: OOMPAH-1316
type: bug
status: In Progress
priority: 2
title: '[backend:orchestrator] Pre-provider contributor evidence exceeded its bounded
  task-authority deadline issue_id=OOMPAH-1196 identifier=OOMPAH-1196 run_id=45e6fe9e17414df8adda05d62cf48ee4
  timeout_sec...'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-21T00:48:11.061409Z'
updated_at: '2026-08-21T08:45:29.497704Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.lifecycle_revision: 2
oompah.last_batch:
  batch_id: batch-05f0739579694f67a5b19b240bad80a4
  actor: shedwards
  committed_at: '2026-08-21T01:07:48.555641Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 285f4d3f707f257cb7cd6eaca55f7f2cc524ddcf7aad296779f47fcba8a5f2a9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T04:07:48.873435+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-1316 reports a bounded task-authority deadline\
    \ timeout in backend:orchestrator, which does not match any active task in the\
    \ corpus. All similar candidates (primarily OOMPAH-1000\u20131027) are in terminal\
    \ states and describe different issues: workflow/epic handling, terminal-audit\
    \ enforcement metadata, or completed recovery work. The error domain (orchestrator\
    \ vs. terminal_audit_enforcement) and symptom (authority deadline vs. malformed\
    \ metadata) are distinct from all reviewed tasks. No active duplicate can be confirmed\
    \ from the available corpus.\nLooking at OOMPAH-1316 and analyzing the supplied\
    \ project task corpus for potential duplicates.\n\n## Duplicate Investigation\n\
    \n**OOMPAH-1316** reports an error from `backend:orchestrator`:\n- Error: \"Pre-provider\
    \ contributor evidence exceeded its bounded task-authority deadline\"\n- Issue\
    \ ID referenced: OOMPAH-1196\n- Timeout: 5 seconds\n- Status: Open\n- Auto-filed\
    \ by error_watcher\n\n### Corpus Analysis\n\nReviewing the 29 included similarity\
    \ candidates in the corpus:\n\n**Active (non-terminal) tasks:** Only OOMPAH-1316\
    \ itself (status: Open)\n\n**Archived/terminal tasks reviewed:**\n- OOMPAH-1000\
    \ through OOMPAH-1012: Various workflow, epic, and terminal-audit issues \u2014\
    \ all Merged/Done\n- OOMPAH-1014: Orphaned terminal-audit authority \u2014 Merged\n\
    - OOMPAH-1015: Legacy terminal-override compatibility (terminal_audit_enforcement\
    \ malformed metadata) \u2014 Merged\n- OOMPAH-1016 through OOMPAH-1027: Startup\
    \ flood duplicates of OOMPAH-1015 \u2014 all Archived with explicit notes like\
    \ \"Erroneous auto-file duplicate from the 2026-08-11 05ed11f22 malformed-ledger\
    \ startup flood; OOMPAH-1015 is the canonical incident\"\n- OOMPAH-1, OOMPAH-10,\
    \ OOMPAH-164: Various older tasks \u2014 all Archived\n\n### Key Findings\n\n\
    1. **No active duplicate exists.** The only non-terminal task in the corpus is\
    \ OOMPAH-1316 itself.\n\n2. **Different error domain.** OOMPAH-1316 reports an\
    \ error from `backend:orchestrator` about \"bounded task-authority deadline.\"\
    \ The closest similar issues in the corpus (OOMPAH-1015, OOMPAH-1016\u20131027)\
    \ report `backend:terminal_audit_enforcement` errors about \"pre_recovery_finalization_metadata_malformed\"\
    \ \u2014 a different problem.\n\n3. **Cross-reference unresolved.** OOMPAH-1316's\
    \ error message references OOMPAH-1196, but that task is not in the supplied corpus\
    \ (which included only 29 of 726 similarity candidates). That reference may point\
    \ to a related but distinct issue.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-1316\
    \ reports a bounded task"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 10582620-3fc0-485b-9cba-cb3bd6dfc343
oompah.work_contributors:
  runs:
  - run_id: f8c4634572d24818a5ca1d438fb65d62--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1316
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T04:07:48.898133+00:00'
  - run_id: 5cea23f4c35a4786a29cdb3b5f988c65--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1316
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2127
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2127
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2127
    cost_usd: 0.0
    recorded_at: '2026-08-21T04:07:48.872530+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1196 identifier=OOMPAH-1196 run_id=45e6fe9e17414df8adda05d62cf48ee4 timeout_seconds=5.0

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Pre-provider contributor evidence exceeded its bounded task-authority deadline issue_id=OOMPAH-1196 identifier=OOMPAH-1196 run_id=45e6fe9e17414df8adda05d62cf48ee4 timeout_seconds=5.0

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
- fingerprint: e6fd4c20f6c3b668
- dedup_fingerprint: e6fd4c20f6c3b668

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-21 04:06
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 04:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 04:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 19s
- Log: OOMPAH-1316__20260821T040717Z.jsonl
---
author: oompah
created: 2026-08-21 08:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-21 08:37
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-21 08:44
---
UNDERSTANDING: The issue is a timeout in backend:orchestrator when trying to persist pre-provider contributor evidence (provider/model identity) to the tracker. The timeout occurs in _stage_work_contributor_launch() when asyncio.wait_for() exceeds persistence_timeout (default ~5sec based on control/termination timeouts, but can be configured). This error is being auto-filed by error_watcher because it's currently logged as ERROR level. The fix involves either: (1) improving tracker write performance, (2) increasing the timeout gracefully, (3) changing the log level/handling so error_watcher doesn't treat it as a reportable error, or (4) documenting this as expected behavior. Starting investigation of error_watcher and timeout configuration.
---
author: oompah
created: 2026-08-21 08:45
---
DISCOVERY: Root cause identified in oompah/orchestrator.py:_stage_work_contributor_launch(). When writing pre-provider contributor evidence (provider/model identity) times out (line 58066), a logger.error() is called. This log message gets caught by error_watcher (oompah/error_watcher.py) which auto-files it as a task. However, this timeout is an expected failure scenario during task authority transitions/retirement - it's handled gracefully (returns an error message, releases task authority). Similar cancelled timeout case (line 58102) already uses logger.warning(). Fix: change logger.error() to logger.warning() to prevent error_watcher from filing this as a task.
---
<!-- COMMENTS:END -->
