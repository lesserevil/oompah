---
id: OOMPAH-954
type: bug
status: In Validation
priority: 1
title: Compose canonical epic facts in universal workflow decisions
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:29:27.319915Z'
updated_at: '2026-08-09T12:51:35.522753Z'
work_branch: OOMPAH-954
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-954
  base_branch: epic-OOMPAH-940
  base_sha: 41a158291ad932b232e9ebc4dcff5b0357d9f57b
  head_sha: dccbeb5ac4e1012d772ebfa366e586bdb6df76db
  submitted_at: '2026-08-09T11:51:17.689634+00:00'
  updated_at: '2026-08-09T11:51:17.689634+00:00'
oompah.work_branch: OOMPAH-954
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-f0bc7481f2ea
    project_id: proj-14849f1b
    task_id: OOMPAH-954
    digest: 6a65e99a38416f8a8fb971ec139006b80a90d105284f6e4b9d8967597b8c62f7
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f0bc7481f2ea
    project_id: proj-14849f1b
    task_id: OOMPAH-954
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a65e99a38416f8a8fb971ec139006b80a90d105284f6e4b9d8967597b8c62f7
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:51:29.097174+00:00'
    selected_ref: dccbeb5ac4e1012d772ebfa366e586bdb6df76db
    selected_sha: dccbeb5ac4e1012d772ebfa366e586bdb6df76db
  attempt_history: []
---
## Summary

Triggered by PR #757 hosted CI run 31310033950 and OOMPAH-945. All Python 3.11-3.13 jobs deterministically fail the OOMPAH-748 production-stack incident because work_decision now correctly requires canonical epic containment (epic_branch and target_branch) while Orchestrator._collect_universal_workflow_facts still composes the generic WorkflowFactCollector containment projection (parent_id and children only). This also makes universal liveness/UI publish evidence.containment_malformed for valid landed Done epics while the dedicated epic lane reaches terminal.immediate_target_landing_proven. Scope: based on the exact OOMPAH-940 aggregate head and targeting epic-OOMPAH-940, route epic tasks in universal fact collection through the canonical EpicFactCollector using the project repo/default branch and the same production sources as scheduler/shadow composition; update the OOMPAH-748 production-stack replay to exercise that production epic collector path. Do not restore mutable task-field fallback or weaken fail-closed containment validation. Required tests: exact failing OOMPAH-748 replay; universal/UI and epic scheduler agree on terminal.immediate_target_landing_proven; malformed and wrong-target containment remain fail-closed; full incident module, universal decision/cache and epic workflow suites; aggregate protected branch gate. Acceptance: PR #757 passes its full Python matrix, universal/scheduler/UI decisions share one canonical reason, and no incomplete generic containment is used for epic universal decisions.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 11:40
---
Implemented and pushed 9062f64273cdc0e14bac39b9d0c68f683707adae from exact epic-OOMPAH-940 head 41a158291. Universal controller and shadow fact collection now share canonical EpicFactCollector selection for epic issues, using project default branch/repo and the existing production sources. OOMPAH-748 now exercises the production universal path and asserts canonical containment plus reason agreement with UI projection and EpicWorkflowController. Checks: exact OOMPAH-748 replay passed; 160 incident/cache/epic/decision tests passed; 121 dashboard/controller/runtime/shadow tests passed; explicit malformed/wrong-target fail-closed checks passed; secret scan passed. No service restart performed.
---
author: oompah
created: 2026-08-09 11:40
---
Canonical epic facts now drive universal controller, shadow, UI, and epic scheduling decisions; OOMPAH-748 production replay and focused fail-closed suites pass at pushed head 9062f6427.
---
author: oompah
created: 2026-08-09 11:51
---
Independent review found and the branch now fixes a second production path at dccbeb5acbd3b17ee71ec2950e6583e824b2fdf3: WorkflowRuntime enforce-mode liveness now reuses epic_batch facts with the other owning-domain fact cuts. The new OOMPAH-748 runtime regression first proves the generic collector yields containment_malformed and an exhausted generic epic_terminal_validation row, then runs reconcile_async and proves the epic owner, runtime projection, and published decision all remain terminal.immediate_target_landing_proven while the stale exhausted row remains immutable. Focused runtime/incident/epic/decision/cache suite: 227 passed. No restart.
---
author: oompah
created: 2026-08-09 11:51
---
Review blocker fixed at dccbeb5ac: enforce runtime liveness reuses canonical epic facts, and OOMPAH-748 cannot be falsely overridden by stale generic retry exhaustion; 227 focused tests pass.
---
author: oompah
created: 2026-08-09 12:51
---
Worked around OOMPAH-958 durable integration lease deadlock: both accepted commits are patch-equivalent in origin/epic-OOMPAH-940 at 1ab5776d8. Reconciled to Done from authoritative target evidence.
---
author: oompah
created: 2026-08-09 12:51
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
