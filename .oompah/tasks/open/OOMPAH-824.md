---
id: OOMPAH-824
type: task
status: Open
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
updated_at: '2026-08-05T11:48:12.596874Z'
work_branch: OOMPAH-824
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/720
review_number: '720'
review_head: 476cf5514514ba70c8641a3a908c0d0eb7ccfe79
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-824
  head_sha: 476cf5514514ba70c8641a3a908c0d0eb7ccfe79
  submitted_at: '2026-08-05T11:23:49.281637+00:00'
  updated_at: '2026-08-05T11:23:49.281637+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/720
oompah.review_number: '720'
oompah.work_branch: OOMPAH-824
oompah.target_branch: main
oompah.review_head: 476cf5514514ba70c8641a3a908c0d0eb7ccfe79
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
<!-- COMMENTS:END -->
