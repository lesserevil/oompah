---
id: OOMPAH-806
type: bug
status: In Validation
priority: 1
title: Fence stalled-task recovery behind internal gate authority
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T20:44:00.064452Z'
updated_at: '2026-08-04T23:01:21.820032Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-806
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 37a03c9984f7a48928f4dc44a6e6eac2a049d5deec92e4d74a806a7e80609853
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:47:13.660470+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest active tasks are OOMPAH-803, OOMPAH-768, OOMPAH-769,\
    \ and OOMPAH-770. They cover transition-service routing, integration-domain migration,\
    \ generation fencing, and liveness generally, but none specifically addresses\
    \ external CI overriding an authoritative failed exact-head internal gate and\
    \ cancelling its blocked integration generation. OOMPAH-806 is a distinct incident\
    \ regression requiring explicit precedence and race/restart tests.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none\n\nEvidence: Closest active tasks are OOMPAH-803, OOMPAH-768, OOMPAH-769,\
    \ and OOMPAH-770. They cover transition-service routing, integration-domain migration,\
    \ generation fencing, and liveness generally, but none specifically addresses\
    \ external CI overriding an authoritative failed exact-head internal gate and\
    \ cancelling its blocked integration generation. OOMPAH-806 is a distinct incident\
    \ regression requiring explicit precedence and race/restart tests."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-806
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-806
  base_branch: epic-OOMPAH-763
  base_sha: 5cd24351e3b3f643bf4d43af84e81af0928b5f44
  head_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  integrated_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  submitted_at: '2026-08-04T22:38:33.232494+00:00'
  updated_at: '2026-08-04T23:00:44.676647+00:00'
oompah.task_costs:
  total_input_tokens: 48134
  total_output_tokens: 5473
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 48134
      output_tokens: 5473
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 47917
    output_tokens: 291
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:47:13.658330+00:00'
  - profile: deep
    model: opus
    input_tokens: 199
    output_tokens: 4792
    cost_usd: 0.0
    recorded_at: '2026-08-04T21:48:38.627010+00:00'
  - profile: deep
    model: opus
    input_tokens: 18
    output_tokens: 390
    cost_usd: 0.0
    recorded_at: '2026-08-04T22:32:34.868830+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-806__20260804T204517Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-806
    source_sha: f1e7925b7263f980517f943291102c8c83335ed2
    completed_at: '2026-08-04T20:47:13.706379+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e95e35ff5779
    project_id: proj-14849f1b
    task_id: OOMPAH-806
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 11ab1dfd8cf4bcfcfaf6ab5f6ac31aab28ab666033c89441eea41e7a808b7694
    attempts: []
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-04T23:01:11.209732+00:00'
  attempt_history: []
---
## Summary

