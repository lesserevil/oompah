---
id: OOMPAH-982
type: bug
status: In Progress
priority: 1
title: Retire implementation recovery when direct owner holds authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T02:54:36.526201Z'
updated_at: '2026-08-10T06:14:46.343967Z'
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
<!-- COMMENTS:END -->
