---
id: OOMPAH-980
type: bug
status: Done
priority: 1
title: Reuse authoritative full branch gates in terminal audits
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T01:42:03.823626Z'
updated_at: '2026-08-10T02:37:34.850015Z'
work_branch: OOMPAH-980
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  mode: queue
  task_branch: OOMPAH-980
  base_branch: epic-OOMPAH-940
  base_sha: 2dd74be288b81265ea4a242d7467ecc1ed9f1435
  head_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
  submitted_at: '2026-08-10T02:22:46.589167+00:00'
  last_error: automatic rebase could not prove that the rewritten head preserves every
    accepted submission change; rebase the private branch explicitly and submit the
    resulting exact head
oompah.work_branch: OOMPAH-980
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-cd3df7f6baa7
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
  - version: 1
    audit_id: audit-aca2a9199109
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
  oompah.terminal_override_records:
  - version: 1
    override_id: override-f1ccfa22e053
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner completion override: exact head 10f586bbcdd87287f486906840e4a5405de4bddd
      passed the complete local gate with 19,279 tests and protected Python 3.11,
      3.12, and 3.13 CI, independent review approved, and PR 789 landed main at 2dde7ad8734542a056e45e1fb5d52fff8204b9fb.
      The automatic audit was cancelled to avoid rerunning the same twenty-minute
      full gate while the post-landed epic routing workaround is active.'
    created_at: '2026-08-10T02:37:09.928178+00:00'
    selected_ref: 10f586bbcdd87287f486906840e4a5405de4bddd
    selected_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-980
    target_state: Done
    evidence_fingerprint: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
    audit_ids:
    - audit-cd3df7f6baa7
    - audit-aca2a9199109
    kind: override
    applied: true
    retired_at: '2026-08-10T02:37:19.848449+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-cd3df7f6baa7
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
    attempts:
    - version: 1
      attempt_id: attempt-a15f133bdfd2
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
      created_at: '2026-08-10T02:35:56.041902+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-10T02:35:56.041902+00:00'
      branch_key: OOMPAH-980
      selected_ref: 10f586bbcdd87287f486906840e4a5405de4bddd
      selected_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Needs Rebase
    created_at: '2026-08-10T02:33:48.003361+00:00'
    selected_ref: 10f586bbcdd87287f486906840e4a5405de4bddd
    selected_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
    updated_at: '2026-08-10T02:37:19.848403+00:00'
  - version: 1
    audit_id: audit-aca2a9199109
    project_id: proj-14849f1b
    task_id: OOMPAH-980
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Needs Rebase
    created_at: '2026-08-10T02:33:48.003361+00:00'
    selected_ref: 10f586bbcdd87287f486906840e4a5405de4bddd
    selected_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
    updated_at: '2026-08-10T02:37:19.848433+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-a15f133bdfd2
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3e8483858cb6678a11d1ad45db692f279d49ed26910557e96c6f56631b4c52a4
    created_at: '2026-08-10T02:35:56.041902+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-10T02:35:56.041902+00:00'
    branch_key: OOMPAH-980
    selected_ref: 10f586bbcdd87287f486906840e4a5405de4bddd
    selected_sha: 10f586bbcdd87287f486906840e4a5405de4bddd
oompah.task_costs:
  total_input_tokens: 64
  total_output_tokens: 7
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 64
      output_tokens: 7
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 64
    output_tokens: 7
    cost_usd: 0.0
    recorded_at: '2026-08-10T02:37:23.009546+00:00'
---
## Summary

Triggered by OOMPAH-979. Its exact branch head 7fc8bc8ea4a36c952a96349406a173c6b85ec94e had an authoritative full make test result recorded before review, but terminal audit authority treated the gate as incomplete and launched another full test run. Under the outer auditor validation environment, that redundant run also classified two ordinary native test lifecycles as opaque instead of full. Scope: reproduce the OOMPAH-979 branch-gate-to-terminal-audit path end to end; identify and fix the exact-head authority propagation or compatibility gap so a current compatible full gate is reused before any auditor process launch; add a native guard regression proving ordinary make test lifecycle telemetry stays full beneath an outer auditor guard without weakening hostile or leading-assignment fail-closed classification. Relevant context includes orchestrator exact-gate authority and audit launch policy, api_agent gate enforcement, validation_resource_lease, native validation guard and ACP lifecycle plumbing. Required tests: focused unit and integration regressions for compatible gate reuse, stale or incompatible rejection, no redundant auditor launch, nested native scope classification, and preserved opaque fail-closed cases. Acceptance: an OOMPAH-979-shaped exact-head full gate is reused rather than rerun; nested ordinary lifecycle scope remains full; no broad environment sanitization is introduced; focused tests and the complete project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 01:42
---
Claimed for direct-owner completion. Reproducing the exact OOMPAH-979 gate-authority and nested native lifecycle path on current main before changing production code.
---
author: oompah
created: 2026-08-10 01:54
---
Reproduction complete. OOMPAH-979 had durable exact-head make test evidence and review_head 7fc8bc8e, but terminal audit identity ignored review_head and therefore never queried the gate store. Separately, the Make-launched service leaked MAKEFLAGS and MFLAGS into auditor environments, making the fail-closed classifier report ordinary make test as opaque. The fix now uses canonical exact-head resolution for audit evidence and strips only inherited Make control variables at the agent boundary; the classifier remains fail closed for command-supplied controls. Focused verification: 290 affected gate, auth, API lifecycle, and native Codex tests passed.
---
author: oompah
created: 2026-08-10 02:22
---
Implementation complete at exact pushed head 10f586bbcdd87287f486906840e4a5405de4bddd. Independent review approved with no blockers. Verification: 310 affected tests passed; complete make test passed with 19,279 passed, 7 skipped, 2 expected failures, zero failures in 1246.99 seconds; terminal mutation scan, diff check, commit hooks, and secret scan passed.
---
author: oompah
created: 2026-08-10 02:23
---
Canonical review heads now reuse durable exact gate evidence, and inherited Make control channels are removed at the agent boundary while explicit hostile controls remain fail closed.
---
author: oompah
created: 2026-08-10 02:33
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-10 02:36
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-10 02:36
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-10 02:37
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Project-owner completion override: exact head 10f586bbcdd87287f486906840e4a5405de4bddd passed the complete local gate with 19,279 tests and protected Python 3.11, 3.12, and 3.13 CI, independent review approved, and PR 789 landed main at 2dde7ad8734542a056e45e1fb5d52fff8204b9fb. The automatic audit was cancelled to avoid rerunning the same twenty-minute full gate while the post-landed epic routing workaround is active.
---
author: oompah
created: 2026-08-10 02:37
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 3
- Tokens: 64 in / 7 out [71 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 23s
- Log: OOMPAH-980__20260810T023609Z.jsonl
---
author: oompah
created: 2026-08-10 02:37
---
Owner-verified exact gate and protected CI evidence applied after direct-main landing; implementation is complete.
---
<!-- COMMENTS:END -->
