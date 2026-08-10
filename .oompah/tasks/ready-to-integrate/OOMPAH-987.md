---
id: OOMPAH-987
type: bug
status: Ready to Integrate
priority: 1
title: Prevent post-gate auditor inspection from blocking behind the next full gate
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T04:50:28.752372Z'
updated_at: '2026-08-10T05:48:01.134154Z'
work_branch: OOMPAH-987
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-987
  head_sha: dcfbceebeab1e489e88a87dc9e8da6b6ddff8623
  submitted_at: '2026-08-10T05:47:48.858881+00:00'
  updated_at: '2026-08-10T05:47:48.858881+00:00'
oompah.work_branch: OOMPAH-987
---
## Summary

Triggered by: OOMPAH-983

Live reproduction on 2026-08-10: OOMPAH-983 terminal audit attempt attempt-315a836a8421 completed its exact-head make test successfully at 04:43:10 UTC with 19,279 passed, 7 skipped, and 2 xfailed. OOMPAH-981 then acquired the capacity-1 validation resource for another full gate at 04:43:24. At 04:44:22 the already-validated OOMPAH-983 auditor requested read-only git diff HEAD~1 HEAD tests/test_workflow_runtime.py. The command was classified heavyweight/opaque because effective system, user, and worktree Git configuration contains executable helper surfaces such as filter.lfs, credential.helper, and core.hooksPath. No git child launched; the ACP log remained at permission_grant and OOMPAH-983 stayed In Validation behind the unrelated twenty-minute OOMPAH-981 gate. This is distinct from OOMPAH-810 completed-result delivery, OOMPAH-816/852 validation oversubscription, OOMPAH-862/980 redundant full-gate reuse, and OOMPAH-905 eventual waiter fairness: capacity serialization is working, but a completed audit cannot promptly submit because redundant post-gate inspection enters a long unrelated queue.\n\nImplementation scope: make the completion-auditor contract order or constrain inspection so an auditor that has just received successful full-gate evidence cannot enqueue an inspection-shaped Git command behind a later heavyweight gate before submitting its verdict. Prefer a structured bounded helper-free inspection path or a recoverable post-gate response directing the auditor to read_file/search_files and the already captured diff evidence; do not weaken fail-closed Git helper/config classification, execute task-controlled helpers, retain the validation lease while the model reasons, or give one task unbounded priority over unrelated exact gates. Record post-gate command disposition and enough evidence to diagnose any intentional supplemental validation. Preserve independent review, exact-head/evidence fencing, command-result delivery, cancellation, restart behavior, and validation capacity 1.\n\nRelevant code: oompah/auditor.py and prompt rendering, oompah/api_agent.py run_command/reuse lifecycle, oompah/validation_resource_lease.py Git classification, terminal-audit telemetry, and related auditor/validation tests.\n\nRequired tests: reproduce two auditors with capacity 1 where A completes a full gate, B acquires a long full gate, and A next asks for inspection-shaped git diff; A receives a bounded recoverable/structured result and can submit exactly once without waiting for B. Prove executable Git config and helper flags remain fail closed and never spawn helpers; pre-gate or genuinely required supplemental validation still queues correctly; already captured exact diff/full-gate evidence remains available; restart, cancellation, result delivery, and exact evidence supersession remain correct. Include focused auditor, ACP, validation-resource, and terminal-audit tests plus make test.\n\nAcceptance criteria: after a terminal auditor receives a successful exact full-gate result, unrelated later validation owners cannot delay its verdict solely because of redundant read-only repository inspection; OOMPAH-983-shaped flow reaches terminal disposition promptly while all Git helper and validation-capacity safety guarantees remain intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 04:51
---
Direct owner claim active as 6e38711da07b4fb995f0775852d4c0b6. Live OOMPAH-983 evidence confirms the exact failure mode: its successful full-gate result was delivered, then inspection-shaped Git was classified heavyweight/opaque from executable effective Git config and queued with no child behind OOMPAH-981. Implementation is intentionally deferred until the current OOMPAH-981/OOMPAH-983/OOMPAH-984 validation activity drains so this repair does not contend with or invalidate in-flight exact evidence.
---
author: oompah
created: 2026-08-10 05:21
---
Implemented and pushed exact head d22d5d4a4fc4897241dba03ac62fdea2758459df on branch OOMPAH-987. The fix remembers a successful required full gate only within the exact active auditor session, denies later opaque/non-focused heavyweight inspection before validation-capacity acquisition, preserves focused and explicitly justified distinct validation, applies the fence to bridged API and native Codex command paths, and records denied_post_gate_inspection telemetry. Fail-closed Git helper/config classification and capacity=1 behavior are unchanged. Validation: 902 passed across test_validation_resource_lease.py, test_native_validation_guard.py, test_quality_gate.py, and test_auditor_contract.py; 73 passed in test_terminal_audit_observability.py; 4 focused ACP policy-threading tests passed; 6 focused end-to-end policy/queue/telemetry regressions passed; make terminal-audit-scan passed; make check-secrets passed; git diff --check passed; pre-commit hooks passed. Branch is clean and up to date with origin. Awaiting independent review before submission.
---
author: oompah
created: 2026-08-10 05:40
---
Independent-review blocker fixed and pushed at exact head dcfbceebeab1e489e88a87dc9e8da6b6ddff8623. Session-local gate completion now requires a nonempty configured command and exact outer-whitespace-normalized command identity; classification.contains_configured is no longer pass proof. Regressions cover configured make test exiting 17 while make test || true exits 0 on both bridged API and native Codex paths: the compound command remains fail-closed/capacity-bearing, never sets _session_full_gate_passed, and the next opaque Git command is not misclassified as post-gate. Exact gate success still fences redundant inspection. Validation: 909 passed across the four affected modules in 136.09s; 7 exact identity/masked-failure regressions passed; make terminal-audit-scan passed; make check-secrets passed; git diff --check and pre-commit hooks passed. Branch is clean and up to date with origin. Awaiting renewed independent review before submission.
---
author: oompah
created: 2026-08-10 05:47
---
Prevent post-gate auditor inspection from blocking behind the next full gate. Exact head dcfbceebeab1e489e88a87dc9e8da6b6ddff8623 independently approved after masked compound-command gate evidence was fixed; 1,291 review tests and 909 affected-module tests pass.
---
<!-- COMMENTS:END -->
