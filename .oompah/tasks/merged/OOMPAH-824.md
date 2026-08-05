---
id: OOMPAH-824
type: task
status: Merged
priority: 0
title: Bootstrap heavyweight validation arbitration onto main
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-816
labels:
- ci-fix
assignee: null
created_at: '2026-08-05T08:20:26.696471Z'
updated_at: '2026-08-05T12:21:58.907285Z'
work_branch: OOMPAH-824
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/720
review_number: '720'
review_head: 50d19fe5d932421111494403c9b0160d5f2e35f4
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-824
  base_branch: main
  head_sha: 50d19fe5d932421111494403c9b0160d5f2e35f4
  submitted_at: '2026-08-05T11:49:56.447474+00:00'
  updated_at: '2026-08-05T11:49:56.447474+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/720
oompah.review_number: '720'
oompah.work_branch: OOMPAH-824
oompah.target_branch: main
oompah.review_head: 50d19fe5d932421111494403c9b0160d5f2e35f4
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-0c343f36134c: '2026-08-05T12:05:34.422214+00:00'
    attempt-cf24920ef4f4: '2026-08-05T12:08:33.069632+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-824
    target_state: Done
    evidence_fingerprint: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
    audit_ids:
    - audit-11ec4964b81b
    kind: result
    applied: true
    retired_at: '2026-08-05T12:05:34.422221+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-824
    target_state: Merged
    evidence_fingerprint: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
    audit_ids:
    - audit-6b3fa26bb2f6
    kind: result
    applied: true
    retired_at: '2026-08-05T12:08:33.069646+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-824
    audit_id: audit-11ec4964b81b
    attempt_id: attempt-0c343f36134c
    target_state: Done
    evidence_fingerprint: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
    status: In Validation
    audit_ids:
    - audit-11ec4964b81b
    applied: true
    created_at: '2026-08-05T12:05:34.422231+00:00'
    applied_at: '2026-08-05T12:05:39.886036+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-824
    audit_id: audit-6b3fa26bb2f6
    attempt_id: attempt-cf24920ef4f4
    target_state: Merged
    evidence_fingerprint: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
    status: Merged
    audit_ids:
    - audit-6b3fa26bb2f6
    applied: true
    created_at: '2026-08-05T12:08:33.069659+00:00'
    applied_at: '2026-08-05T12:08:42.268383+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-11ec4964b81b
    project_id: proj-14849f1b
    task_id: OOMPAH-824
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
    attempts:
    - version: 1
      attempt_id: attempt-0c343f36134c
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
      created_at: '2026-08-05T11:57:27.667364+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T11:57:27.667364+00:00'
      branch_key: OOMPAH-824
      verdict: pass
      completed_at: '2026-08-05T12:05:34.422121+00:00'
      ended_at: '2026-08-05T12:05:34.422121+00:00'
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-05T11:56:58.531869+00:00'
    updated_at: '2026-08-05T12:05:34.422121+00:00'
  - version: 1
    audit_id: audit-6b3fa26bb2f6
    project_id: proj-14849f1b
    task_id: OOMPAH-824
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
    attempts:
    - version: 1
      attempt_id: attempt-cf24920ef4f4
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
      created_at: '2026-08-05T12:07:21.908376+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T12:07:21.908376+00:00'
      branch_key: OOMPAH-824
      verdict: pass
      completed_at: '2026-08-05T12:08:33.069531+00:00'
      ended_at: '2026-08-05T12:08:33.069531+00:00'
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-05T11:56:58.531869+00:00'
    updated_at: '2026-08-05T12:08:33.069531+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-0c343f36134c
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
    created_at: '2026-08-05T11:57:27.667364+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T11:57:27.667364+00:00'
    branch_key: OOMPAH-824
  - version: 1
    attempt_id: attempt-cf24920ef4f4
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2701e4eaf3dd9b3fd75638852536efecd3bd04b8657a3c9ff02a3081cb7b5536
    created_at: '2026-08-05T12:07:21.908376+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T12:07:21.908376+00:00'
    branch_key: OOMPAH-824
oompah.task_costs:
  total_input_tokens: 44
  total_output_tokens: 8278
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 44
      output_tokens: 8278
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 32
    output_tokens: 5828
    cost_usd: 0.0
    recorded_at: '2026-08-05T12:05:55.916965+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 12
    output_tokens: 2450
    cost_usd: 0.0
    recorded_at: '2026-08-05T12:08:55.156973+00:00'
---
## Summary

