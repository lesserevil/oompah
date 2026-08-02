---
id: OOMPAH-700
type: bug
status: In Progress
priority: 1
title: Gate accepted submissions without a canonical task worktree
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T19:52:39.323644Z'
updated_at: '2026-08-02T20:24:53.176048Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d7674744c97e28ac82f72e0612635fd532dc44d1a9094bb4fbf95b21aa9eecfe
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T19:56:56.660505+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\n\nEvidence: OOMPAH-700 is a follow-up bug filed from OOMPAH-698\
    \ addressing a specific failure mode: `oompah task submit` accepts a valid pushed\
    \ submission but the standalone review gate can only find canonical worktrees\
    \ and thereby wrongly moves the task to Needs CI Fix with \"No existing worktree\
    \ matched the review branch tip\". The scope is precise \u2014 quality-gate worktree\
    \ discovery, exact-head snapshot/preflight in `oompah/quality_gate.py`, and submission\
    \ validation in `oompah/server.py`/`oompah/task_cli.py`.\n\nReviewing the supplied\
    \ project task corpus (OOMPAH-1 through OOMPAH-175, plus the current task), every\
    \ candidate other than OOMPAH-700 is in the terminal `Archived` state and must\
    \ be excluded per the duplicate rules. The corpus contains no active peer whose\
    \ description addresses the exact-head review gate, quality-gate worktree discovery,\
    \ submission acceptance semantics, or the \"No existing worktree matched the review\
    \ branch tip\" failure. The closest historical work in the corpus is orchestrator/epic-landing\
    \ hardening (OOMPAH-162, OOMPAH-163, OOMPAH-165) \u2014 all Archived and orthogonal\
    \ (child-branch landing checks, dispatch validation, and epic-target-aware landing\
    \ detection, respectively), not the submission-gate worktree discovery bug described\
    \ here.\n\nThe triggering task OOMPAH-698 is referenced only as the origin/reproducer;\
    \ it does not appear as an active peer in the supplied corpus and cannot serve\
    \ as a duplicate target (and would not be one anyway, since this task is the follow-up\
    \ fix for that reproduction).\n\nNo active duplicate exists. Ending run without\
    \ tracker mutation."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5475ec6b-9612-4159-a581-930f5e6724e6
oompah.task_costs:
  total_input_tokens: 6
  total_output_tokens: 1125
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 6
      output_tokens: 1125
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 6
    output_tokens: 1125
    cost_usd: 0.0
    recorded_at: '2026-08-02T19:56:56.659616+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-700__20260802T195632Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: duplicate_detector
    source_branch: OOMPAH-700
    source_sha: 126422448bb23f19561533eebbdfc0a4aa4f9178
    completed_at: '2026-08-02T19:56:56.670367+00:00'
---
## Summary

Triggered by: OOMPAH-698

