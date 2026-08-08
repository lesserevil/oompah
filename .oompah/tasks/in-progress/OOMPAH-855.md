---
id: OOMPAH-855
type: task
status: In Progress
priority: null
title: Preserve auditor candidate eligibility across operator pause retirement
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-854
labels: []
assignee: null
created_at: '2026-08-06T06:52:17.206143Z'
updated_at: '2026-08-08T08:17:54.909932Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-855
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0ad2f9dc5c677ad6cd902f1e9c2c86707b47b775130aff56c10ad27c67567388
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T18:00:31.418473+00:00'
  matched_identifiers: []
  evidence: Project-owner review of the complete active systemic-workflow corpus found
    no equivalent task. OOMPAH-855 uniquely preserves auditor candidate eligibility
    across scheduler pause/graceful quiesce retirement. The corpus-capacity inconclusive
    path is the already-fixed OOMPAH-853 deployment gap, not evidence of a duplicate.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-06T18:00:31.418473+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Project-owner review of the complete active systemic-workflow
    corpus found no equivalent task. OOMPAH-855 uniquely preserves auditor candidate
    eligibility across scheduler pause/graceful quiesce retirement. The corpus-capacity
    inconclusive path is the already-fixed OOMPAH-853 deployment gap, not evidence
    of a duplicate.
oompah.agent_run_id: 557c0e32-8f76-470e-b1bb-7f55dcefff86
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-855
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-855
  base_branch: epic-OOMPAH-763
  base_sha: a85a36baf7b3ebcb45be27823755b5694a790a49
  updated_at: '2026-08-07T17:47:16.210836+00:00'
oompah.task_costs:
  total_input_tokens: 112
  total_output_tokens: 3943
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2744
      cost_usd: 0.0
    sonnet:
      input_tokens: 102
      output_tokens: 1199
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2744
    cost_usd: 0.0
    recorded_at: '2026-08-06T16:32:35.675392+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 102
    output_tokens: 1199
    cost_usd: 0.0
    recorded_at: '2026-08-07T18:19:22.114489+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-855__20260806T163128Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-855
    source_sha: 6b67846406858b585ce47939f70bec76eb706fe8
    completed_at: '2026-08-06T16:32:35.707636+00:00'
  - run_id: 117bbd8e19e540ca877226e1150565f2--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: epic-OOMPAH-763--task-OOMPAH-855
    source_sha: null
    completed_at: ''
  - run_id: 5d40281878bd4717b31d5e8bad14168c--contributor-1e03bff0a496
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: general
    source_branch: epic-OOMPAH-763--task-OOMPAH-855
    source_sha: null
    completed_at: ''
---
## Summary

