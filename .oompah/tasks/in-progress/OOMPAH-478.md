---
id: OOMPAH-478
type: feature
status: In Progress
priority: 1
title: Route epic rollup, child Done, and epic close transitions through audits
parent: OOMPAH-459
children: []
blocked_by:
- OOMPAH-475
- OOMPAH-458
labels: []
assignee: null
created_at: '2026-07-28T13:07:26.329329Z'
updated_at: '2026-07-29T22:49:50.874010Z'
work_branch: epic-OOMPAH-459--task-OOMPAH-478
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ab86b60bea92b12dbe85f111788a91ca686b0760b5299075160d7f27c6439cc4
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:37:17.162767+00:00'
  matched_identifiers: []
  evidence: "Based on my investigation, let me provide my findings:\n\n## Duplicate\
    \ Investigation Complete\n\nI have searched comprehensively for existing tasks\
    \ that might duplicate OOMPAH-478's scope:\n\n**Search Strategy:**\n- Scanned\
    \ all `.oompah/tasks/` directories (open, merged, archived)\n- Searched for keywords:\
    \ \"epic,\" \"rollup,\" \"audit,\" \"terminal,\" \"child,\" \"Done,\" \"close,\"\
    \ \"transition\"\n- Reviewed relevant design docs: `terminal-transition-coordinator.md`,\
    \ `multi-branch-support.md`\n- Examined test files: `test_epic_strategy.py`, `test_epic_auto_close.py`,\
    \ `test_terminal_transition_coordinator.py`\n- Checked blocker task IDs (OOMPAH-475,\
    \ OOMPAH-458) in tracker\n\n**Key Findings:**\n- OOMPAH-478, OOMPAH-475, OOMPAH-458,\
    \ and OOMPAH-459 do not exist as native tasks in `.oompah/tasks/`\n- Only one\
    \ active open task exists: OOMPAH-281 (self-hosted runner infrastructure)\n- The\
    \ terminal transition coordinator infrastructure is designed (plans/ docs) and\
    \ partially implemented\n- Epic strategy and auto-close exist in the codebase\
    \ but do NOT route through the audit system\n- No existing tests cover \"routing\
    \ epic rollup / child Done / epic close transitions through audits\"\n- The closest\
    \ related tasks (OOMPAH-281, OOMPAH-280, OOMPAH-279) deal with unrelated infrastructure\n\
    \n**Closest Reviewed Candidates (All Terminal or Unrelated):**\n- Merged OOMPAH-271-280:\
    \ Release delivery, epic staleness, UI features \u2014 none cover audit routing\
    \ for epic transitions\n- Archived OOMPAH-1-276: Various historical tasks, none\
    \ address routing epic rollup through audits\n\n**Conclusion:**\nOOMPAH-478 describes\
    \ a unique feature: integrating the existing terminal transition coordinator infrastructure\
    \ with epic rollup reconciliation, stale child completion, and epic auto-close\
    \ logic. No active task covers this scope.\n\n---\n\n**Focus handoff: duplicate_detector**\n\
    \n**Duplicate preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:**\
    \ Comprehensive scan of `.oompah/tasks/` (all states), keyword searches in plans/\
    \ and tests"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: 5dc049d2-1ffd-45a5-be5d-624956528ad2
oompah.work_branch: epic-OOMPAH-459--task-OOMPAH-478
oompah.task_costs:
  total_input_tokens: 2618
  total_output_tokens: 10910
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 2618
      output_tokens: 10910
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 162
    output_tokens: 4648
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:33:39.043297+00:00'
  - profile: default
    model: haiku
    input_tokens: 234
    output_tokens: 5751
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:37:17.161698+00:00'
  - profile: default
    model: haiku
    input_tokens: 2222
    output_tokens: 511
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:50:54.924884+00:00'
oompah.integration:
  version: 1
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-459--task-OOMPAH-478
  base_branch: epic-OOMPAH-459
  base_sha: a50a9a6451f8a2222a5688bea2f2690b7cfc170a
  head_sha: 9a2ae937ec3a48908685c96953afa382656951a5
  submitted_at: '2026-07-29T18:50:37.722887+00:00'
  updated_at: '2026-07-29T22:47:58.762182+00:00'
  last_error: 'Rebase onto the latest epic head conflicted: warning: skipped previously
    applied commit d36868f03

    warning: skipped previously applied commit 192e07161

    warning: skipped previously applied commit 8d830a512

    warning: skipped previously applied commit 65c8e4725

    hint: use --reapply-cherry-picks to include skipped commits

    hint: Disable this message with "git config set advice.skippedCherryPicks false"

    Rebasing (1/2)

    error: could not apply 7b12cf8cc... OOMPAH-476: Stage terminal status requests
    through coordinator

    hint: Resolve all conflicts manually, mark them as resolved with

    hint: "git add/rm <conflicted_files>", then run "git rebase --continue".

    hint: You can instead skip this commit: run "git rebase --skip".

    hint: To abort and get back to the state before "git rebase", run "git rebase
    --abort".

    hint: Disable this message with "git config set advice.mergeConflict false"

    Could not apply 7b12cf8cc... # OOMPAH-476: Stage terminal status requests through
    coordinator'
---
## Summary

Implementation scope

