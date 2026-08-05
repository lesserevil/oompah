---
id: OOMPAH-819
type: bug
status: In Validation
priority: 1
title: Fence Ready reconciliation against stale merged-review generations
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T03:06:28.414558Z'
updated_at: '2026-08-05T05:56:08.962641Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-819
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6ace6d18079d04a236343266e1745edd4beb5c3ae6ad187f5e609d94a3ad5cc8
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T05:31:13.396384+00:00'
  matched_identifiers: []
  evidence: 'OOMPAH-820 is the terminal standalone bootstrap, but OOMPAH-819 has distinct
    accepted epic-lineage accounting: the same reviewed patch must be recorded on
    epic-OOMPAH-768 before program rollup.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-05T05:31:13.396384+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: 'OOMPAH-820 is the terminal standalone bootstrap, but OOMPAH-819
    has distinct accepted epic-lineage accounting: the same reviewed patch must be
    recorded on epic-OOMPAH-768 before program rollup.'
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-819
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-768--task-OOMPAH-819
  base_branch: epic-OOMPAH-768
  base_sha: eb5d206f2fc040698808130b2629a997c3c9b953
  head_sha: ce2526a8b7e67426c3919cf890a9b3b1cdca20ad
  integrated_sha: ce2526a8b7e67426c3919cf890a9b3b1cdca20ad
  submitted_at: '2026-08-05T05:34:40.842315+00:00'
  updated_at: '2026-08-05T05:54:45.428840+00:00'
oompah.task_costs:
  total_input_tokens: 47589
  total_output_tokens: 254
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47589
      output_tokens: 254
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 47589
    output_tokens: 254
    cost_usd: 0.0
    recorded_at: '2026-08-05T04:54:02.158626+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-819__20260805T045317Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-819
    source_sha: eb5d206f2fc040698808130b2629a997c3c9b953
    completed_at: '2026-08-05T04:54:02.205638+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e681539af605
    project_id: proj-14849f1b
    task_id: OOMPAH-819
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f2d495b25ea57c4b356449daadbf688cc45f1483bfe89025dcb7a4b83230357
    attempts:
    - version: 1
      attempt_id: attempt-287be3710e38
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2f2d495b25ea57c4b356449daadbf688cc45f1483bfe89025dcb7a4b83230357
      created_at: '2026-08-05T05:55:56.273694+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T05:55:56.273694+00:00'
      branch_key: epic-OOMPAH-768--task-OOMPAH-819
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-05T05:54:49.248670+00:00'
    updated_at: '2026-08-05T05:55:56.273694+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-287be3710e38
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f2d495b25ea57c4b356449daadbf688cc45f1483bfe89025dcb7a4b83230357
    created_at: '2026-08-05T05:55:56.273694+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T05:55:56.273694+00:00'
    branch_key: epic-OOMPAH-768--task-OOMPAH-819
---
## Summary

Live regression on 2026-08-05 while resubmitting OOMPAH-818: task branch advanced from the head merged by PR #716 to e3140b65f4958a4b7f89a1fc414bb53e88215dc4, task submit recorded the new exact integration head and moved Ready to Integrate, but standalone Ready reconciliation reused stale review_url/review_number #716, moved the task directly to In Validation, queued a Merged audit, and created no integration-queue row or exact-head quality gate. origin/main remained f1270e41 and did not contain e3140b65. This bypasses OOMPAH-697/698 protections because the task enters via Ready reconciliation rather than stale In Review reconciliation. Implementation scope: in standalone Ready/review reconciliation, bind every open/closed/merged review outcome to its exact forge review head and the current oompah.integration head generation; a merged or closed review for an older head is historical only, must be superseded/cleared without losing history, and the newer submitted head must remain/reenter the integration queue for an exact-head quality gate and fresh review. Fence tracker/review/queue mutations against concurrent resubmit, webhook, and review merge. In Validation/Merged transitions require proof that the reviewed exact submitted head landed on the target. Relevant code: Orchestrator standalone Ready reconciliation, _ensure_review_exists/_mark_task_in_review, review metadata and IntegrationQueueStore generation, TerminalTransitionCoordinator; preserve OOMPAH-697/698 legacy recovery. Required tests: exact OOMPAH-818 same-branch post-merge resubmit with stale PR metadata; merged old head plus new integration head; review payload missing head with Git containment fallback; concurrent resubmit during reconciliation; restart/webhook lag; current-head open/merged controls; assert no terminal audit, In Validation, or queue retirement before the new exact head gates and lands. Acceptance: a task branch advance after a merged review can never reuse that review to bypass the current submission generation, and OOMPAH-818 naturally flows through a new exact-head gate/review.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 03:08
---
Started implementation. The tracker claim is live, but the claimed /home/shedwards/.oompah/worktrees/oompah/OOMPAH-819 checkout and local OOMPAH-819 branch were absent from Git's worktree registry. I am resolving the recorded claim base and will recreate only that missing checkout before implementing the exact-head Ready reconciliation fence and race regressions.
---
author: oompah
created: 2026-08-05 03:11
---
Topology correction recorded: OOMPAH-819 remains the systemic epic-lineage task. No implementation edits were made in its recreated checkout. The same accepted fix is now being bootstrapped on standalone main-based OOMPAH-820; OOMPAH-819 depends on that deployment and will later record the patch on the epic lineage.
---
author: oompah
created: 2026-08-05 04:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 04:48
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 16s
---
author: oompah
created: 2026-08-05 04:52
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 04:52
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 04:54
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.6K in / 254 out [47.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 23s
- Log: OOMPAH-819__20260805T045317Z.jsonl
---
author: oompah
created: 2026-08-05 04:55
---
Cleared the automatic-retry blocker: the pre-existing /home/shedwards/.oompah/worktrees/oompah/OOMPAH-819 directory belonged to obsolete standalone branch OOMPAH-819 at already-merged commit f1270e41, while this task now authoritatively targets epic-OOMPAH-768--task-OOMPAH-819. The worktree was clean with no unique commits, so the redundant worktree and local branch were safely removed. The next server retry can create the correct nested worktree; implementation remains held until OOMPAH-820 finishes terminal audit/deployment.
---
author: oompah
created: 2026-08-05 05:34
---
Recorded the independently accepted OOMPAH-820 bootstrap patch on the systemic epic lineage as commits 742327deb and ce2526a8b (same two logical commits, cleanly applied onto current epic-OOMPAH-768). Verification on the lineage tree: 660 focused standalone-ready, terminal coordinator, native tracker, webhook, and submission-fencing tests passed; terminal mutation scan 8/8 allowlisted; secret scan and git diff check passed. Branch is clean and pushed at ce2526a8b7e67426c3919cf890a9b3b1cdca20ad.
---
author: oompah
created: 2026-08-05 05:34
---
Recorded the deployed exact-head review-generation fence on epic-OOMPAH-768; 660 focused regressions and required scans pass at ce2526a8b.
---
author: oompah
created: 2026-08-05 05:40
---
Removing the OOMPAH-820 finish dependency after fulfillment: OOMPAH-820 is terminal Merged on main, and this submitted lineage head contains the same two reviewed logical commits. Keeping the cross-epic dependency would intentionally require main to be reachable from epic-OOMPAH-768 before the very integration that records those commits, creating an artificial containment cycle.
---
author: oompah
created: 2026-08-05 05:55
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 05:56
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 05:56
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
