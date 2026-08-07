---
id: OOMPAH-871
type: bug
status: In Progress
priority: 1
title: Prevent provenance-only terminal tasks from watchdog reopen and redispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:24:14.554398Z'
updated_at: '2026-08-07T08:42:38.870465Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d5315e2b5150ac71c464336b3c712f7ea42c50006472f8171c1b4fe8b0d3179d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T07:20:47.816766+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-871 is a novel follow-up bug triggered by OOMPAH-576\
    \ (post-merge) that requires new architectural changes to persist \"provenance-only\"\
    \ state and prevent watchdog from redispatching terminal tasks. The closest archived\
    \ tasks (OOMPAH-160, OOMPAH-212, OOMPAH-219) address related domains (atomic writes,\
    \ duplicate records, commit races) but do not cover provenance-only suppression\
    \ or watchdog reopen prevention. No active task in the corpus describes this problem.\n\
    Looking at OOMPAH-871 and the supplied task corpus, I need to determine whether\
    \ this is a duplicate of an existing active task.\n\n**Issue Summary:**\nOOMPAH-871\
    \ describes a bug where a task retained solely as terminal provenance (after being\
    \ merged) is later reopened and redispatched by the watchdog. The fix requires\
    \ defining and persisting an authoritative \"provenance-only\" or \"terminal-suppression\"\
    \ state that watchdog, reconciliation, dependency rollup, and restart recovery\
    \ all honor.\n\n**Corpus Analysis:**\nI've reviewed all 33 included similarity\
    \ candidates plus the current task. Examining the closest topically-related archived\
    \ tasks:\n\n1. **OOMPAH-160** (Archived) - \"Make native task writes atomic and\
    \ block intake reimports for corrupt tasks\" - Focuses on atomic writes and preventing\
    \ duplicate task reimports due to corruption, not on provenance-only state or\
    \ watchdog reopen prevention.\n\n2. **OOMPAH-212** (Archived) - \"Prevent duplicate\
    \ native task records from appearing on the board\" - Addresses duplicate task\
    \ records in the board view, not watchdog reopening of provenance-only tasks.\n\
    \n3. **OOMPAH-219** (Archived) - \"Detect shared-worktree commits that absorb\
    \ another task's changes\" - Handles shared worktree commit races and stale incomplete-session\
    \ state, not provenance-only suppression.\n\nAll remaining tasks in the corpus\
    \ are unrelated (epic strategies, release addendums, docs, etc.).\n\n**Key Distinction:**\n\
    OOMPAH-871 is explicitly triggered by OOMPAH-576 (mentioned in the description),\
    \ implying 576 was already completed. This is a follow-up bug discovered after\
    \ that implementation merged\u2014not a re-filing of the same issue. The problem\
    \ is specifically about **preventing watchdog from reopening tasks retained only\
    \ as provenance**, which requires new state-persistence and dispatch-eligibility\
    \ logic not covered by any existing task.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-871\
    \ is a novel follow-u"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d8095cec-228b-4530-bc47-7e9a9f470921
oompah.task_costs:
  total_input_tokens: 289
  total_output_tokens: 9006
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 40
      output_tokens: 1745
      cost_usd: 0.0
    opus:
      input_tokens: 249
      output_tokens: 7261
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1736
    cost_usd: 0.0
    recorded_at: '2026-08-07T07:20:47.801719+00:00'
  - profile: default
    model: haiku
    input_tokens: 30
    output_tokens: 9
    cost_usd: 0.0
    recorded_at: '2026-08-07T07:29:19.336540+00:00'
  - profile: deep
    model: opus
    input_tokens: 224
    output_tokens: 6538
    cost_usd: 0.0
    recorded_at: '2026-08-07T08:31:11.779630+00:00'
  - profile: deep
    model: opus
    input_tokens: 25
    output_tokens: 723
    cost_usd: 0.0
    recorded_at: '2026-08-07T08:41:17.601591+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-871__20260807T071552Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-871
    source_sha: 45e2b83356dd041200d7cad0970c7e6f939dc757
    completed_at: '2026-08-07T07:20:47.824750+00:00'
---
## Summary

Triggered by: OOMPAH-576

