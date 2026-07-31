---
id: OOMPAH-650
type: bug
status: In Progress
priority: 1
title: Keep scoped task handoff credentials valid for the full worker lifetime
parent: OOMPAH-619
children: []
blocked_by:
- OOMPAH-652
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T08:57:09.832838Z'
updated_at: '2026-07-31T09:10:36.818145Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-650
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a045feb3c4e136514e5067edcf8e10cd8e6ddf01b44eef220fd15192a76e1c6b
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T09:10:26.973037+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: Reviewed complete active records for OOMPAH-619,\
    \ 623, 645, 649, 651, 652, and 653. Each covers a distinct issue; OOMPAH-645 explicitly\
    \ tracks this credential-lifetime defect separately. Merged OOMPAH-646 was excluded.\
    \ No files or tracker state were modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 9edc9ae9-678c-4ade-8b4c-8bfcb475e367
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-650
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-619--task-OOMPAH-650
  base_branch: epic-OOMPAH-619
  base_sha: 0dc7d0f7caeea06a6eceb55ea2e58cf16554f0a4
  updated_at: '2026-07-31T09:07:21.802007+00:00'
oompah.task_costs:
  total_input_tokens: 1605589
  total_output_tokens: 7905
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1605589
      output_tokens: 7905
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1605589
    output_tokens: 7905
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:10:26.970500+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-650__20260731T090726Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-619--task-OOMPAH-650
    source_sha: 0dc7d0f7caeea06a6eceb55ea2e58cf16554f0a4
    completed_at: '2026-07-31T09:10:27.032754+00:00'
---
## Summary

Live reproduction on 2026-07-31: an active OOMPAH-646 worker inherited OOMPAH_TASK_HANDOFF_TOKEN, but the capability expired while that worker was still running. Every permitted oompah task view then selected the expired scoped capability and returned 401; unsetting the token exposed reusable operator Basic credentials and worked, but spawned workers must never need or inherit that fallback. Implementation scope: bind task-handoff grant lifetime to the owning live worker/session rather than a shorter wall-clock lease, renew or rotate grants safely across long tool calls and graceful service restarts, revoke them exactly when ownership ends, and return an explicit expired/revoked diagnostic that distinguishes auth transport failure from task failure. Keep the capability task/project/action scoped and do not weaken the prohibition on reusable operator credentials in worker environments. Relevant files: oompah/task_handoff.py, orchestrator worker launch/termination/restart recovery, task_cli.py, ACP backend environment injection, and auth-health reporting. Required tests: a worker outliving the current grant TTL can view/comment/submit; long tool activity keeps the grant usable; restart recovery preserves or atomically replaces the grant; termination/retry revokes the old grant; cross-task/project/action use remains denied; no Basic-auth fallback. Acceptance: a live worker never receives 401 solely because its task-scoped credential aged out, stale workers remain unable to mutate tasks, focused auth/handoff tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 08:59
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 08:59
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 09:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:08
---
Additional live evidence: OOMPAH-645 completed focused verification on clean pushed head 6686290d5, but its post-worker task handoff failed at 08:58. After operator reconciliation and a server restart, a fresh standard worker repeated the same post-run handoff failure at 09:04 and the task returned to Needs Human again. The task is now intentionally held with finish-order dependencies on OOMPAH-650/OOMPAH-652 to stop redispatch churn. Cover both TTL expiry and restart/revocation/reissue paths; a newly launched post-restart worker must receive a valid server-owned capability through its final submit.
---
author: oompah
created: 2026-07-31 09:10
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 45
- Tokens: 1.6M in / 7.9K out [1.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 10s
- Log: OOMPAH-650__20260731T090726Z.jsonl
---
<!-- COMMENTS:END -->
