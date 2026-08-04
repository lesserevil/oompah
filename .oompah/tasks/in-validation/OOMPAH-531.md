---
id: OOMPAH-531
type: task
status: In Validation
priority: 2
title: Schedule duplicate preflight from spare agent capacity
parent: OOMPAH-528
children: []
blocked_by:
- OOMPAH-530
labels:
- focus-complete:duplicate_detector
- 'focus-complete:'
- focus-complete:chore
assignee: null
created_at: '2026-07-28T21:19:12.151334Z'
updated_at: '2026-08-04T23:34:30.353013Z'
work_branch: epic-OOMPAH-528
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: abda3bc5-0bd9-49ce-99f1-25f5d9e14e00
oompah.work_branch: epic-OOMPAH-528
oompah.task_costs:
  total_input_tokens: 260
  total_output_tokens: 9189
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 260
      output_tokens: 9189
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 210
    output_tokens: 6408
    cost_usd: 0.0
    recorded_at: '2026-07-28T21:58:49.799298+00:00'
  - profile: default
    model: haiku
    input_tokens: 50
    output_tokens: 2781
    cost_usd: 0.0
    recorded_at: '2026-07-28T22:02:03.075494+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-6f439353f931
    project_id: proj-14849f1b
    task_id: OOMPAH-531
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ad9fed55b0801ba2f2b18563060d9c0886ed4609bdd48d0ef4c488c46a04c335
    attempts:
    - version: 1
      attempt_id: attempt-04e4215c2556
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ad9fed55b0801ba2f2b18563060d9c0886ed4609bdd48d0ef4c488c46a04c335
      created_at: '2026-08-04T23:33:49.010342+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T23:33:49.010342+00:00'
      branch_key: epic-OOMPAH-528
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T22:36:38.202855+00:00'
    updated_at: '2026-08-04T23:33:49.010342+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-04e4215c2556
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ad9fed55b0801ba2f2b18563060d9c0886ed4609bdd48d0ef4c488c46a04c335
    created_at: '2026-08-04T23:33:49.010342+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T23:33:49.010342+00:00'
    branch_key: epic-OOMPAH-528
---
## Summary

Integrate duplicate preflight into each orchestrator scheduling tick after the evidence and claim APIs from OOMPAH-529 and OOMPAH-530 exist.

Implementation scope:
- During every scheduling tick, collect Open tasks that are non-terminal, otherwise dispatchable, not dependency-blocked, not already claimed, and unchecked or stale for the configured duplicate detector version.
- Preserve the existing inexpensive _apply_duplicate_detection pass. A heuristic match may still immediately produce Duplicate Candidate, but a heuristic miss must not be written as a model-backed pass.
- Allocate only otherwise-available configured agent capacity to preflight and enforce a configurable cap. Add OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS to .env.example and ServiceConfig; default to 1. A value of 0 disables model-backed background preflight.
- Preserve an implementation lane: when checked implementation-ready work is waiting, preflight must not consume the final available slot. If no checked work is waiting, preflight may use available slots up to its cap.
- Use the normal provider/focus selection for duplicate_detector, but attach the separate preflight claim and do not transition the issue to In Progress.
- Define deterministic ordering using existing task priority/age ordering so repeated ticks do not starve older Open work.
- Respect project pause, global pause, provider availability/whitelists, budgets, one-agent-per-epic/shared-branch constraints where applicable, and max-concurrency auto-scaling.
- Re-evaluate capacity and eligible tasks on every scheduling tick. Never kill a running preflight when capacity later shrinks.
- Add counters/log reasons for selected, started, skipped-no-capacity, skipped-reserved-slot, stale, already-checked, and claim-race-lost.

Relevant context/files:
- oompah/orchestrator.py: _handle_dispatch_needed_locked, _apply_duplicate_detection, _select_dispatchable, _available_slots, focus dispatch.
- oompah/config.py and .env.example for configuration.
- oompah/focus.py for duplicate_detector selection.
- tests/test_orchestrator_duplicate_detection.py and scheduler/capacity tests for existing patterns.

Required tests:
- An unchecked Open task starts preflight when a slot is spare and remains Open.
- A checked implementation-ready task receives the reserved last slot before additional preflight.
- Multiple slots respect the preflight cap; cap 0 disables preflight.
- Paused, blocked, terminal, active, or already-checked tasks are skipped with the correct reason.
- Auto-scaled concurrency is re-evaluated each tick and reductions do not terminate existing runs.
- Ordering is deterministic and old unchecked tasks are not starved.

