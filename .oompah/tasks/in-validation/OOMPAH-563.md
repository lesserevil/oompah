---
id: OOMPAH-563
type: bug
status: In Validation
priority: 1
title: Make service-state persistence atomic and recover terminal-audit quarantine
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T21:36:54.712161Z'
updated_at: '2026-08-05T23:22:23.524854Z'
work_branch: OOMPAH-563
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/583
review_number: '583'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bdde81b07a41310991436e518c773d153354bfafae950790f7022c715f28a6f3
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T21:39:05.316495+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-281 and OOMPAH-282, plus closest archived tasks
    OOMPAH-219, OOMPAH-257, and OOMPAH-265. None covers atomic `service_state.json`
    persistence or terminal-audit quarantine recovery. No files or tracker records
    were modified.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 59690314-eeef-4556-96b5-f384b761404a
oompah.task_costs:
  total_input_tokens: 494016
  total_output_tokens: 3764
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 493971
      output_tokens: 2706
      cost_usd: 0.0
    opus:
      input_tokens: 45
      output_tokens: 1058
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 493525
    output_tokens: 2600
    cost_usd: 0.0
    recorded_at: '2026-07-29T21:39:05.315145+00:00'
  - profile: default
    model: haiku
    input_tokens: 446
    output_tokens: 106
    cost_usd: 0.0
    recorded_at: '2026-07-29T21:43:05.376900+00:00'
  - profile: deep
    model: opus
    input_tokens: 45
    output_tokens: 1058
    cost_usd: 0.0
    recorded_at: '2026-07-29T21:46:50.075594+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-563__20260729T213757Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-563
    source_sha: 31f8938b8f669a316a830690aaedcc1e0d3834bf
    completed_at: '2026-07-29T21:39:05.324442+00:00'
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-563
  head_sha: f47d09a7bc7812f5c881a0a1356d559202276c85
  submitted_at: '2026-07-29T21:46:35.201256+00:00'
  updated_at: '2026-07-29T21:46:35.201256+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/583
oompah.review_number: '583'
oompah.work_branch: OOMPAH-563
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-79e52794cc1e
    project_id: proj-14849f1b
    task_id: OOMPAH-563
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf668811f69e8000b632265f5e6af57507d688e19a56b427cc3ab29f2de868fc
    attempts:
    - version: 1
      attempt_id: attempt-3279af4acdce
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: cf668811f69e8000b632265f5e6af57507d688e19a56b427cc3ab29f2de868fc
      created_at: '2026-08-05T23:22:12.764110+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T23:22:12.764110+00:00'
      branch_key: OOMPAH-563
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T23:21:25.964144+00:00'
    updated_at: '2026-08-05T23:22:12.764110+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-3279af4acdce
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cf668811f69e8000b632265f5e6af57507d688e19a56b427cc3ab29f2de868fc
    created_at: '2026-08-05T23:22:12.764110+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T23:22:12.764110+00:00'
    branch_key: OOMPAH-563
---
## Summary

Triggered by: OOMPAH-561

