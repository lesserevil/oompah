---
id: OOMPAH-1003
type: bug
status: Done
priority: 1
title: Revalidate root epic auto-close from durable landing authority without a mutable
  issue head
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T19:11:49.831627Z'
updated_at: '2026-08-11T02:03:53.758069Z'
work_branch: OOMPAH-1003
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/802
review_number: '802'
review_head: 7186cce68e1ad569bd2e0f2dec225787902100bd
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: o940-root-epic-auto-close-null-head
  request_fingerprint: 6e42d1ebee1399c57ba567812850dfa474f446e9fa9271a6cee34474222ffa31
oompah.target_branch: main
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  post_landed_parent_id: OOMPAH-940
  task_branch: OOMPAH-1003
  base_branch: main
  base_sha: 8eac2ae5097e84840d6b07fe965b37224c0f7960
  head_sha: 7186cce68e1ad569bd2e0f2dec225787902100bd
  submitted_at: '2026-08-10T19:49:22.598132+00:00'
  updated_at: '2026-08-10T19:49:22.598132+00:00'
oompah.work_branch: OOMPAH-1003
oompah.review_url: https://github.com/lesserevil/oompah/pull/802
oompah.review_number: '802'
oompah.review_head: 7186cce68e1ad569bd2e0f2dec225787902100bd
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-f69884c1e483
    project_id: proj-14849f1b
    task_id: OOMPAH-1003
    digest: 780e5db61a3579be824065d17d777e80957e88b3d96a56ab896654b90016db2b
  - version: 1
    audit_id: audit-885f9bb5906b
    project_id: proj-14849f1b
    task_id: OOMPAH-1003
    digest: 780e5db61a3579be824065d17d777e80957e88b3d96a56ab896654b90016db2b
  oompah.terminal_override_records:
  - version: 1
    override_id: override-aa968107ae7e
    project_id: proj-14849f1b
    task_id: OOMPAH-1003
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 780e5db61a3579be824065d17d777e80957e88b3d96a56ab896654b90016db2b
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Implementation is delivered in protected PR #803 at merge a9e6cf0047af5d2e37a53853cf49467b2cf16f22
      with exact local and hosted gates green. Done is the topology-valid child terminal
      lane while parent epic OOMPAH-940 remains the live natural auto-close canary.'
    created_at: '2026-08-10T21:03:06.800777+00:00'
    selected_ref: 7186cce68e1ad569bd2e0f2dec225787902100bd
    selected_sha: 7186cce68e1ad569bd2e0f2dec225787902100bd
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1003
    target_state: Done
    evidence_fingerprint: 780e5db61a3579be824065d17d777e80957e88b3d96a56ab896654b90016db2b
    audit_ids:
    - audit-f69884c1e483
    - audit-885f9bb5906b
    kind: override
    applied: true
    retired_at: '2026-08-10T21:03:17.539253+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: 'Implementation is delivered by protected PR #803 and its topology-valid
      Done state is intentionally retained while parent epic OOMPAH-940 owns final
      rollup. This removes a self-superseding child Merged recovery that is starving
      the current parent auto-close job; OOMPAH-1005 regression follow-up is being
      filed.'
    marked_at: '2026-08-11T02:03:52.090415+00:00'
    updated_at: '2026-08-11T02:03:52.090415+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: 'Implementation is delivered by protected PR #803 and its topology-valid
        Done state is intentionally retained while parent epic OOMPAH-940 owns final
        rollup. This removes a self-superseding child Merged recovery that is starving
        the current parent auto-close job; OOMPAH-1005 regression follow-up is being
        filed.'
      recorded_at: '2026-08-11T02:03:52.090415+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f69884c1e483
    project_id: proj-14849f1b
    task_id: OOMPAH-1003
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 780e5db61a3579be824065d17d777e80957e88b3d96a56ab896654b90016db2b
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-10T20:59:25.076621+00:00'
    selected_ref: 7186cce68e1ad569bd2e0f2dec225787902100bd
    selected_sha: 7186cce68e1ad569bd2e0f2dec225787902100bd
    updated_at: '2026-08-10T21:03:17.539201+00:00'
  - version: 1
    audit_id: audit-885f9bb5906b
    project_id: proj-14849f1b
    task_id: OOMPAH-1003
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 780e5db61a3579be824065d17d777e80957e88b3d96a56ab896654b90016db2b
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-10T20:59:25.076621+00:00'
    selected_ref: 7186cce68e1ad569bd2e0f2dec225787902100bd
    selected_sha: 7186cce68e1ad569bd2e0f2dec225787902100bd
    updated_at: '2026-08-10T21:03:17.539230+00:00'
  attempt_history: []