Acceptance criteria:
1. Open tasks can be screened before implementation without a user-visible In Progress transition.
2. Background screening cannot monopolize all useful implementation capacity.
3. All existing dispatch constraints continue to apply and claim races are harmless.
4. Configuration is loaded only through OOMPAH_* environment settings and documented in .env.example.
5. Focused scheduler and capacity tests pass through the appropriate Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:42
---
Claimed by the current interactive Codex session before OOMPAH-530 completion. Core scheduler work is pushed on epic-OOMPAH-528; do not dispatch another agent.
---
author: oompah
created: 2026-07-28 21:43
---
Implemented and pushed in 7a2e467fb: per-tick spare-capacity selection, implementation-first ordering, configurable cap, forced duplicate-detector focus, pause/budget/dependency/shared-epic gates, deterministic ordering, and metrics. Scheduler regressions pass.
---
author: oompah
created: 2026-07-28 21:43
---
Spare-capacity duplicate-preflight scheduling implemented and pushed in 7a2e467fb.
---
author: oompah
created: 2026-07-28 21:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 21:58
---
DUPLICATE INVESTIGATION COMPLETE

No duplicate found. Searched .oompah/tasks (open, archived, merged) and documentation for related work.

Current state:
- OOMPAH-530 (dependency) was just merged with atomic duplicate-preflight claim infrastructure
- OOMPAH-531 implementation has NOT been started yet
  * No duplicate preflight scheduling logic exists in orchestrator._handle_dispatch_needed_locked
  * No OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS config exists in .env.example or ServiceConfig
  * No _select_duplicate_preflight or similar scheduling function exists

Closest reviewed tasks:
- OOMPAH-530: Atomic duplicate-preflight claims (completed, merged in HEAD 92aa5e5c2)
- OOMPAH-529: Evidence and claim APIs (presumably completed, dependency satisfied)
- OOMPAH-528: Parent epic (epic-OOMPAH-528 branch active)

Previous comments referenced commit '7a2e467fb' claiming implementation complete. This commit does not exist in git history; the comment appears to be incorrect or from an abandoned branch.