Reproduce OOMPAH-576 after its original implementation merged and an operator explicitly retained the record only as terminal provenance. A watchdog later reopened and redispatched the task, causing a new documentation-only accepted head and another full validation/review cycle. Define and persist an authoritative provenance-only or terminal-suppression state that every watchdog, reconciliation path, dependency rollup, and restart recovery honors. Relevant code: watchdog task reconciliation, terminal-state evidence, archived/provenance metadata, dispatch eligibility, restart recovery. Required tests: terminal provenance records remain non-dispatchable across repeated watchdog ticks and service restart; legitimate owner-requested revision creates a new authority generation and can dispatch; stale branch or historical review observations cannot reopen the record; alerts explain malformed provenance metadata without mutating status. Acceptance: a task retained solely as merged/archived provenance cannot re-enter a dispatchable or validation state unless a project owner explicitly starts a new revision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 07:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 07:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 07:20
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 40s
- Log: OOMPAH-871__20260807T071552Z.jsonl
---
author: oompah
created: 2026-08-07 07:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 07:25
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 07:29
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 1
- Tokens: 30 in / 9 out [39 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 38s
- Log: OOMPAH-871__20260807T072559Z.jsonl
---
author: oompah
created: 2026-08-07 07:30
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-07 07:30
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 07:48
---
**Understanding**: The scenario is a terminal task (Done/Merged/Archived) that an operator has retained *purely as provenance* — a historical record — but does not want the system to treat as active work. A watchdog observed some stale/historical signal and reopened it, causing another full validation/review cycle.

**Planned approach**:
1. Introduce a durable 'provenance-only' (a.k.a. terminal-suppression) marker persisted in the terminal-audit metadata envelope (\`oompah.terminal_audit\`). Store it via the same TerminalAuditMetadataStore that already owns quarantine — same lock discipline, same redaction. Marker is set only by an explicit operator/owner action and cleared only by an explicit owner-authorized new revision.
2. Every dispatch/reopen/reconcile path checks the marker before mutating status. Specifically: stalled-task watchdog reopen (\`_execute_stalled_watchdog_reopen_under_authority\`), review reconciliation reopen (\`_reopen_missing_review\`, \`_reopen_stale_in_review_task\`), shared-absorption reopen, epic child reopen, dispatch eligibility (\`_should_dispatch\`), auto-archive skip guard, restart recovery.
3. Owner-initiated 'new revision' explicitly clears the marker and bumps an authority generation. This is the only path that returns the task to a dispatchable state.
4. Malformed provenance metadata is quarantined (existing MetadataQuarantine path) and surfaces an operator alert — never silently mutates status.
5. Tests: watchdog ticks + restart recovery leave the record non-dispatchable; owner-authored revision creates a new authority generation; stale branch/review observations cannot reopen; malformed metadata does not mutate status.
---
author: oompah
created: 2026-08-07 08:12
---
**Discovery**: The critical reopen path for a Merged/Archived-provenance-only task is \`_reconcile_terminal_open_reviews\` in \`oompah/orchestrator.py:23393\` — it observes a cached open review and demotes a Merged task to \`In Review\`/\`Needs CI Fix\`/\`Needs Rebase\`. This is exactly the 'documentation-only accepted head and another full validation/review cycle' the bug describes.

Additional reopen paths that need fencing: \`_execute_stalled_watchdog_reopen_locked\`, \`_reopen_stale_in_review_task\`, dispatch eligibility in \`_should_dispatch\`. The shared-worktree absorption reopen already skips terminal state so it inherits the fence.

Design: persist a durable \`ProvenanceSuppression\` marker inside the existing \`TerminalAuditMetadata\` envelope under key \`oompah.terminal_provenance_suppression\`. This inherits the metadata store's project write lock, quarantine handling, and redaction rules. The marker carries a monotonically increasing \`authority_generation\` bumped only by \`authorize_new_revision(actor, reason)\` — this is the only path that returns a suppressed record to a dispatchable state and survives service restart naturally because the marker is tracker-durable.

**Implementation**: Added new module \`oompah/provenance_suppression.py\` with pure logic. Integrated into the orchestrator at four sites: \`_reconcile_terminal_open_reviews\`, \`_reopen_stale_in_review_task\`, \`_execute_stalled_watchdog_reopen_locked\`, and \`_should_dispatch\`. The fence emits an operator log line on suppression and an alert-severity log for malformed markers, and never mutates status in either case.
---
author: oompah
created: 2026-08-07 08:12
---
Independent early review (while implementation remains in progress): the current durable-marker diff is not yet acceptance-complete. No reachable owner-authorized API/CLI/transition path currently invokes mark_provenance_only or authorize_new_revision, so suppression cannot be set or explicitly cleared. Current fences cover dispatch/watchdog and two review reconciliations, but not shared-absorption, epic-child rollup, restart recovery, or auto-archive paths. These are blocking if still absent at the frozen head; please either cover the required transition surfaces with tests or document and prove why they cannot reopen provenance-only work.
---
author: oompah
created: 2026-08-07 08:14
---
Independent review follow-up: current draft remains REJECT until these are resolved: (1) mark/authorize helpers merely accept a caller-supplied ContributorIdentity and do not bind to authenticated project-owner authority; (2) autonomous restart recovery, shared absorption, late review handoff, close/unpushed/integration gates, and merge-conflict/CI escalations can still mutate provenance-only terminal work before _should_dispatch; (3) tests must exercise real orchestrator/restart calls, not marker models only; (4) unsupported marker version currently interpolates raw metadata into ProvenanceSuppressionError, so malformed-marker alert text can leak attacker-controlled/sensitive payload. Use an auth-bound reachable entry point, a central fenced status-transition boundary or complete coverage of reopeners, and sanitized structural errors.
---
author: oompah
created: 2026-08-07 08:31
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/opus]
- Turns: 214, Tool calls: 158
- Tokens: 224 in / 6.5K out [6.8K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 1m 7s
- Log: OOMPAH-871__20260807T073021Z.jsonl
---
author: oompah
created: 2026-08-07 08:31
---
Issue has failed 2 time(s). Attempting auto-decomposition into smaller tasks.
---
author: oompah
created: 2026-08-07 08:31
---
Auto-decomposition failed: No provider configured for decomposition. Falling back to normal retry.
---
author: oompah
created: 2026-08-07 08:33
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-08-07 08:33
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 08:41
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 11
- Tokens: 25 in / 723 out [748 total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 4s
- Log: OOMPAH-871__20260807T083334Z.jsonl
---
<!-- COMMENTS:END -->
