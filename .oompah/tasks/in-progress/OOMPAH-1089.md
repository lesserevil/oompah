---
id: OOMPAH-1089
type: bug
status: In Progress
priority: 1
title: Regenerate current review jobs after stale-evidence exhaustion
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T14:22:55.237924Z'
updated_at: '2026-08-11T14:42:24.622310Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: review-stale-evidence-regeneration-20260811
  request_fingerprint: 632471a88f61cd821faefecc9c5fba392deb4e027a77c57f2d54abfef736019d
---
## Summary

Triggered by: OOMPAH-1086

Live incident: after deploying exact review-generation synchronization on 2026-08-11, OOMPAH-1086 had open PR 823 at exact head 6dedb86fa1b6e4b310482bd5c5c1d2931c82981f, a current-main merge candidate, all protected Python 3.11/3.12/3.13 checks green, an accepted exact-head independent review, and work decision review.ready_to_merge. The durable review_merge effect then exhausted on its first attempt with stale_evidence: review, repository, branch, or exact head identity changed. The next projection became critical retry.exhausted with no durable job, even though this identity/base evolution is a normal optimistic-concurrency race that should generate fresh exact authority. OOMPAH-1087 showed the same terminal retry projection after its base generation changed. Scope: classify review identity, head, repository, branch, and target-base changes observed between intent, revalidation, effect, and observation as superseded generation when a current valid open review can be re-observed; enqueue exactly one fresh review monitor, gate, or merge job for the new evidence; preserve fail-closed behavior and bounded retries for genuinely unavailable, malformed, forked, conflicting, or policy-invalid reviews; and ensure retry budgets are generation-scoped rather than poisoning a newer evidence generation. Required tests: identity enrichment after deployment, base-only advance, head advance, synchronize during merge intent, restart between stale detection and regeneration, and repeated webhook/poll races must all supersede stale authority and converge to one current job; stale authority must never merge; missing review, wrong repo/base/source, conflicts, and persistent provider errors must remain actionable after bounded attempts. Acceptance: normal review evidence changes cannot strand an otherwise valid In Review task in retry.exhausted, current exact authority is regenerated automatically, focused review/workflow/liveness tests and terminal mutation scan pass, and protected CI is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 14:23
---
Direct owner claimed from the live OOMPAH-1086 and OOMPAH-1087 evidence. OOMPAH-1086 review_merge job workflow-job-6f277655ecc4449db3147f82222169b0 exhausted at effect_pending on its first stale-evidence observation despite PR 823 being open, exact-head green, current-main mergeable, and independently accepted. Repair is starting from deployed main 6a0f7210 with generation-scoped stale-evidence regeneration tests.
---
author: oompah
created: 2026-08-11 14:42
---
Live evidence confirmed both OOMPAH-1086 and OOMPAH-1087 review_merge jobs exhausted at effect_pending after one stale_evidence refusal. OOMPAH-1086's accepted integration record lacked base_branch/base_sha while the fresh PR 823 observation supplied a complete exact same-repository identity, so selection reached merge but the strict effect correctly refused it. Repair now routes missing accepted base identity through exact head/base reconciliation, supersedes an old merge effect when the second observation or forge CAS proves a valid newer review generation, and rearms stale exhaustion only for a complete non-forked non-conflicting current review identity. Wrong repositories/source/base, conflicts, missing reviews, and provider errors stay fail-closed. Green so far: 387 review/runtime/liveness tests, 74 architecture/churn tests, terminal mutation scan 21/21, production Ruff and py_compile.
---
<!-- COMMENTS:END -->