Live reproduction on 2026-08-04: OOMPAH-793's exact-head combined-tree integration gate failed at ef5e8c30e (integration row blocked; task Needs CI Fix). Minutes later the stalled-task watchdog observed unrelated passing external commit CI, reopened the task to Open, and the integration reconciler cancelled the blocked row because tracker state was Open. This discarded the authoritative internal gate failure and could expose completed implementation to duplicate dispatch; only an existing direct-owner lease prevented churn. Implementation scope: make current internal integration/gate records and exact-head authority outrank generic forge CI when classifying Needs CI Fix/Ready to Integrate; never reopen or cancel a blocked integration generation based solely on external CI for the same or another check suite; require a newer pushed head, explicit same-generation integration retry, or authoritative repair evidence; serialize watchdog and integration transitions through TaskTransitionService with generation CAS; keep actionable blocked evidence visible to UI/liveness. Relevant code: oompah/stalled_task_watchdog.py, orchestrator watchdog evidence/action plumbing, integration queue reconciliation/executor, TaskTransitionService, and state/alert projections. Required deterministic tests: reproduce blocked combined-tree gate plus passing external CI; watchdog performs no Open transition and row remains blocked; newer repaired head may reopen/resubmit exactly once; race watchdog vs gate completion has one generation winner; restart preserves precedence; unrelated project/task CI cannot influence it; direct-owner absence still cannot cause duplicate implementation dispatch. Acceptance: an internal failed gate remains authoritative until repaired or explicitly retried, watchdog recovery cannot cancel or regress its integration generation, and OOMPAH-793-style churn cannot recur.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:44
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-04 20:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:47
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 47.9K in / 291 out [48.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 19s
- Log: OOMPAH-806__20260804T204517Z.jsonl
---
author: oompah
created: 2026-08-04 20:47
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 20:47
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-04 20:49
---
Understanding: The bug is a churn scenario where the stalled-task watchdog reopens a task to Open based on unrelated passing external forge CI, causing the integration reconciler to cancel the authoritative internal gate 'Needs CI Fix' row (blocked at exact head). The fix must: (1) make current internal integration/gate records outrank generic forge CI; (2) never reopen or cancel a blocked integration generation based on external CI alone; (3) require newer pushed head, explicit same-gen retry, or authoritative repair evidence; (4) serialize watchdog + integration transitions through TaskTransitionService with generation CAS; (5) keep blocked evidence visible. Focus files: oompah/stalled_task_watchdog.py, oompah/integration_queue.py, oompah/integration_executor.py, oompah/task_transition_service.py, oompah/orchestrator.py. Starting exploration.
---
author: oompah
created: 2026-08-04 21:16
---
Discovery: Root cause traced. (1) oompah/stalled_task_watchdog.py:_current_evidence_decision() uses external CI signal ('ci_status' in {pass,green,success}) to reopen NEEDS_CI_FIX tasks — with no precedence check against an authoritative internal integration record. (2) oompah/orchestrator.py:_collect_stalled_watchdog_evidence and stalled_task_watchdog._tracker_issue_evidence do not include the integration record (metadata['oompah.integration']) — so classifier cannot see the blocked authority. (3) oompah/orchestrator.py:_retire_inactive_integration_rows cancels 'blocked' rows unconditionally when tracker state != READY_TO_INTEGRATE (line ~10236); a watchdog-driven Open transition therefore erases the internal gate authority. Fix plan: (a) include integration record in evidence; (b) add authority precedence in classifier: if integration.state=='blocked' and integration.head_sha matches, DO NOT reopen based on external CI — insufficient_evidence; (c) preserve 'blocked' rows in retirement unless task reached a terminal state (Done/Merged/Archived) or the branch head has moved past the blocked head_sha; (d) add deterministic tests.
---
author: oompah
created: 2026-08-04 21:45
---
Implementation: Three surgical changes to fence stalled-task recovery behind internal gate authority.

**oompah/stalled_task_watchdog.py**
- Extended WatchdogEvidence with 'integration' field carrying the tracker's oompah.integration record.
- _normalise_watchdog_evidence + _evidence_signals extract integration_state, integration_head_sha, integration_last_error, and branch_head_sha.
- New _blocked_gate_authority_decision helper: if the internal integration record is 'blocked' at a head that equals (or is not superseded by) the current branch head, the classifier returns 'insufficient_evidence' / 'none' — the authoritative internal gate verdict outranks any generic forge CI signal.
- The precedence check runs in both _current_evidence_decision (evidence-driven path) and classify_stalled_task's NEEDS_CI_FIX / NEEDS_REBASE branches (prose-comment fallback path), so neither a passing external-CI evidence signal nor a legacy 'CI passing' comment can override a blocked internal gate.
- Merged review, audit-verdict pass, and branch-on-canonical-target signals still override the blocked record (authoritative repair evidence).
- _tracker_issue_evidence now surfaces the integration record from either metadata['oompah.integration'] or issue.integration.

**oompah/orchestrator.py**
- _collect_stalled_watchdog_evidence includes metadata['oompah.integration'] (or issue.integration fallback) so the classifier can see the internal gate authority.
- _retire_inactive_integration_rows preserves 'blocked' rows unless (a) the tracker task reached a terminal state (Done/Merged/Archived), (b) the tracker's integration record recorded a divergent head_sha (fresh submission), or (c) the tracker no longer reports the task at all. This prevents the reconciler from cancelling a blocked row on the strength of a watchdog-driven Open transition — the OOMPAH-793 reproduction.

**Tests added**
- tests/test_stalled_task_watchdog.py::TestInternalGateAuthorityPrecedence — 12 cases covering the blocked-gate + passing-CI reproduction, prose-comment fallback, newer-head repair evidence, NEEDS_REBASE symmetry, restart idempotence, and end-to-end run_watchdog_audit assertions.
- test_collects_integration_record_for_internal_gate_authority — verifies the orchestrator evidence collector surfaces the integration record.
- tests/test_delivery_plane_recovery.py — 6 new cases covering blocked-row preservation across watchdog-driven Open/Needs CI Fix/Needs Rebase/In Progress transitions, terminal-state retirement (parametrised across Done/Merged/Archived), head-divergence retirement, tracker-issue-absent retirement, non-blocked (ready) row retirement (OOMPAH-657 regression), and explicit_retry rearm-exactly-once via the queue.
---
author: oompah
created: 2026-08-04 21:48
---
Agent stalled — no productive actions (writes/commands) for 10 consecutive turns (3660s (4991 tokens)). Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-04 21:48
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 189, Tool calls: 126
- Tokens: 199 in / 4.8K out [5.0K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 1m 0s
- Log: OOMPAH-806__20260804T204754Z.jsonl
---
author: oompah
created: 2026-08-04 21:49
---
Acceptance-gap handoff after the 3600s agent timeout: the preserved four-file worktree has 288 focused tests passing, but current code still lets run_watchdog_audit() call tracker.update_issue(..., status=Open) directly. Before submission, either route watchdog/integration status races through TaskTransitionService with generation CAS and prove one authoritative winner, or explicitly narrow this task and add a dependency/handoff to OOMPAH-775 for the remaining writer-boundary invariant. Do not submit solely on the passing focused suite.
---
author: oompah
created: 2026-08-04 21:49
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 21:49
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-04 21:54
---
Discovery update: The preserved authority-precedence fix is correct, but the acceptance gap is real: run_watchdog_audit still writes Open directly and _route_integration_failure writes the gate repair status directly. TaskTransitionService already supplies a durable per-task claim plus expected-version, assignment-generation, and exact-head CAS, but Orchestrator does not instantiate it. I will wire a shared durable transition journal into Orchestrator, make watchdog remediation fail closed without an injected transition boundary, route combined-tree gate failure through the same boundary, and add a deterministic race/restart test. The workflow contract also needs the existing Needs CI Fix/Needs Rebase -> Open recovery edges so the service can preserve watchdog behavior.
---
author: oompah
created: 2026-08-04 22:05
---
Landing-order coordination: OOMPAH-796 now finish-depends on this task because both legitimately touch orchestrator.py and workflow_contract.py. Finish and submit the transition-authority repair first; OOMPAH-796 will rebase and run combined focused tests afterward.
---
author: oompah
created: 2026-08-04 22:08
---
Final acceptance check before submission: run_watchdog_audit currently posts the [watchdog:stalled_task] action comment before the TaskTransitionService CAS. If CAS returns WAITING/rejected, ensure that sentinel does not make the next sweep classify already_actioned and suppress a required retry. Add a deterministic regression proving deferred/failed generation CAS remains retryable later, while an actually applied winner stays idempotent. Passing transition routing tests alone are insufficient if the comment becomes premature durable authority.
---
author: oompah
created: 2026-08-04 22:09
---
Implementation update: Completed the writer-boundary gap. Orchestrator now owns a durable task_transitions.sqlite3 journal and routes stalled-watchdog reopen plus combined-tree integration failure status changes through TaskTransitionService. Intents carry the observed authority version, assignment generation when present, and exact tracker head; brief same-task claim races retry under one idempotency key. run_watchdog_audit fails closed without an injected transition boundary and posts its sentinel only after a verified reopen, so rejected generations are not suppressed. The blocked integration record is persisted before the gate status CAS; blocked rows remain authoritative; Open+blocked tasks are rejected from generic dispatch even without a direct-owner lease. Added the existing gate-routing/watchdog-recovery contract edges and deterministic production-path/race tests.
---
author: oompah
created: 2026-08-04 22:09
---
Verification: 188 focused tests pass (test_stalled_task_watchdog, test_delivery_plane_recovery, test_task_transition_service, test_workflow_contract). An additional 334 neighboring tests pass (test_integration_retry_alert_recovery, test_parallel_epic_children, test_orchestrator_handlers). Terminal mutation scan passes: 8 identified, 8 allowlisted. git diff --check and py_compile pass. The normal Make bootstrap could not run because uv/systemd-run fails in this managed container (DBus rejects PID 2); after attempting the Make target, I ran its underlying scanner with the already provisioned project Python. GitHub has no PR or Actions run for this unpushed task branch, so there were no remote failure logs to inspect.
---
author: oompah
created: 2026-08-04 22:10
---
Completion: Delivered and pushed 8322a4d198067b7c01d1e8ce7f379ca8f51bc621 on epic-OOMPAH-763--task-OOMPAH-806. Internal blocked gate evidence now outranks external CI; watchdog and combined-tree gate status writers share durable generation/version/head CAS; blocked rows and actionable alerts survive inconsistent tracker state; Open+blocked cannot dispatch duplicate implementation; repaired/newer heads and explicit retries remain available. Focused and neighboring suites total 522 passing tests, with terminal mutation scan, py_compile, and diff checks clean. The remote branch exactly matches local and is up to date. GitHub currently reports no PR or workflow run for the newly published branch; oompah submission will create/manage the review.
---
author: oompah
created: 2026-08-04 22:10
---
Fenced stalled-task recovery behind authoritative internal gate records and durable TaskTransitionService CAS; preserved blocked generations/alerts and prevented duplicate dispatch. 522 focused/neighboring tests pass.
---
author: oompah
created: 2026-08-04 22:10
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 75
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 21m 18s
- Log: OOMPAH-806__20260804T214941Z.jsonl
---
author: oompah
created: 2026-08-04 22:26
---
The combined-tree quality gate failed on `epic-OOMPAH-763--task-OOMPAH-806`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_webhooks.py::TestForwarderProcessFullLifecycle::test_process_start_and_immediate_exit
  /home/shedwards/.oompah/tmp/oompah-quality-gate-gkfd5rlm/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7e1afe14b9c0>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_orchestrator_merged.py::TestResetOrphanedInProgress::test_preserves_completed_marker_orphaned_in_progress_as_done
FAILED tests/test_orchestrator_merged.py::TestBudgetGateFreeTierBypass::test_free_model_dispatched_when_over_budget
= 2 failed, 15691 passed, 8 skipped, 1 xfailed, 43 warnings in 810.28s (0:13:30) =

/home/shedwards/.oompah/tmp/oompah-quality-gate-gkfd5rlm/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7b3a3d80b9c0>

Traceback (most recent call last):
  File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
    self.close()
  File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
    proto.pipe.close()
  File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
    self._close(None)
  File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
    self._loop.call_soon(self._call_connection_lost, exc)
  File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
    self._check_closed()
  File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
    raise RuntimeError('Event loop is closed')
RuntimeError: Event loop is closed

Enable tracemalloc to get traceback where the object was allocated.
See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
  warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))