---
## Summary

Triggered by the live OOMPAH-940 rollout at workflow generations 1564-1571. Problem: universal workflow decisions correctly accept the durable root-epic landing fact epic-OOMPAH-940 -> main at 2dd74be288b81265ea4a242d7467ecc1ed9f1435 and enqueue epic_auto_close, but EpicWorkflow._is_action_current(AUTO_CLOSE) requires that landed revision to equal issue_exact_head(snapshot.epic). OOMPAH-940 has intentionally null work_branch, target_branch, review_head, and exact mutable head after landing, so every auto-close job is claimed then superseded as 'workflow evidence changed after job enqueue'; the action can never succeed. Scope: make epic auto-close worker revalidation consume the same canonical durable landing authority and target identity as universal decision construction, while fencing task/project/evidence-generation changes and preserving fail-closed behavior for ambiguous or stale facts. Do not reintroduce mutable-head authority and do not direct-edit task or workflow data. Relevant code: EpicWorkflow AUTO_CLOSE decision/current-action validation and workflow job authority snapshots; compare the composed/null-head parent_rollup_review fix in OOMPAH-975. Required tests: reproduce a root epic with null issue_exact_head plus an exact current durable landing fact, prove auto-close remains current and reaches terminal flow, and prove mismatched revision/target/generation or changed task authority is rejected. Acceptance: OOMPAH-940 naturally leaves In Progress after deployment, no epic_auto_close supersession loop remains, a complete published scan has zero current divergence/exhaustion/action_required, and make workflow-rollout-check passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 19:49
---
Implementation is complete and pushed at exact head 7186cce68e1ad569bd2e0f2dec225787902100bd. The auto-close path now binds one durable containment-scoped immediate-target landing through revalidation/apply/verify/transition, preserves ordinary mutable-head CAS, permits fallback only for headless root epics still In Progress under ORCHESTRATOR authority, and rechecks the immutable SHA in TaskTransitionService, terminal coordinator, and final runtime guard. Validation: 557 combined focused tests, terminal mutation scan 20/20, diff/secret checks, and independent adversarial review are green.
---
author: oompah
created: 2026-08-10 19:49
---
Fix headless root-epic auto-close using immutable durable landing authority
---
author: oompah
created: 2026-08-10 20:19
---
Branch quality gate passed for `7186cce68e1ad569bd2e0f2dec225787902100bd` using `make test` in 176.4s. Review creation may proceed.
---
author: oompah
created: 2026-08-10 20:49
---
Exact combined recovery head 1d35b2e922b59077dc4b0d758e7e0c823affe027 passed the complete make test gate: 19,650 passed, 7 skipped, 2 xfailed in 21m07s. Protected delivery PR #803 is open for hosted Python 3.11/3.12/3.13 checks.
---
author: oompah
created: 2026-08-10 20:59
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-10 21:03
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Implementation is delivered in protected PR #803 at merge a9e6cf0047af5d2e37a53853cf49467b2cf16f22 with exact local and hosted gates green. Done is the topology-valid child terminal lane while parent epic OOMPAH-940 remains the live natural auto-close canary.
---
author: oompah
created: 2026-08-10 21:03
---
Delivered root-epic auto-close recovery through protected PR #803; terminalized as Done pending natural parent rollup.
---
<!-- COMMENTS:END -->
