---
id: OOMPAH-733
type: task
status: Ready to Integrate
priority: null
title: Fail closed when a nested epic rebase target cannot be resolved
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-03T18:23:48.756544Z'
updated_at: '2026-08-03T19:45:28.299866Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d31efe1048fb2a727e1b2258c28d0d552076e4d24e28ffbc2fbd4061e24f07d0
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T18:26:35.076595+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** OOMPAH-733 is the only active (Open) task in the corpus.\
    \ All other tasks are in terminal Archived state and thus ineligible as duplicate\
    \ targets. Related archived tasks (OOMPAH-162, OOMPAH-163, OOMPAH-165) address\
    \ distinct epic branch routing and validation problems. OOMPAH-733 uniquely targets\
    \ the transient parent lookup failure path and its incorrect fallback to main,\
    \ which is not addressed by any existing task.\nI'll analyze OOMPAH-733 against\
    \ the project task corpus to determine if it's a duplicate of any existing task.\n\
    \n## Analysis\n\n**OOMPAH-733 Summary:**\nThe issue describes a problem where\
    \ nested epic rebase targets are incorrectly resolved to `main` when a transient\
    \ parent lookup failure occurs. The root cause is in `_resolve_epic_target_branch`,\
    \ which treats a failed `_resolve_parent_epic` lookup as proof the epic is top-level\
    \ and silently falls back to `project.default_branch`.\n\n**Key characteristics:**\n\
    - Nested epic with `parent_id` present\n- Transient parent lookup failure\n- Inappropriate\
    \ fallback to main instead of failing closed\n- References OOMPAH-633 (parent-only\
    \ policy) and OOMPAH-731 (direct-maintenance completion)\n\n**Corpus Review:**\n\
    \nScanning the provided task corpus for active (non-terminal) candidates:\n- **OOMPAH-733**\
    \ is the ONLY Open task\n- All other tasks listed are in **Archived** state (terminal)\n\
    \nReviewing related tasks by topic (all Archived):\n- **OOMPAH-162**: Stacked\
    \ child landing when merged to default branch \u2014 addresses different symptom\
    \ (merged-to-default behavior)\n- **OOMPAH-163**: Generated epic target branches\
    \ through dispatch \u2014 addresses branch allowlist bypass, not parent resolution\n\
    - **OOMPAH-165**: Shared epic landed detection before main merge \u2014 addresses\
    \ verifying merged PR target matches epic's resolved branch, not parent lookup\
    \ failure\n\n**Distinction from related tasks:**\nThese archived tasks handle\
    \ epic branch routing and validation, but none address the specific problem OOMPAH-733\
    \ targets: **transient parent epic resolution failure causing inappropriate main-branch\
    \ substitution**. OOMPAH-733 focuses on fail-closed error handling for parent\
    \ lookup, not the consequences of an already-wrong target.\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** OOMPAH-733 is the only active (Open) task in the corpus.\
    \ All other tasks are in terminal Archived state and thus i"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: f0a0e3e6-1ceb-4efc-9fe5-38e09092eb10
oompah.task_costs:
  total_input_tokens: 13
  total_output_tokens: 2018
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1711
      cost_usd: 0.0
    sonnet:
      input_tokens: 3
      output_tokens: 307
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1711
    cost_usd: 0.0
    recorded_at: '2026-08-03T18:26:35.074433+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 3
    output_tokens: 307
    cost_usd: 0.0
    recorded_at: '2026-08-03T19:37:53.542868+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-733__20260803T182536Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-733
    source_sha: a7fc6676c44d6c88cf9a955002d51454929a2b20
    completed_at: '2026-08-03T18:26:35.114601+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-733
  head_sha: daefb6fb2dc282879d20c84e4d18015c250a6635
  submitted_at: '2026-08-03T19:37:09.725945+00:00'
  updated_at: '2026-08-03T19:37:09.725945+00:00'
---
## Summary

