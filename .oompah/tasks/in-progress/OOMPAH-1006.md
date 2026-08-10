---
id: OOMPAH-1006
type: task
status: In Progress
priority: null
title: Normalize native project scope at epic mutation revalidation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T21:29:22.606379Z'
updated_at: '2026-08-10T22:57:46.432742Z'
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
  creation_marker: 623bf5a4-7de8-4bd2-9ea3-8eb97160db76
  request_fingerprint: edb0abe4fbe3045cc119e008b887fe52bf238967b68b705f99f7386480db9791
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-edc69b9442f7
    project_id: proj-14849f1b
    task_id: OOMPAH-1006
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b30f95df9c402e407d3266d0aa11a5bfa0f7f8694163b17ee2c535ede9850527
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected PR #804 merged exact reviewed and fully gated implementation
      into main at 74e68a020357615c81cf7c7b5cff808763dc34d3; direct owner is terminalizing
      the claimed repair after hosted Python 3.11/3.12/3.13 success.'
    created_at: '2026-08-10T22:57:44.709550+00:00'
    selected_ref: origin/OOMPAH-1006
    selected_sha: 074c0330902cc3356519d6adb2a4725613c652e9
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-940 and OOMPAH-1003

Problem: live generation 1726 produced a current headless root-epic auto-close job with exact durable landing 2dd74be288b81265ea4a242d7467ecc1ed9f1435. ProductionEpicWorkflowBackend._fresh_snapshot normalizes a native Markdown Issue whose project_id is absent to the bound project, so worker revalidation succeeded and persisted the exact landing checkpoint. OrchestratorEpicWorkflowEffects._fresh_epic_authority then fetched the same unchanged native issue but compared its raw project_id=None directly with self.project_id, raising WorkflowActionSuperseded("epic project, parent, status, or delivery authority changed") at effect_pending. No tracker field changed; OOMPAH-940 updated_at remained 2026-08-10T19:11:50Z.

Scope: normalize native project identity consistently at every epic fresh-authority boundary before computing/comparing issue_authority_version, without accepting a conflicting non-empty project identity. Keep mismatched projects fail closed and preserve parent/status/delivery CAS. Audit adjacent effect/verification/transition refreshes for the same asymmetry. Relevant files: oompah/epic_workflow_adapter.py, oompah/epic_workflow.py, native Markdown tracker tests.

Required tests: use a native-tracker-shaped fresh Issue with project_id=None and a bound snapshot Issue; prove unchanged auto-close apply/verify proceeds with the checkpointed durable landing; prove a conflicting non-empty project id, changed parent/status/branch/integration/evidence, or missing issue supersedes/fails closed; include an end-to-end headless root epic regression using the real Markdown tracker rather than mocks that prefill project_id.

Acceptance: OOMPAH-940 naturally leaves In Progress after deployment with no effect_pending supersession, exact landing authority remains unchanged through terminal transition, and focused plus complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 21:29
---
Accepted for direct-owner repair after live generation 1726 reproduced native project-scope self-supersession.
---
author: oompah
created: 2026-08-10 21:40
---
Implementation in progress on branch OOMPAH-1006. The fix normalizes only blank native Markdown project identities to the bound workflow project using immutable Issue replacement, while conflicting non-empty identities remain fail-closed. It covers backend and fresh effect authority plus child cleanup, with a real on-disk OompahMarkdownTracker headless-root auto-close regression and mutation-authority negatives under independent review.
---
author: oompah
created: 2026-08-10 21:44
---
Implementation is committed and pushed at exact head 074c0330902cc3356519d6adb2a4725613c652e9. Focused validation: 152 epic workflow/adapter tests passed; 120 transition/audit-contract tests passed with 2 expected xfails; terminal mutation scan passed 20/20; diff, gitleaks, attribution, and worktree sync checks are green. Independent final exact-head review is in progress before combined protected delivery.
---
author: oompah
created: 2026-08-10 22:11
---
Exact combined recovery head 1e9032b4bdd870acf6822962fb45dcc8c5e73d3a passed focused validation (457 passed, 2 expected xfails), terminal mutation scan 20/20, secret/diff checks, and the complete make test gate: 19,679 passed, 7 skipped, 2 expected xfails in 21m06s. Protected delivery PR #804 is open and running hosted Python 3.11/3.12/3.13 checks.
---
author: oompah
created: 2026-08-10 22:46
---
Hosted PR #804 exposed one test-only xdist incompatibility: production emitted and captured the expected stale-owner failure on Python 3.11/3.12/3.13, but the new test inspected caplog records after asyncio.run. The assertion now directly observes the logger call and preserves the production invariants. It passed repeated xdist runs and isolated Python 3.11/3.12/3.13 checks. Updated exact head 5fc2432263ad3593ef891dc716b43332083ed455 passed the full make test gate: 19,679 passed, 7 skipped, 2 expected xfails in 21m09s, and is pushed to rerun hosted CI.
---
<!-- COMMENTS:END -->
