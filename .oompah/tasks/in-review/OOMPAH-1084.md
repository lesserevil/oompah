---
id: OOMPAH-1084
type: task
status: In Review
priority: null
title: Propagate synchronized open-review heads into exact gate and merge authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T12:18:01.834270Z'
updated_at: '2026-08-11T13:33:20.930373Z'
work_branch: OOMPAH-1084
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/821
review_number: '821'
review_head: 15a2ee7c9b82cfefb49a00173c302c095f3ca46e
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: cf39693e-0c40-4a0f-b906-d1d9f0f32091
  request_fingerprint: 0c291c7dc884f23ab6ff6da8a48bacb3bb0abc28b37aa4ba995855e97b708aa2
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1084
  head_sha: 15a2ee7c9b82cfefb49a00173c302c095f3ca46e
  submitted_at: '2026-08-11T12:41:57.981846+00:00'
  updated_at: '2026-08-11T12:41:57.981846+00:00'
oompah.work_branch: OOMPAH-1084
oompah.review_url: https://github.com/lesserevil/oompah/pull/821
oompah.review_number: '821'
oompah.target_branch: main
oompah.review_head: 15a2ee7c9b82cfefb49a00173c302c095f3ca46e
---
## Summary

Triggered by live PR 819 / OOMPAH-1082 on 2026-08-11. The task had adopted/local-gated review head a2d82..., then the draft PR and branch synchronized to 4af426... with fresh protected CI. GitHubProvider.list_open_reviews constructed ReviewRequest without head_sha even though the GitHub list payload contained it. Consequently work_decision could not emit review.head_changed, the durable task integration/review heads and gate PASS remained a2d82, periodic reassessment could not heal them, and undrafting could permit 4af426 to merge under stale a2d82 local authority. Scope: propagate exact open-review head SHA (and any required source/base identity) from provider projections through work-decision/review monitoring; on synchronized draft or ready PR head change, revoke stale review/gate/merge authority, return/requeue the task through exact Ready-to-Integrate delivery gating, persist/adopt only the new head, and fail closed until branch gate and review authority match. Preserve fork/source/base validation, PR identity, task/project scope, idempotent repeated webhooks/polls, concurrent synchronize/undraft ordering, restart recovery, and protected-workflow import behavior. Relevant code: oompah/scm.py list_open_reviews, ReviewRequest, work_decision.py review.head_changed, review monitor/delivery transitions, integration/review/gate stores, GitHub webhook/poll tests. Required tests: adopted head A + draft PR synchronize to B must expose observed head B, revoke A, gate/adopt B, and never mark ready/merge using A; same race with undraft/check completion fails closed; repeated polls/webhooks coalesce; wrong fork/base/source/PR and advanced C cannot reuse B; restart between revocation and B gate converges once; GitHub API degradation remains fail closed. Acceptance: task integration head, review head, branch gate PASS, PR head, and eventual merge head must be the same exact SHA before merge eligibility; focused tests, terminal mutation scan, and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 12:41
---
Implemented exact review generation reconciliation on branch OOMPAH-1084 after rebasing onto main d9e1c7ae6. GitHub/GitLab observations now propagate head/base/repository identity; synchronized head changes replace standalone integration authority and requeue through Ready to Integrate; review merges re-observe and use forge expected-head CAS. Focused review/provider/standalone suite: 478 passed; terminal task-status scan passed. Preparing final commit and submission.
---
author: oompah
created: 2026-08-11 12:42
---
Propagated exact PR/MR head, base, and repository identity; made synchronized review heads durably replace stale standalone integration authority and requeue through exact Ready-to-Integrate gating/adoption; fenced merge execution with fresh observations and forge atomic expected-head CAS; added restart, repeat, fork/base/source/PR, B-to-C, API/race, provider propagation, and production-shaped regating/readoption coverage. Focused suites: 478 passed; terminal-audit scan passed. Commit 15a2ee7c9b82cfefb49a00173c302c095f3ca46e pushed to origin/OOMPAH-1084.
---
author: oompah
created: 2026-08-11 12:48
---
Branch quality gate passed for `15a2ee7c9b82cfefb49a00173c302c095f3ca46e` using `make test` in 180.4s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 12:55
---
Independent exact-head review BLOCKED 15a2ee7: production-shaped A→B→C review advancement can strand the durable intermediate B head, and GitLab omitted source/target project IDs can fail open as same-repository identity. Direct owner repair is adding eventual-convergence and missing-ID regressions; the branch will require fresh independent review at its replacement exact head.
---
author: oompah
created: 2026-08-11 12:56
---
Repaired the independent-review blockers and pushed exact head 1260f6ee368ef7402fb637e81a08ec79436e20cd. A production-shaped A→B checkpoint→C sequence now schedules the fresh C reconciliation and converges to Ready to Integrate at exact C; malformed or non-ready intermediate authority still fails closed. GitLab list/find/get projections now claim same-repository source identity only when both source_project_id and target_project_id are present and equal; missing-ID and fork regressions cover fail-closed behavior. Post-commit checks: 117 adapter/standalone passed; 380 SCM/GitLab-flow passed. Earlier adjacent checks also passed: 295 review/worker/transition/standalone, 155 GitLab/merge-queue, 168 orchestrator review/merge. PR #821 is draft and CI is running. Because the reviewed head changed, 1260f6ee3 requires fresh independent review; no approval or merge performed.
---
author: oompah
created: 2026-08-11 13:33
---
Replacement exact head 575e6c358573ec1f103ea782e9168a57587da735 is pushed on origin/OOMPAH-1084, rebased directly on deployed main fe06a0ff1e0e2a2430a1190121df790595040998. It closes all three fresh-review blockers: durable base-generation synchronization forces a new gate even for the same head; active review adoption requires positive exact source and target repository identity; and Ready-to-Integrate recovery checkpoints a PR/MR that advances after verification but before tracker transition, then re-gates and adopts only the latest exact head/base. The replacement path is restricted to a valid marker for the same tracked review, so a newer independent accepted submission cannot be overwritten by stale review history. Deterministic B-to-C late-race, restart, base-only, missing-ID, fork, unmarked-submission, and cache-bypass regressions are included. Post-head evidence: standalone Ready suite 99 passed; review workflow adapter 28 passed; review/work-decision adjacent suites 215 passed; SCM/GitLab/integration suites 410 passed; provider/server GitLab suites 103 passed; full quality-gate suite 309 passed; terminal task-status mutation scan passed. Pre-commit secret and safety hooks passed. This exact head requires another independent review; no self-approval or merge was performed.
---
<!-- COMMENTS:END -->
