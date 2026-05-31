---
id: TASK-380
title: 'Per-task cost telemetry: write model-broken-down spend on every transition
  out of in_progress'
status: Done
assignee: []
created_date: 2026-05-05 19:49
updated_date: 2026-05-05 20:11
labels:
- feature
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: feature
beads:
  id: oompah-zlz_2-qh8
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-qh8
  target_branch: null
  url: null
  created_at: '2026-05-05T19:49:52Z'
  updated_at: '2026-05-05T20:11:06Z'
  closed_at: '2026-05-05T20:11:06Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
oompah currently tracks cost only as a process-wide running total (state.agent_totals.estimated_cost) rolled into the rolling budget window. There is no per-issue cost telemetry: closing an issue in beads gives no record of how much agent compute it consumed, and an issue that escalated quick → standard → deep is indistinguishable in the backlog from one that landed first try on quick.

We need per-task cost data attached to each issue so that:

- Backlog grooming can spot expensive issues (something burned $5 on retries).
- Postmortems can show whether escalation chains paid off (deep ran $0.80 after standard's failed $0.30 attempt — was it worth it).
- Future planning can size effort/cost vs delivered value.

The trigger should be every transition OUT of in_progress, not only on close. If the orchestrator detects an issue's state is no longer in_progress (closed, deferred, blocked, reopened, superseded, manually dragged to open via UI, agent terminated mid-flight by graceful drain) the cost record for the run that just ended must be persisted before the issue's runtime entry is dropped.

Costs should be broken down by model. Escalated runs use multiple models across attempts; that breakdown is the whole point of capturing this. Storage shape (comment vs attachment vs new field on the issue) should be picked during implementation, but the data must be readable from `bd show <id>` at minimum.

This pairs with the rolling-budget-window persistence that just landed (commit 331a895): the budget gives global affordance limits, the per-task data gives the receipts.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df9b3-3fe5-7eff-8650-a6d6774e1b2e
author: oompah
created: 2026-05-05T19:52:47Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9b3-4c66-7add-bbb6-3d9b60a25bb7
author: oompah
created: 2026-05-05T19:52:51Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9b4-3a08-74f1-827f-2cea04dd6a6b
author: oompah
created: 2026-05-05T19:53:51Z

**Understanding & Plan**

This feature requires writing per-task cost telemetry on every transition out of in_progress.

Key findings from codebase exploration:
-  in orchestrator.py is the main exit handler — this is where costs are already accumulated into
-  is called during reconciliation for issues that leave in_progress mid-flight (user moved to open, closed, etc.)
- Costs are estimated per-run using  which uses provider model_costs
- The tracker has  and  with  for storing structured data

**Plan:**
1. Add a  method in orchestrator.py that computes a model-breakdown cost record and stores it as beads metadata () on the issue
2. Call it from  (normal exits) and from  (mid-flight kills)
3. The record will be stored in issue metadata accumulating across runs (summing per-model entries)
4. Wire it into  visibility by storing in metadata (readable via bd show --json)
5. Write tests covering single-run close, multi-run escalation, and mid-flight termination

Storage: issue metadata  key — readable via  and by extension  text output. The dashboard detail page can also read from metadata.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9be-86f1-75b1-93eb-f00a3223b4cd
author: oompah
created: 2026-05-05T20:05:06Z

**Discovery**

Key code locations identified:

1. **oompah/orchestrator.py** - The main implementation target:
   - : Called on ALL normal exit paths (normal, stalled, max_turns, abnormal, rate_limited, ask_question)
   - : Called for mid-flight kills (reconcile detecting state change, drain, stall timeout)
   - : Already resolves model costs from provider - useful reference
   -  +  + : Used to identify what model was used

2. **Storage**: Issue metadata via  (key: ). This is:
   - Readable via  (already used for attachments)
   - Persistent across orchestrator restarts
   - Mergeable (existing metadata preserved on update)

3. **Cost computation**: Provider model_costs dict has  /  per model. Profile has fallback rates. The  +  chain resolves which model was actually used.

4. **Mid-flight kills**: Both  (for reconcile-triggered termination) and  (for worker-driven exits) are the two places cost must be written.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9be-bf89-742a-b2ad-d1df3e95662a
author: oompah
created: 2026-05-05T20:05:21Z

**Implementation**

Added to oompah/orchestrator.py:

1. **_compute_run_cost_record(entry)**: Builds a cost record for one completed run. Resolves model id via the existing provider/model resolution chain, computes cost using provider model_costs with profile-rate fallback. Returns None if no tokens to record. Shape: {total_input_tokens, total_output_tokens, total_cost_usd, by_model, runs}.

2. **_merge_cost_records(existing, new_record)** (staticmethod): Accumulates new_record into existing. Deduplicates by model id (sums tokens + cost). Appends to runs list (full history preserved). Handles None/empty existing cleanly.

3. **_write_task_cost_record(entry)**: Persists cost telemetry into issue metadata (oompah.task_costs). Reads existing metadata first (to preserve other keys like oompah.attachments), merges cost records, writes back via bd update --metadata. All exceptions logged+swallowed.

4. **_fire_task_cost_record(entry)**: Fire-and-forget wrapper. Submits _write_task_cost_record to _tick_pool (background thread). Exception in pool submission also swallowed. Never blocks the caller.

5. **Call sites**:
   - _on_worker_exit(): fires AFTER cost is added to process-wide budget totals (so the record captures the same tokens as the global counter), BEFORE the reason-specific logic (captures all exit paths including ask_question which transitions out of in_progress)
   - _terminate_running(): fires BEFORE workspace cleanup (entry still has session token data at that point)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c1-835a-751c-b77b-2088cf162a8d
author: oompah
created: 2026-05-05T20:08:22Z

**Verification**

All 37 new tests pass:
- TestComputeRunCostRecord (7 tests): cost computation, zero token guard, fallback rates, runs list shape
- TestMergeCostRecords (5 tests): same-model sum, different-model entries, three-run accumulation, run list ordering
- TestWriteTaskCostRecord (6 tests): happy path write, merge with existing, zero tokens skip, bd show failure resilience, bd update failure swallowed, unexpected exception swallowed
- TestFireTaskCostRecord (3 tests): submits to pool, non-blocking, pool exception swallowed
- TestOnWorkerExitWritesCostRecord (7 tests): all exit reasons (normal, stalled, max_turns, abnormal, rate_limited, ask_question, missing entry)
- TestTerminateRunningWritesCostRecord (3 tests): terminate fires cost, cost before workspace cleanup, missing entry no-op
- TestReconcileTriggeredCostRecord (2 tests): terminal state and moved-to-open both write cost
- TestMultiRunAccumulation (2 tests): two-model escalation breakdown, sequential writes accumulate

Full suite: 779 tests pass (pre-existing failures due to missing httpx/fastapi dev dependencies are unrelated to this change).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c3-ed02-7c25-be3e-fb7b82b85370
author: oompah
created: 2026-05-05T20:11:00Z

**Completion**

Delivered per-task cost telemetry feature:

**What was built:**
- Cost records stored in issue metadata (oompah.task_costs) on every transition out of in_progress
- Model-broken-down spend: each record includes per-model input/output tokens and dollar cost
- Cumulative accumulation: escalated runs (quick to standard to deep) sum correctly, separate model entries per model used
- All trigger paths covered: normal completion, stalled, max_turns, abnormal, rate_limited, ask_question (transitions out of in_progress), mid-flight UI move-to-open, reconcile-triggered termination
- Fire-and-forget threading: cost writes never block worker exit path; exceptions logged+swallowed
- Readable via bd show --json (metadata field oompah.task_costs) and therefore bd show at minimum

**Acceptance criteria status:**
- Every in_progress out-transition writes a cost record: YES (_on_worker_exit + _terminate_running)
- Cost record shape with model breakdown: YES (total_input/output_tokens, total_cost_usd, by_model dict, runs list)
- Multiple runs accumulate cumulatively: YES (_merge_cost_records deduplicates by model id)
- Readable from bd show: YES (stored in issue metadata, same as oompah.attachments)
- Mid-flight termination paths covered: YES (_terminate_running fires before runtime entry dropped)
- Tests: 37 new tests, all passing
- Backwards compat: YES (no backfill, existing issues without record are fine)
- Performance: YES (fire-and-forget thread, never blocks exit)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c4-0b15-7b85-8357-487453333b01
author: oompah
created: 2026-05-05T20:11:08Z

Agent completed successfully in 1110s (5763764 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
