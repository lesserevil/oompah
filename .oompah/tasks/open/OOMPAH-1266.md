---
id: OOMPAH-1266
type: bug
status: Open
priority: 1
title: Fence late task submission from regressing landed integration authority
parent: OOMPAH-1231
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T04:54:34.556175Z'
updated_at: '2026-08-21T02:12:53.716898Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: o1263-post-merge-submit-provenance-regression
  request_fingerprint: 9a9d8d03687f81678f5061a4c7f6ca12b789b64399e6fd9b92b89ef14dc3e4b5
oompah.lifecycle_revision: 1
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9f3a0a5a59f2a06ff79051089822dbfee82b28352e54ad90889e4e0d3419a375
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 078958f870b3ee75bf1b37df2d2205c9ece78fb6b6684bd1e0152cf5de0c467b:142895
  claim_owner: 884c7b0a-4fe0-4acd-9fe6-041416485094
  claimed_at: '2026-08-21T02:10:11.245832+00:00'
  claim_expires_at: '2026-08-21T02:40:11.245832+00:00'
  retry_count: 2
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4653f428-6485-4215-968e-7c5b999c24f6
oompah.work_contributors:
  runs:
  - run_id: 0f8450b3837a46cb84d3b7f0335aff70--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1266
    source_sha: null
    completed_at: ''
  - run_id: 49e4ee0f510f42e7af04dded2e2b1e4d--contributor-a8b0475e7b09
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-1266
    source_sha: null
    completed_at: ''
  - run_id: 7cf71eef56cc4a9ebb9ba7f9f4dcf97f--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1266
    source_sha: null
    completed_at: ''
---
## Summary

A pull-request closed+merged webhook can stage terminal evidence before a delayed `oompah task submit` arrives. Reproduced on OOMPAH-1263: PR 880 merged into epic-OOMPAH-1231 and staged Done, then the later submit replaced the landed/integrated projection with a `ready` IntegrationRecord at reviewed head 987c46c. The active audit retained the earlier fingerprint, so every owner override returned terminal fingerprint mismatch until a fresh normal Done request superseded the stale audit. Implement an atomic authority fence across submission, integration queue, native tracker integration metadata, and merged-review reconciliation so a late or retried submit cannot change an integrated generation back to ready or cause duplicate delivery. If the review is already merged, either preserve/repair the exact integrated record using forge-confirmed landed SHA or reject the stale submit with an actionable idempotent result. Add regression tests for webhook-before-submit, submit-before-webhook, lost-response retry, restart between the two events, mismatched head/base, and concurrent replacement generation. Verify terminal fingerprint remains stable and the task cannot be reintegrated. Relevant areas: task submit API/service, integration_queue CAS, native integration metadata, PR webhook/reconciliation, terminal fingerprint tests. Acceptance: exact landed authority is monotonic, same-generation late submits are idempotent, mismatched submissions fail closed, and terminal override/audit no longer deadlocks after this ordering.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 04:56
---
Claimed directly on branch OOMPAH-1266 in /home/shedwards/src/oompah-1266 from origin/epic-OOMPAH-1231. Reproducing the webhook-before-submit metadata regression and implementing the smallest monotonic integration-authority fence with same-generation retry idempotency and replacement fail-closed coverage. I will not push, submit, or change terminal status.
---
author: oompah
created: 2026-08-14 05:13
---
Implementation complete on local branch OOMPAH-1266 at 91a0d0842784bd42aba8324c86a4a6b026b4dbba. The submit path now preserves exact integrated tracker authority, rejects changed head/base generations, repairs the queue-first restart gap, and avoids queue rearm, lifecycle regression, duplicate coordination, or validation reflow after landing. Integrated queue rows are immutable under exact retry/replacement races, and landed retry retirement is generation-fenced so a successor worker survives. Regression coverage includes webhook-before-submit, submit-before-webhook, lost-response retry, restart gap, mismatched head/base, concurrent replacement, terminal fingerprint stability, and durable authority retirement. Verification: 928 tests passed across submission, handoff, queue, webhook, integration/review workflow, implementation fencing, and terminal fingerprint/transition suites. Focused Ruff checks pass for the directly changed queue/adapter and their new tests; the broad server/test invocation reports pre-existing lint debt outside this change. Per coordination instructions, this commit is local only: not pushed, submitted, or status-transitioned.
---
author: oompah
created: 2026-08-14 05:59
---
Review blockers resolved on local branch OOMPAH-1266 at 2653bdd799f4d89b3629a5f11d065522df0f415d. The first-submit path now adopts an exact already-merged forge review under the task lock using two matching immutable observations (including merge SHA and repository identity); GitLab merged-list observations hydrate missing base identity from exact MR detail. Queue/tracker opposite crash windows reconcile through transactional queue CAS, including claim/finish races and a submit-vs-completion race, while mismatched nonterminal generations retire fail-closed. OOMPAH-628 explicit fresh-Ready reflow is preserved with durable tracker-vs-queue checkpoint ordering, and verified later Ready generations may replace historical integrated rows without weakening default landed authority. Rebase predecessor head+base authority is persisted in queue schema v7 and bound into integrated records so wrong-base retries fail and exact lost-201 retries remain idempotent. Terminal fingerprint migration is bounded to that service-authored accepted predecessor. Verification: 1,487 broad submission/queue/handoff/fencing/webhook/integration/review/terminal/SCM tests passed; 225 workflow-runtime/parallel-epic tests passed; task-status mutation scan passed; focused Ruff checks passed; commit hooks and paranoid secret scans passed. Per coordination instructions this commit remains local only: not pushed, submitted, status-transitioned, or deployed.
---
author: oompah
created: 2026-08-20 23:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-20 23:14
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-20 23:15
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 55s
- Log: OOMPAH-1266__20260820T231442Z.jsonl
---
author: oompah
created: 2026-08-21 00:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 00:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 00:27
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 16s
- Log: OOMPAH-1266__20260821T002627Z.jsonl
---
author: oompah
created: 2026-08-21 02:11
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:12
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