Live regression on OOMPAH-853 on 2026-08-06. A Done auditor using the second eligible candidate was retired by the global operator pause used to fence a duplicate implementation writer. The retirement was recorded as a consumed attempt. After resume, both configured candidates were considered attempted and the exact unchanged audit moved to Needs Human for no independent candidate. An owner override was required even though the exact-head gate had passed and the interrupted auditor reported no code defect. Implementation scope: classify scheduler pause and graceful quiesce retirement separately from provider, policy, verdict, transport, timeout, and operator-cancel failures; preserve or immediately requeue the same candidate eligibility when no structured verdict was committed; fence late output from the retired runtime; keep genuine policy denials and repeated provider failures consuming or rotating attempts as configured; make recovery idempotent across pause, resume, and restart. Relevant code includes orchestrator pause and worker retirement, auditor dispatch attempt persistence, terminal audit workflow recovery, and exhaustion classification. Required tests: barrier-pause an auditor before verdict, resume, and prove one retry without Needs Human or attempt-budget consumption; repeat across restart; cover pause after durable verdict finalization without duplicate apply; cover mixed first-candidate policy denial plus second-candidate pause; prove explicit owner cancellation and genuine policy or transport failure retain current semantics. Acceptance criteria: routine pause or graceful drain cannot turn an otherwise healthy unchanged audit into no-independent-candidate exhaustion; exact evidence and candidate independence remain fail-closed; focused pause, auditor lifecycle, durable workflow, and terminal-transition tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 16:30
---
Promoted for the systemic completion program with an explicit hard-start on OOMPAH-854. The pause-retirement eligibility repair depends on OOMPAH-854 durable pre-provider audit fencing and must dispatch from that accepted lineage, avoiding a second overlapping quiesce/restart implementation.
---
author: oompah
created: 2026-08-06 16:31
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 16:31
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 16:32
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.7K out [2.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 32s
- Log: OOMPAH-855__20260806T163128Z.jsonl
---
author: oompah
created: 2026-08-06 16:33
---
Duplicate screening stopped with an actionable corpus diagnostic: Required structural peers could not fit the bounded duplicate corpus. Omitted peer identifiers: OOMPAH-847, OOMPAH-848, OOMPAH-850, OOMPAH-851, OOMPAH-852, OOMPAH-853, OOMPAH-854, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861, OOMPAH-862. Increase the duplicate corpus task/byte budget or have a project owner review the authoritative tracker corpus, then use the authenticated duplicate-screening owner-resolution action with a conclusive verdict.
---
author: oompah
created: 2026-08-07 17:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 17:45
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-07 17:46
---
Agent failed: RuntimeError: Codex native command runner bypassed the required validation guard boundary. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-07 17:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 51s
- Log: OOMPAH-855__20260807T174554Z.jsonl
---
author: oompah
created: 2026-08-07 17:47
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-07 17:47
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-07 17:55
---
**Understanding:** The bug is a live regression where an operator pause terminates running auditors, and that termination consumes the attempt budget exactly like a genuine provider failure.

Root cause (traced through orchestrator.py):
1. `pause()` calls `_terminate_all_running()` → `_terminate_running(issue_id)` for each running auditor
2. `_terminating_worker_ids.add(issue_id)` prevents `_on_worker_exit` from firing
3. In `_terminate_running` (line ~42307), `_finish_audit_attempt` is only called if `forced_exit_reason` is set — pause does NOT set this
4. The audit record is left in IN_PROGRESS state in the tracker metadata
5. On resume, `recover()` sees an IN_PROGRESS attempt with no live worker → marks it as 'abandoned' (PENDING) with the provider/model still in the attempt
6. `plan()` in the dispatch loop calls `attempted_pairs()` — the abandoned attempt's (provider_id, model) is still counted → candidate excluded
7. With 2 candidates total (policy denial + pause-abandoned), both are in `attempted_pairs()` → no more candidates → NEEDS_HUMAN

Fix plan:
1. Add `SCHEDULER_PAUSE = 'scheduler_pause'` to `FailureClassification` in `terminal_audit.py`
2. In `orchestrator.py`:
   - In `pause()`, before `_terminate_all_running()`, set `forced_exit_reason = 'scheduler_pause'` on all running auditor entries
   - In `_finish_audit_attempt()`, map 'scheduler_pause' and 'lifecycle_drain_before_launch' to `FailureClassification.SCHEDULER_PAUSE`
3. In `auditor_dispatch.py`:
   - `attempted_pairs()`: exclude attempts with `SCHEDULER_PAUSE` classification
   - `plan()`: exclude `SCHEDULER_PAUSE` attempts from the count check
4. Write tests covering: pause-before-verdict retry, restart, post-verdict no-duplicate, mixed policy-denial+pause, owner-cancel semantics preserved
---
author: oompah
created: 2026-08-07 18:19
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 53
- Tokens: 102 in / 1.2K out [1.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 32m 26s
- Log: OOMPAH-855__20260807T174739Z.jsonl
---
author: oompah
created: 2026-08-08 08:00
---
Direct implementation is underway on exact systemic base 6cbbd6ef7. The fix now fences pause/graceful retirement before cancellation, records a non-consuming scheduler-pause audit outcome, restores the durable workflow claim count, and rejects late callbacks by rotating the exact lease. Focused coverage includes mixed policy+pause candidate selection, repeated pause workflow ownership, restart recovery, actual pause/resume retirement, and post-verdict race behavior. Static compilation is green; focused tests are queued through the dedicated validation broker.
---
author: oompah
created: 2026-08-08 08:17
---
Implementation complete on isolated branch direct/OOMPAH-855-on-systemic at 296a6c289f7a7a1a3d3e87996a79490bb3bad98e (base 6cbbd6ef7bb7882257c4c9e9175bd5b3edc14183). Scheduler pause/graceful retirement is now a durable non-consuming classification; candidate, transport, and workflow execution budgets are restored; exact workflow phase/lease fences reject late callbacks; finalizing verdicts win; restart recovery is idempotent; policy, transport, and owner-cancel semantics remain distinct; health no longer warns for routine pause recovery. Dedicated focused validation: 225 passed, 1 pre-existing AsyncMock RuntimeWarning, artifact /home/shedwards/.oompah/ci-artifacts.OOMPAH-855-green.fjr82i. Static compile, diff check, terminal mutation scan, and secret scan passed. Branch/worktree preserved for systemic composition; no task status or remote mutation performed.
---
<!-- COMMENTS:END -->