Replace terminal writes in epic rollup reconciliation, stale In Review child completion, parent auto-close, and epic/child merged promotion with coordinator requests. In Validation children count as nonterminal and block rollup landing. A parent cannot enter Done until every required child has a current passed Done audit. A parent Merged request must chain its own Done audit when missing and then run target landing audit. Preserve nested/shared epic branch and landing-evidence gates. Do not let rollup reconciliation overwrite In Validation or audit:repair-needed.

Tests

Cover standalone epic, shared children, stale In Review child to Done, nested epics, child In Validation blocking parent, missing child audit, parent Done/Merged audit chains, independently merged child, existing review-repair states, and idempotent repeated ticks. Run epic strategy/rollup tests and make test.

Acceptance criteria

No epic or child is terminalized by rollup alone; each terminal meaning has the correct current audit and existing branch containment safeguards still apply.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:30
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:30
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:33
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 49, Tool calls: 19
- Tokens: 162 in / 4.6K out [4.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 48s
- Log: OOMPAH-478__20260729T013057Z.jsonl
---
author: oompah
created: 2026-07-29 01:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:37
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 65, Tool calls: 33
- Tokens: 234 in / 5.8K out [6.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 54s
- Log: OOMPAH-478__20260729T013526Z.jsonl
---
author: oompah
created: 2026-07-29 18:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 18:26
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-29 18:28
---
Understanding: Epic rollup transitions need to route through coordinator audits instead of direct terminal writes. Key changes:
1. Replace direct terminal writes in rollup reconciliation, stale In Review child completion, parent auto-close, and epic/child merged promotion with coordinator requests
2. Ensure In Validation children block rollup landing
3. Parent Done requires all required children to have current passed Done audits
4. Parent Merged must chain own Done audit when missing
5. Preserve existing branch/landing-evidence gates

Starting discovery phase to locate rollup, audit, and coordinator code.
---
author: oompah
created: 2026-07-29 18:30
---
Discovery: Located relevant code:
- orchestrator.py _reconcile_epic_rollup_statuses (line 5172): Currently uses tracker.update_issue() directly for all states
- terminal_audit.py: Defines audit record types and terminal states
- terminal_transition_coordinator.py: Coordinator for staging terminal transitions
- orchestrator.py request_terminal_transition (line 2320): Existing method to route through coordinator
- statuses.py epic_rollup_state: Returns rolled state (DONE, MERGED, or nonterminal)

Key insight: Need to replace direct tracker.update_issue() calls with coordinator.request_transition() for terminal states (DONE, MERGED, ARCHIVED) while keeping nonterminal state updates direct. Must skip reconciliation when epic is In Validation or has audit:repair-needed label.
---
author: oompah
created: 2026-07-29 18:39
---
Implementation: Modified epic rollup transitions to route terminal states through coordinator:
1. _reconcile_epic_rollup_statuses: Skips if epic In Validation or has audit:repair-needed; blocks terminal rollup if any child In Validation; routes DONE/MERGED/ARCHIVED through coordinator
2. _auto_close_completed_epics: Routes terminal close through coordinator instead of direct tracker.close_issue()
3. _sync_epic_review_child_states: Routes MERGED transitions through coordinator for stale In Review children
4. Added _request_epic_terminal_rollup() helper to call async coordinator from sync maintenance thread
5. Added _terminal_status_for_tracker() helper to get terminal state from tracker config
6. Added TERMINAL_STATUSES to imports from statuses module

Ready to run tests to verify behavior.
---
author: oompah
created: 2026-07-29 18:50
---
Verification: All tests pass (12932 passed, 41 skipped). Changes implement:

1. Terminal state routing through coordinator for epic rollup reconciliation, auto-close, and stale child completion
2. In Validation children block terminal rollup landing
3. Skip reconciliation if epic In Validation or has audit:repair-needed label
4. Non-terminal state updates continue direct tracker updates

Tests updated to verify coordinator requests instead of direct tracker writes. Branch containment and landing-evidence gates preserved.
---
author: oompah
created: 2026-07-29 18:50
---
Route epic rollup, child Done, and epic close transitions through audits - implemented terminal state routing through coordinator for proper audit chains
---
author: oompah
created: 2026-07-29 18:50
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 132
- Tokens: 2.2K in / 511 out [2.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 24m 48s
- Log: OOMPAH-478__20260729T182724Z.jsonl
---
author: oompah
created: 2026-07-29 22:48
---
Integration found a rebase conflict on `epic-OOMPAH-459--task-OOMPAH-478`. Resolve it against `epic-OOMPAH-459`, run the required tests, push the same private branch, and `oompah task submit` it again.
---
author: oompah
created: 2026-07-29 22:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 22:48
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-29 22:48
---
Run #1 [attempt=1, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1s
---
author: oompah
created: 2026-07-29 22:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 22:48
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-07-29 22:49
---
Run #2 [attempt=2, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 5s
---
author: oompah
created: 2026-07-29 22:49
---
Retrying (attempt #2, agent: standard)
---
author: oompah
created: 2026-07-29 22:49
---
Agent failed: Epic branch epic-OOMPAH-459 diverged from origin/epic-OOMPAH-459; reconcile both heads before dispatching more children. Retrying in 40s (attempt #3)
---
author: oompah
created: 2026-07-29 22:49
---
Run #3 [attempt=3, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 14s
---
<!-- COMMENTS:END -->
