---
id: OOMPAH-982
type: bug
status: Merged
priority: 1
title: Retire implementation recovery when direct owner holds authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T02:54:36.526201Z'
updated_at: '2026-08-10T06:27:16.336732Z'
work_branch: OOMPAH-982
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/790
review_number: '790'
review_head: 450f909a18cc42b97d7c91619cd55a07e14445e0
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-982
  base_branch: main
  base_sha: 148db44a97e42140160a428bd11eed2c50f75381
  head_sha: e96ed93c944bca7c5f5ac8e65aede731b5ab862d
  submitted_at: '2026-08-10T05:38:30.551526+00:00'
  updated_at: '2026-08-10T05:38:30.551526+00:00'
oompah.work_branch: OOMPAH-982
oompah.review_url: https://github.com/lesserevil/oompah/pull/790
oompah.review_number: '790'
oompah.target_branch: main
oompah.review_head: 450f909a18cc42b97d7c91619cd55a07e14445e0
oompah.agent_run_id: null
oompah.work_contributors:
  runs:
  - run_id: a1e1fbab0ebd4f37ac8a8d39ddb6b9d4--contributor-9efe7fcc211b
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-982
    source_sha: null
    completed_at: ''
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-18dbb68ac73b
    project_id: proj-14849f1b
    task_id: OOMPAH-982
    digest: b591ef7d63f4a3fc1f6cb91a452df51f37015ea241c1904a830da921d6957006
  - version: 1
    audit_id: audit-759471ea069e
    project_id: proj-14849f1b
    task_id: OOMPAH-982
    digest: b591ef7d63f4a3fc1f6cb91a452df51f37015ea241c1904a830da921d6957006
  oompah.terminal_override_records:
  - version: 1
    override_id: override-a0800222c141
    project_id: proj-14849f1b
    task_id: OOMPAH-982
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b591ef7d63f4a3fc1f6cb91a452df51f37015ea241c1904a830da921d6957006
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-10T06:27:04.597192+00:00'
    selected_ref: e96ed93c944bca7c5f5ac8e65aede731b5ab862d
    selected_sha: e96ed93c944bca7c5f5ac8e65aede731b5ab862d
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-982
    target_state: Merged
    evidence_fingerprint: b591ef7d63f4a3fc1f6cb91a452df51f37015ea241c1904a830da921d6957006
    audit_ids:
    - audit-18dbb68ac73b
    - audit-759471ea069e
    kind: override
    applied: true
    retired_at: '2026-08-10T06:27:14.738835+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-18dbb68ac73b
    project_id: proj-14849f1b
    task_id: OOMPAH-982
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b591ef7d63f4a3fc1f6cb91a452df51f37015ea241c1904a830da921d6957006
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-10T06:26:40.489947+00:00'
    selected_ref: e96ed93c944bca7c5f5ac8e65aede731b5ab862d
    selected_sha: e96ed93c944bca7c5f5ac8e65aede731b5ab862d
    updated_at: '2026-08-10T06:27:14.738794+00:00'
  - version: 1
    audit_id: audit-759471ea069e
    project_id: proj-14849f1b
    task_id: OOMPAH-982
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b591ef7d63f4a3fc1f6cb91a452df51f37015ea241c1904a830da921d6957006
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-10T06:26:40.489947+00:00'
    selected_ref: e96ed93c944bca7c5f5ac8e65aede731b5ab862d
    selected_sha: e96ed93c944bca7c5f5ac8e65aede731b5ab862d
    updated_at: '2026-08-10T06:27:14.738818+00:00'
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-981

Live reproduction on OOMPAH-981: after a supported direct-owner claim became active and the task was correctly In Progress, the durable implementation_recovery job continued invoking dispatch. Dispatch correctly denied it with direct_owner_claim, but the workflow treated that expected ownership fence as a retryable failure, consumed all five attempts, and exhausted. Scope: make implementation recovery recognize an exact current direct-owner claim as successful/superseded recovery ownership instead of attempting scheduler dispatch; retire any stale retry generation without revoking the owner; preserve automatic recovery for truly orphaned tasks and fail closed for expired, mismatched, retirement-pending, or cross-project claims. Relevant code includes implementation recovery revalidation/apply/verify, direct-owner fact projection, retry classification, restart reconstruction, and liveness job authority. Required tests: active exact owner claim produces no dispatch and no retry/exhaustion; claim installed during recovery wins the race; expired/released/replaced claim resumes ordinary recovery; restart with a retained claim converges idempotently; cross-task/project claims do not suppress recovery; and no stale recovery job revokes an ABA replacement. Acceptance: a directly owned In Progress task has no current implementation_recovery retry or exhausted job, zero false operator warning, and ordinary orphan recovery remains bounded; focused tests and the complete project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 02:55
---
Claimed for direct-owner completion from the exact OOMPAH-981 live exhausted recovery generation. A separate implementation branch is being worked in parallel with OOMPAH-981.
---
author: oompah
created: 2026-08-10 03:15
---
The exact direct-owner/recovery race fix is implementation-complete. Focused suites pass (152 tests from implementation workflow coverage); independent review and the complete 19,297-test branch gate are in progress.
---
author: oompah
created: 2026-08-10 03:19
---
Implemented exact direct-owner authority supersession for stale implementation recovery. Recovery now retires without dispatch, receipt, retry, exhaustion, or claim revocation across pre-admission, policy, final-dispatch, ABA, expiry, and real durable restart races. Focused implementation suites pass (152); independent review approved.
---
author: oompah
created: 2026-08-10 03:28
---
Branch quality gate passed for `450f909a18cc42b97d7c91619cd55a07e14445e0` using `make test` in 164.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-10 04:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-10 04:10
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-10 04:11
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 0s
- Log: OOMPAH-982__20260810T041046Z.jsonl
---
author: oompah
created: 2026-08-10 04:12
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 24s
- Log: OOMPAH-982__20260810T041046Z.jsonl
---
author: oompah
created: 2026-08-10 05:38
---
Direct-owner rebase repair: exact reviewed patch replayed without conflicts onto origin/main 148db44a97e42140160a428bd11eed2c50f75381 at new head e96ed93c944bca7c5f5ac8e65aede731b5ab862d. Range-diff is patch-identical; only implementation_workflow_adapter.py and its test changed. Focused adapter/worker/refresh/runtime matrix passed 60/60; terminal mutation scan and diff check passed. Force-pushed with exact lease against old remote 450f909a18cc42b97d7c91619cd55a07e14445e0; PR #790 head verified exact.
---
author: oompah
created: 2026-08-10 05:38
---
Rebased exact direct-owner recovery fix onto landed OOMPAH-983/984/985 graph at e96ed93c944bca7c5f5ac8e65aede731b5ab862d; patch-equivalent range-diff and 60 focused tests pass.
---
author: oompah
created: 2026-08-10 06:25
---
Exact full branch gate passed at unchanged pushed head e96ed93c944bca7c5f5ac8e65aede731b5ab862d after OOMPAH-986 deployment: make test completed with 19,302 passed, 7 skipped, 2 xfailed, 48 warnings in 1,385.42s. Worktree is clean and origin/OOMPAH-982 resolves to the same exact head. This directly validates the replacement delivery after the stale implementation-recovery row moved the task back to In Progress during restart.
---
author: oompah
created: 2026-08-10 06:26
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-10 06:27
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: [REDACTED]
---
<!-- COMMENTS:END -->