Production reproduction from OOMPAH-698: oompah task submit accepted a clean, pushed checkout whose branch and exact head matched the task, but the standalone review gate only searched the canonical managed worktree path and project checkout. It then moved the task to Needs CI Fix with No existing worktree matched the review branch tip, despite the submitted head already being available at origin/OOMPAH-698 and having passed the full gate in the submitting checkout.\n\nImplementation scope:\n- Make exact-head review gating independent of a surviving checkout at the submitted branch head. Materialize or snapshot the verified remote/local ref from the managed repository, or reject unsupported submission locations synchronously before returning success.\n- Preserve the immutable exact-head sandbox, lifecycle safety-head containment, clean-tree guarantees, generation cancellation, and cache semantics.\n- Do not trust a client-supplied filesystem path and do not require operators to copy an otherwise valid checkout into the private worktree directory.\n- Classify missing commit objects or unavailable remote refs as infrastructure/evidence failures, not candidate CI failures; never add ci-fix for a gate command that did not run.\n- Make retries and restart recovery idempotent.\n\nRelevant code: oompah/orchestrator.py quality-gate worktree discovery and review gate; oompah/quality_gate.py exact-head snapshot/preflight; submission validation in oompah/server.py and oompah/task_cli.py.\n\nRequired tests:\n- A valid pushed submission from a clean non-canonical checkout gates the exact remote head and creates a review.\n- A missing canonical worktree does not become Needs CI Fix when the exact commit exists in the managed repository.\n- A missing or unfetchable exact head fails closed with an actionable infrastructure classification and no ci-fix label.\n- A branch advancing during snapshot or gate remains stale and cannot create a review.\n- Repeated resubmission and restart runs at most one gate per evidence key and one review.\n\nAcceptance criteria:\n- The OOMPAH-698 reproduction completes without manually recreating its worktree.\n- Accepted submissions cannot be stranded solely by checkout-path discovery.\n- Focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 19:56
---
Duplicate screening dispatched (profile: deep, task remains Open)
---
author: oompah
created: 2026-08-02 19:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 19:56
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/opus]
- Turns: 2, Tool calls: 0
- Tokens: 6 in / 1.1K out [1.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 28s
- Log: OOMPAH-700__20260802T195632Z.jsonl
---
author: oompah
created: 2026-08-02 19:57
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-02 19:57
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-02 19:57
---
Understanding: OOMPAH-700 must decouple exact-head review gating from discovery of a surviving canonical checkout. I will inspect the existing OOMPAH-700 branch and CI logs, reproduce the failure, then minimally materialize trusted submitted evidence from the managed repository while preserving stale-head checks, sandbox cleanliness, cancellation/cache idempotency, and infrastructure-vs-CI classification. Regression tests will cover non-canonical submission, unavailable evidence, stale branch movement, and repeated recovery.
---
author: oompah
created: 2026-08-02 20:01
---
Discovery: No OOMPAH-700 PR or Actions run exists; the branch is clean at origin/main, so this is the original bug implementation rather than repair of an existing check. Root cause is orchestrator.py::_review_quality_gate_passes/_quality_gate_worktree: review gating aborts unless a discovered checkout HEAD equals the locally resolved branch ref. BranchQualityGate already archives an explicit SHA, but run() rejects sources whose checkout HEAD differs. The fix will let the managed repository supply an exact committed snapshot, retain strict mode for reusable task/integration worktrees, bind standalone gates to submitted/verified remote evidence, and classify unavailable commit/ref materialization as infrastructure_error without ci-fix.
---
author: oompah
created: 2026-08-02 20:02
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 24
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 1s
- Log: OOMPAH-700__20260802T195722Z.jsonl
---
author: oompah
created: 2026-08-02 20:02
---
Claimed for direct owner implementation after stopping the automatic dispatch to avoid concurrent writes during this cleanup session.
---
author: oompah
created: 2026-08-02 20:12
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-02 20:12
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-02 20:16
---
Understanding: Resuming from the preserved snapshot at decf967e5 which already modified oompah/quality_gate.py to accept require_source_head_match=False, resolve the archive from the managed repository's exact commit rather than the source checkout's HEAD, and classify unresolvable heads as infrastructure_error. Orchestrator side (_review_quality_gate_passes) already routes standalone submissions through project.repo_path when no matching worktree exists. Next step: add regression tests for OOMPAH-698 scenarios (non-canonical clean submission, unfetchable head, stale head during snapshot, idempotent recovery) then run focused suites.
---
author: oompah
created: 2026-08-02 20:24
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-02 20:24
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-02 20:24
---
Understanding: Resume the preserved exact-head gating fix and validate it against OOMPAH-700's acceptance criteria. I will inspect the existing recovery snapshot without replacing it, identify any incomplete test coverage or CI failures, make only the necessary changes, run focused Makefile-backed checks, then commit, push OOMPAH-700, and submit the task.
---
<!-- COMMENTS:END -->