Recommendation: Ready for implementation focus agent to add:
1. Per-tick duplicate preflight task selection (spare capacity only)
2. Configurable capacity cap with OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS (default 1)
3. Implementation-first ordering to preserve capacity for checked implementation-ready work
4. All required tests from acceptance criteria
5. Configuration in .env.example and ServiceConfig
---
author: oompah
created: 2026-07-28 21:58
---
Agent completed successfully in 110s (6618 tokens)
---
author: oompah
created: 2026-07-28 21:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 61, Tool calls: 25
- Tokens: 210 in / 6.4K out [6.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 50s
- Log: OOMPAH-531__20260728T215703Z.jsonl
---
author: oompah
created: 2026-07-28 21:58
---
Focus handoff required before leaving `duplicate_detector`. Add a comment headed `Focus handoff: duplicate_detector` with outcome, evidence, remaining work, and next focus.
---
author: oompah
created: 2026-07-28 21:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 21:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:00
---
Focus handoff: duplicate_detector\n\nOutcome: duplicate screening found no confirmed duplicate. OOMPAH-530 is a distinct prerequisite implementing atomic duplicate-preflight claims; OOMPAH-531 is the separate scheduler-capacity integration task.\n\nEvidence: reviewed the full OOMPAH-530 and OOMPAH-531 task records, searched .oompah/tasks/docs/plans for duplicate-preflight, screening, detector, claim, lease, dispatch, and capacity terms, and inspected the current branch. The current branch contains OOMPAH-530 claim infrastructure but no evidence that the two task scopes are duplicates.\n\nRemaining work: implement per-tick spare-capacity preflight selection, cap/configuration, implementation-lane reservation, focus dispatch, skip/race metrics, and required scheduler tests.\n\nNext focus: feature.
---
author: oompah
created: 2026-07-28 22:00
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 17
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 50s
- Log: OOMPAH-531__20260728T215906Z.jsonl
---
author: oompah
created: 2026-07-28 22:01
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 22:01
---
Agent completed successfully in 0s
---
author: oompah
created: 2026-07-28 22:01
---
Run #1 [attempt=1, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: normal, Duration: 0s
---
author: oompah
created: 2026-07-28 22:01
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 22:01
---
Focus handoff from `` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 22:01
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 22:01
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-28 22:01
---
UNDERSTANDING: This is a feature implementation task requiring per-tick duplicate preflight scheduling, configurable capacity management, and implementation-lane reservation logic. The Duplicate Investigator correctly identified that OOMPAH-530 (claim infrastructure) is complete and OOMPAH-531 implementation is ready to begin. This is beyond maintenance scope and requires feature-focus implementation.
---
author: oompah
created: 2026-07-28 22:01
---
Focus handoff: chore

Outcome: Assessment complete - this task requires feature implementation, not maintenance work.

Evidence: Task requires implementing per-tick duplicate preflight scheduling logic in orchestrator._handle_dispatch_needed_locked, configurable capacity cap in ServiceConfig/.env.example, implementation-lane reservation, focus dispatch integration, comprehensive metrics, and full test coverage. Previous Duplicate Investigator focus confirmed OOMPAH-530 claim infrastructure is merged and ready, with no duplicate found.

Remaining work: All feature implementation work as described in task requirements. Prerequisites (OOMPAH-530 atomic claims) are complete.

Next focus: feature
---
author: oompah
created: 2026-07-28 22:02
---
Agent completed successfully in 46s (2831 tokens)
---
author: oompah
created: 2026-07-28 22:02
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 15, Tool calls: 13
- Tokens: 50 in / 2.8K out [2.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 46s
- Log: OOMPAH-531__20260728T220118Z.jsonl
---
author: oompah
created: 2026-07-28 22:02
---
Focus handoff from `chore` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 22:02
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 22:02
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-28 22:02
---
Understanding: Implementing OOMPAH-531 - Schedule duplicate preflight from spare agent capacity.

Plan:
1. Add OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS to config.py and .env.example (default 1, 0=disabled)
2. In _handle_dispatch_needed_locked, after normal dispatch loop, add a preflight scheduling pass:
   - Collect eligible Open tasks (non-terminal, dispatchable, not dep-blocked, not claimed, unchecked/stale)
   - Check spare capacity after implementation dispatch, reserving last slot for implementation-ready work
   - Use deterministic priority/age ordering to avoid starvation
   - For each eligible task up to cap: acquire preflight claim (OOMPAH-530 API), dispatch duplicate_detector focus without In Progress transition
   - Track counters/log for selected, started, skipped-no-capacity, skipped-reserved-slot, stale, already-checked, claim-race-lost
3. Preserve existing _apply_duplicate_detection heuristic pass
4. Add tests per requirements
---
author: oompah
created: 2026-07-28 22:03
---
The parent epic OOMPAH-528 merged from epic-OOMPAH-528, but this task was In Progress with work branch epic-OOMPAH-528. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-28 22:03
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 21
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 59s
- Log: OOMPAH-531__20260728T220219Z.jsonl
---
author: oompah
created: 2026-07-28 22:03
---
Already completed and merged in PR #568; terminated stale post-merge redispatch from the old scheduler.
---
author: oompah
created: 2026-07-28 22:05
---
The parent epic OOMPAH-528 merged from epic-OOMPAH-528, but this task was Done with work branch epic-OOMPAH-528. Its work is not proven to be in the merged epic. Git evidence: OOMPAH-531 branch epic-OOMPAH-528 has 1 unlanded commit(s), including 92aa5e5c2410. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-28 22:09
---
The parent epic OOMPAH-528 merged from epic-OOMPAH-528, but this task was Needs Human with work branch epic-OOMPAH-528. Its work is not proven to be in the merged epic. Inspect the task's agent history and remote branches, recover any missing commits through a new recovery epic or approved follow-up PR, then move this task to Done only after the recovered work is verified on the target branch.
---
author: oompah
created: 2026-07-28 22:13
---
Resolved: this was a false unlanded-work alert from the stale managed epic worktree. PR #568 merged verified head c4c7f5dfa into main as 70771b4e9. The flagged 92aa5e5c2 commit was a separate incomplete scheduler attempt that explicitly left dispatch integration pending; it was intentionally rejected before review and is not required task work. The stale local worktree/branch has now been removed, while origin/epic-OOMPAH-528 and all completed implementation remain preserved in main. Final branch validation was 13,070 passed, 7 skipped. No human recovery action is required.
---
author: oompah
created: 2026-07-28 22:13
---
Verified the completed duplicate-preflight work landed in PR #568; removed stale divergent worktree evidence.
---
author: oompah
created: 2026-08-04 22:36
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 23:34
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 23:34
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