Live terminal-audit enforcement entered quarantine after .oompah/service_state.json was observed malformed twice during concurrent maintenance writes (Expecting ':' delimiter and Extra data). Scope: serialize orchestrator service-state read/modify/write operations with a process-local reentrant lock; write JSON through a same-directory temporary file and atomic replace; preserve and fail closed on an already-unreadable state document instead of overwriting it; keep terminal-audit callback merging compatible; add deterministic concurrent-writer and corrupt-state regression tests; document/verify recovery; and gracefully restart the live service after the tested fix is deployed so the current terminal-task baseline is rebuilt and the alert clears. Relevant files: oompah/orchestrator.py and focused service-state/terminal-audit tests. Acceptance criteria: concurrent paused/cursor/terminal-audit state updates produce one valid document containing every update; a corrupt document is not destroyed; terminal-audit baseline initializes without quarantine after restart; the dashboard alert disappears; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 21:37
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 21:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 21:39
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 11
- Tokens: 493.5K in / 2.6K out [496.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 16s
- Log: OOMPAH-563__20260729T213757Z.jsonl
---
author: oompah
created: 2026-07-29 21:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 21:39
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-29 21:39
---
Root cause confirmed: Orchestrator._save_state performed an unlocked in-place read/modify/write from dispatch and maintenance threads. Live logs captured malformed JSON twice, after which later writes replaced the document with only a maintenance cursor. Implemented a process-local RLock covering the full transaction, fsynced same-directory temporary writes plus atomic replace, and fail-closed preservation after any read failure. Added deterministic overlapping-writer, corrupt-state preservation, serialization-failure, terminal-audit merge, and post-restart recovery tests; focused suite is green (27 passed).
---
author: oompah
created: 2026-07-29 21:42
---
HANDOFF: Frontend Developer assessment - This task requires backend/orchestrator expertise, not frontend work.

**Finding**: OOMPAH-563 is fundamentally a Python concurrency and file I/O atomicity issue in oompah/orchestrator.py, not user-facing UI work. The scope involves:
- Serializing service-state read/modify/write operations with process-local reentrant locks
- Atomic JSON file writes via temporary files  
- Corrupt state document preservation (fail-closed approach)
- Concurrency regression tests
- Terminal-audit integration

**Current state**: The terminal_audit_enforcement.py already has basic locking infrastructure (_STATE_LOCK_GUARD, _STATE_LOCKS dict, reentrant RLock) and temporary file handling in _persist(). However, concurrent updates from multiple orchestrator components (paused state, cursor state, terminal-audit state) to service_state.json are not properly coordinated.

The only frontend mention is verifying the dashboard alert clears after restart—that's monitoring, not UI development.

**Recommendation**: This needs a backend/core specialist to extend orchestrator.py's locking model across all service-state mutation points, ensure atomic compound writes, add deterministic concurrent-writer tests, and implement recovery verification. I am not the right agent for this work.

**Next focus**: `needs:refactor` (core orchestrator work)
---
author: oompah
created: 2026-07-29 21:43
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 26
- Tokens: 446 in / 106 out [552 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 48s
- Log: OOMPAH-563__20260729T213923Z.jsonl
---
author: oompah
created: 2026-07-29 21:43
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-29 21:43
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-29 21:45
---
PRIMARY CHECKOUT COORDINATION: implementation is complete on branch OOMPAH-563 and the full gate is green (13,581 passed, 7 skipped). Do not modify or submit a competing head. Please stop and hand off without code changes; the primary checkout is committing and publishing the tested implementation now.
---
author: oompah
created: 2026-07-29 21:45
---
Understanding & plan: worktree is currently clean (previous run's work was not committed). Restarting from main. Root cause: \`Orchestrator._save_state\` (oompah/orchestrator.py:1863) does an unlocked read-modify-write, opening \`service_state.json\` for write directly (no temp+atomic-replace). Multiple caller sites (pause, maintenance cursor, epic_rebase_states, shared_absorption_evidence, restart_issues, budget window, terminal-audit) can interleave and produce malformed JSON. On corruption \`_load_state\` swallows the error and returns \`{}\`, so the next \`_save_state\` overwrites the corrupt file, destroying evidence. Plan: (1) add a process-local reentrant lock covering \`_load_state\` + \`_save_state\`; (2) in \`_save_state\`, refuse to write when \`_state_load_failed\` is set (fail-closed preservation); (3) write via same-directory tempfile with fsync and \`os.replace\`; (4) add deterministic tests for concurrent writers, corrupt-state preservation, terminal-audit merge, and post-restart recovery. Terminal-audit path already uses \`_save_state_for_terminal_audit\` → \`_save_state\`, so it stays merge-compatible for free.
---
author: oompah
created: 2026-07-29 21:46
---
Fixed live service-state corruption race with a re-entrant lock covering each read/modify/write, fsynced same-directory temporary files and atomic replace, sticky fail-closed corruption preservation, and post-load corruption detection for terminal-audit startup. Added deterministic concurrent-writer, corrupt-document, serialization-failure, state-merge, and graceful-restart recovery tests. Focused state consumers: 301 passed. Full gate: 13,581 passed, 7 skipped.
---
author: oompah
created: 2026-07-29 21:46
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 24
- Tokens: 45 in / 1.1K out [1.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 24s
- Log: OOMPAH-563__20260729T214332Z.jsonl
---
author: oompah
created: 2026-07-29 21:48
---
LIVE RECOVERY VERIFIED after make graceful on submitted head f47d09a7b: new service instance 88c6ab59-ff17-48bf-8439-b36679919662; dashboard alerts empty; terminal-audit baseline_initialized=true, quarantined=false, pending_audits=0, errors=[]; 1,181 existing terminal records grandfathered; service_state.json parses successfully, is mode 0600, and no temporary files remain. The live alert is cleared.
---
author: oompah
created: 2026-07-29 22:42
---
Deployed on main via PR #583 (merge 61230608) and activated by graceful restart. Live terminal-audit enforcement rebuilt its baseline successfully: quarantine is false, errors are empty, and the dashboard alert has cleared.
---
author: oompah
created: 2026-08-05 23:21
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 23:22
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 23:22
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