The currently deployed main server at a165ee90e includes the lifecycle hot-loop repair but not systemic child OOMPAH-816. The oompah project must remain paused because terminal auditors can still launch broad/full pytest commands concurrently with exact BranchQualityGate runs, recreating I/O starvation and nondeterministic gate failures. After OOMPAH-816 reaches Done at an independently reviewed exact head, port the same logical validation-resource-lease commits onto then-current main as a standalone deployment bootstrap. Scope: preserve the process-safe/restart-safe configured validation lease; exact gate priority and cache/authority lock ordering; durable waiter/owner fencing; PID-safe cancellation and descendant handling; strict heavyweight command classification across shell segments/native launchers; post-acquire liveness/runtime accounting; ACP/Codex authority-generation matching; and informational observability. Reconcile main-only changes without broadening authority or copying unrelated epic work. Relevant files include oompah/validation_resource_lease.py, quality_gate.py, api_agent.py, acp_tools.py, codex_agent.py, config.py, orchestrator.py, server.py, native wrapper/launcher helpers, .env.example, and corresponding tests. Required verification: the complete OOMPAH-816 focused lease/gate/liveness/classifier/native/Codex/config/API matrix; explicit exact-gate versus auditor concurrency and crash/restart/cancellation reproducers; terminal mutation scan; secret/diff checks; canonical full make test; independent exact-head review; merge to main; controlled make restart; live proof that a queued auditor cannot launch a competing heavyweight pytest tree. Acceptance: the deployed /healthz revision contains the reviewed OOMPAH-816 lease, normal waits are non-actionable and self-clearing, no unrelated process is terminated, and proj-14849f1b can be safely unpaused for OOMPAH-821/807 and downstream server dispatch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 11:23
---
Bootstrapped the complete independently passed OOMPAH-816 validation-arbitration delta onto current main in one clean standalone commit 476cf5514514. Exactly 25 requested paths changed; 19 resulting blobs are byte-identical to OOMPAH-816 final head. The six differences only omit workflow-shadow/job/task-transition resources absent from main while preserving main lifecycle and identical validation lease/gate/classification/liveness/evidence/snapshot semantics. Verification: core 9-file matrix 515/515, containment 4-file matrix 374/374 (889 total), terminal mutation scan 8/8, secret scan and diff check pass; independent exact-head review PASS; branch clean and pushed.
---
author: oompah
created: 2026-08-05 11:23
---
Bootstrapped exact heavyweight-validation arbitration onto main; 889 focused/containment tests and required scans pass at independently reviewed head 476cf5514514.
---
author: oompah
created: 2026-08-05 11:34
---
Branch quality gate passed for `476cf5514514ba70c8641a3a908c0d0eb7ccfe79` using `make test` in 637.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-05 11:44
---
YOLO: CI tests failed on MR #720. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-08-05 11:44
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #33)

**State audited:** `Needs CI Fix`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Recent comment indicates CI is now passing or PR has been merged; safe to reopen for dispatch.
**Evidence head:** `476cf5514514ba70c8641a3a908c0d0eb7ccfe79`
**Evidence result:** `comment_ci_passing`

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-05 11:48
---
GitHub CI exposed a runner-specific bug: PATH may contain a nonexistent optional directory (/snap/bin), while native guard discovery deferred directory iteration beyond its OSError handler. Fixed at exact pushed head 50d19fe5d932421111494403c9b0160d5f2e35f4 by eagerly enumerating each PATH directory inside the guarded block and skipping stale/unreadable entries, matching shutil.which behavior. Added an exact missing-PATH-entry regression. Focused native guard + Codex backend suite: 78 passed; terminal mutation scan and secret scan passed. PR #720 CI is rerunning.
---
author: oompah
created: 2026-08-05 11:50
---
Repaired GitHub CI PATH enumeration failure at exact pushed head 50d19fe5d932421111494403c9b0160d5f2e35f4. Native validation guard now skips nonexistent/unreadable PATH directories, with an exact regression; 78 focused tests, terminal scan, secret scan, diff check, and independent review pass.
---
author: oompah
created: 2026-08-05 11:57
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 11:57
---
YOLO: merged PR #720.
---
author: oompah
created: 2026-08-05 11:57
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 11:57
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 12:05
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- main_head: c14ca03f59078e6df06871488cf78f04477acb11
- merge_pr: #720
- branch_head_before_merge: 50d19fe5d932421111494403c9b0160d5f2e35f4
- delta_paths_changed: 25
- delta_insertions: 5218
- delta_deletions: 224
- focused_tests_lease: 131 passed
- focused_tests_native_guard: 11 passed
- focused_tests_quality_gate: 81 passed
- focused_tests_codex_liveness_config: 210 passed
- focused_tests_orchestrator: 346 passed
- focused_tests_provider_gitlab_bounds_heartbeat: 111 passed
- total_focused_passes: 890
- prior_full_gate_seconds: 637.2
- prior_full_gate_head: 476cf5514514ba70c8641a3a908c0d0eb7ccfe79
---
author: oompah
created: 2026-08-05 12:05
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/opus]
- Turns: 36, Tool calls: 26
- Tokens: 32 in / 5.8K out [5.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 24s
- Log: OOMPAH-824__20260805T115740Z.jsonl
---
author: oompah
created: 2026-08-05 12:07
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 12:07
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 12:08
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- main_head: c14ca03f59078e6df06871488cf78f04477acb11
- merge_pr: #720
- merge_commit_message: Merge pull request #720 from lesserevil/OOMPAH-824
- branch_head_merged: 50d19fe5d932421111494403c9b0160d5f2e35f4
- prior_bootstrap_commit: 476cf5514514ba70c8641a3a908c0d0eb7ccfe79
- pre_merge_main: a165ee90e
- branch_contained_in_main: true
- prior_full_gate_seconds: 637.2
- prior_full_gate_head: 476cf5514514ba70c8641a3a908c0d0eb7ccfe79
- prior_total_focused_passes: 890
---
author: oompah
created: 2026-08-05 12:08
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=auditor, role=auditor -> Claude/opus]
- Turns: 11, Tool calls: 6
- Tokens: 12 in / 2.5K out [2.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 31s
- Log: OOMPAH-824__20260805T120734Z.jsonl
---
author: oompah
created: 2026-08-05 12:21
---
Post-deploy live arbitration proof on revision c14ca03f59078e6df06871488cf78f04477acb11: while exact OOMPAH-825 gate generation c7cfc68cbb234f6ebd35b38c2b00aa91 owned slot 0/capacity 1, a native broad auditor pytest probe registered as an auditor waiter (priority 10) and its executable payload marker remained absent. Withdrawing the probe authority returned rc=1, removed the durable waiter, launched no payload, and left OOMPAH-825 as the sole owner. A focused one-test control was intentionally classified light. No unrelated process was terminated and final capacity state retained only the live exact gate.
---
<!-- COMMENTS:END -->