Live reproduction: EXOCOMP-245 was auto-filed as Rebase epic-EXOCOMP-135 onto main even though EXOCOMP-135 is a nested epic whose authoritative synchronization target is epic-EXOCOMP-127. The worker successfully force-pushed a main-based rebase, but the parent branch contains required exact prerequisite ancestry that main does not, so the Ready queue remains unclaimable. OOMPAH-633 allows nested-parent queue repair only when the target is the resolved authoritative parent; however, _resolve_epic_target_branch treats a transient _resolve_parent_epic lookup failure as proof that the epic is top-level and silently falls back to project.default_branch. Implementation scope: distinguish confirmed top-level epics from failed or incomplete parent resolution; when parent_id is present, resolve the parent from a canonical project snapshot or fail closed with a retryable diagnostic, never substitute main. Carry the resolved target branch as durable evidence into rebase-task creation, dispatch, prompt/workspace routing, completion, restart recovery, and dashboard diagnostics. Reject or supersede an existing active helper whose recorded target no longer matches the authoritative parent, without racing a worker or deleting recovery refs. Preserve the OOMPAH-633 parent-only policy, cooldown and duplicate fencing, exact force-with-lease behavior, and direct-maintenance completion from OOMPAH-731. Relevant code: _resolve_parent_epic, _resolve_epic_target_branch, nested integration-queue staleness repair, proactive rebase filing, helper task classification/prompting, and epic rebase state persistence. Required tests: reproduce a nested epic with parent_id where fetch_issue_detail transiently fails and assert no main-target helper is filed or dispatched; recover the parent lookup and assert exactly one helper targets origin/epic-parent; cover restart between failed lookup and recovery, stale wrong-target helper replacement, parent deletion or malformed metadata, true top-level epic main target, and unrelated epic denial. Run focused parallel-epic, epic-strategy, rebase maintenance, restart, and queue tests plus make test. Acceptance criteria: nested epic synchronization never mutates against main solely because parent lookup failed; EXOCOMP-245-style repairs converge on the authoritative parent target; ambiguous hierarchy remains retryable and visible without stranding Ready rows.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 18:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 18:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 18:26
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 4s
- Log: OOMPAH-733__20260803T182536Z.jsonl
---
author: oompah
created: 2026-08-03 18:27
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 18:27
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-03 18:28
---
Understanding: nested epic target resolution must distinguish confirmed top-level epics from failed parent lookup; I will trace helper filing, dispatch, persistence, restart, and diagnostics, then fail closed with retryable evidence and regression tests.
---
author: oompah
created: 2026-08-03 18:32
---
Additional live evidence: after successful nested-parent synchronization, the runtime epic_rebase_states map was empty but EXOCOMP-130, EXOCOMP-132, and EXOCOMP-135 still retained rebase-requested and epic:rebasing labels. _check_epic_staleness clears the alert and immediately continues for epic-* targets, so it never proves parent reachability and transitions nested REBASING to REBASED or clears the durable labels. Extend the fix and tests to reconcile nested rebase state after the authoritative parent becomes an ancestor, including restart when only labels remain. Labels must clear only after exact local/remote/parent reachability is proven; failed or ambiguous sync must stay actionable.
---
author: oompah
created: 2026-08-03 18:46
---
Verification: focused epic-strategy, epic-rebase-state, parallel-epic-children, and YOLO suites pass: 328 passed in 107.26s. The new regressions cover transient nested parent lookup, recovery to exactly one parent-target helper, malformed/deleted parent metadata, restart-style deduplication, wrong-target supersession without worktree cleanup, and retryable dashboard alerts.
---
author: oompah
created: 2026-08-03 18:54
---
Verification update: after tightening helper dispatch/workspace routing, the full focused suites pass at 329 passed in 100.14s. make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-733'
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-733' was retried twice but could not enter its setup phase because astral-uv failed with DBus InvalidArgs (kernel-thread transient-scope error); no project tests ran through Make.
---
author: oompah
created: 2026-08-03 18:55
---
Verification: directly affected integration-queue, conflict-repair, restart API, and event-loop recovery suites also pass: 87 passed in 32.42s. The only unavailable check is the Makefile gate setup, which is blocked by the environment's astral-uv/DBus transient-scope failure before pytest starts.
---
author: oompah
created: 2026-08-03 19:01
---
Verification complete: final affected-suite run passed 417 tests in 211.62s, covering epic strategy/rebase state, parallel epic queue repair, YOLO conflict handling, integration queue, conflict repair, restart API, and event-loop recovery. make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-733'
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-733' remains environment-blocked during uv setup by the DBus transient-scope error documented above.
---
author: oompah
created: 2026-08-03 19:01
---
Implementation update: added a final pre-worker target fence. Epic rebase helpers now re-resolve their parent target during dispatch and workspace creation, persist refreshed target metadata, and are rejected/superseded before mutation when hierarchy is unavailable or the recorded target is stale. Restart/state/dashboard and prompt/workflow target evidence are covered.
---
author: oompah
created: 2026-08-03 19:02
---
Fail-closed nested epic target resolution with durable parent-target evidence, helper fencing, restart recovery, and regression coverage.
---
author: oompah
created: 2026-08-03 19:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 150
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 35m 19s
- Log: OOMPAH-733__20260803T182726Z.jsonl
---
author: oompah
created: 2026-08-03 19:25
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-733`
Target: `main`
Head: `e08f2db26d7f1dc48ab85effb89b1f4bd80720e0`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
ERROR: oompah/orchestrator.py:12767:13: Orchestrator._supersede_wrong_epic_rebase_helper calls update_issue() for Archived
  Route the transition through TerminalTransitionCoordinator or document an exact allowlist entry in oompah/terminal_mutation_scanner.py.
Found 1 unauthorized terminal mutation(s).
make: *** [Makefile:410: terminal-audit-scan] Error 1
```
---
author: oompah
created: 2026-08-03 19:26
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-03 19:26
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-03 19:27
---
Understanding: CI gate failed with terminal-audit-scan error. `_supersede_wrong_epic_rebase_helper` in orchestrator.py calls `update_issue()` for `Archived` state (line 12767) without routing through `TerminalTransitionCoordinator` or being documented in the allowlist in `terminal_mutation_scanner.py`. Fix: either route the call through TerminalTransitionCoordinator or add an allowlist entry. Reading the code now to determine the minimal correct fix.
---
author: oompah
created: 2026-08-03 19:30
---
Discovery: The CI failure is a terminal-audit-scan error. \`_supersede_wrong_epic_rebase_helper\` in orchestrator.py (line 12767) calls \`update_issue(identifier, status=ARCHIVED)\` directly without routing through TerminalTransitionCoordinator or being in the allowlist. The fix is to add an allowlist entry in \`terminal_mutation_scanner.py\` — this is an internal rebase helper task archival (not a user task), has worker-race guards (checks running/claimed state), and the terminal enforcement sweep still provides the audit backstop.
---
author: oompah
created: 2026-08-03 19:36
---
Implementation: Added allowlist entry in terminal_mutation_scanner.py for Orchestrator._supersede_wrong_epic_rebase_helper. The function archives auto-generated rebase helper tasks with stale targets; it has guards against racing workers (checks running/claimed state, re-reads from tracker), only operates on tasks in Open/In-Progress/Needs-Rebase states, and the terminal enforcement sweep still provides the audit backstop. Terminal-audit-scan now reports 8 identified, 8 explicitly allowlisted.
---
author: oompah
created: 2026-08-03 19:36
---
Verification: terminal-audit-scan passes (8 identified, 8 explicitly allowlisted). test_terminal_audit_scanner.py: 15 passed. Epic strategy/rebase state/parallel epic suites: 306 passed in 90.65s. Branch pushed to origin/OOMPAH-733 at daefb6fb2.
---
author: oompah
created: 2026-08-03 19:37
---
Fixed terminal-audit-scan CI failure by adding an allowlist entry in terminal_mutation_scanner.py for Orchestrator._supersede_wrong_epic_rebase_helper. This function archives stale wrong-target rebase helper tasks; it has worker-race guards and the terminal enforcement sweep provides the audit backstop. The scan now shows 8 identified, 8 explicitly allowlisted. All focused suites pass.
---
author: oompah
created: 2026-08-03 19:37
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Claude/sonnet]
- Turns: 46, Tool calls: 29
- Tokens: 3 in / 307 out [310 total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 49s
- Log: OOMPAH-733__20260803T192611Z.jsonl
---
author: oompah
created: 2026-08-03 19:45
---
Branch quality gate passed for `daefb6fb2dc282879d20c84e4d18015c250a6635` using `make test` in 415.9s. Review creation may proceed.
---
<!-- COMMENTS:END -->