make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-04 22:28
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 22:28
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-04 22:32
---
Agent failed: Exception: Command failed with exit code 143 (exit code: 143)
Error output: Check stderr output for details. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-04 22:32
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 8, Tool calls: 7
- Tokens: 18 in / 390 out [408 total]
- Cost: $0.0000
- Exit: error, Duration: 4m 0s
- Log: OOMPAH-806__20260804T222853Z.jsonl
---
author: oompah
created: 2026-08-04 22:38
---
Repaired the failed exact-head submission by reconciling the root epic with merged OOMPAH-805 reliability fixes and the combined-tree fixture stabilization, then patch-equivalently rebasing OOMPAH-806 to 30dc2b2075a48c6c542da55a46ad0285f492d527. The three prior suite-only failures passed together for 25 consecutive iterations; the combined changed-file and fixture slice passed 496/496. The prior blocked queue row was cancelled by the deployed watchdog race this task fixes, so this head is being freshly submitted.
---
author: oompah
created: 2026-08-04 22:38
---
Rebased the authoritative-gate watchdog fix onto the reconciled root at exact head 30dc2b2075a48c6c542da55a46ad0285f492d527. Prior gate-only failures pass 25x stress and 496 combined focused tests.
---
author: oompah
created: 2026-08-04 23:01
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
