---
id: OOMPAH-1094
type: task
status: Merged
priority: null
title: Reject task-worktree attempts to reuse the live service virtualenv
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T16:34:25.712698Z'
updated_at: '2026-08-11T18:12:25.613601Z'
work_branch: OOMPAH-1094
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 2085cefb-e493-48ea-a2dc-b6da41839427
  request_fingerprint: 1fceb852ea92bacae86c813af1227771694691f593bab362552d2db026ff7610
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1094
  head_sha: a8e0c10db484680bc584d272a9903d229bd9576f
  submitted_at: '2026-08-11T17:28:46.561202+00:00'
  updated_at: '2026-08-11T17:28:46.561202+00:00'
oompah.work_branch: OOMPAH-1094
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-5e5eb5ce8ed4
    project_id: proj-14849f1b
    task_id: OOMPAH-1094
    digest: b4d488eccd7e511bfb4f2b0e87a29921436881f652f34db27e642edab61408bc
  - version: 1
    audit_id: audit-4934ddf3f119
    project_id: proj-14849f1b
    task_id: OOMPAH-1094
    digest: b4d488eccd7e511bfb4f2b0e87a29921436881f652f34db27e642edab61408bc
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6e38f75b327c
    project_id: proj-14849f1b
    task_id: OOMPAH-1094
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b4d488eccd7e511bfb4f2b0e87a29921436881f652f34db27e642edab61408bc
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Operator-directed manual completion while all Oompah schedulers are paused:
      independent exact-head audit ACCEPT at a8e0c10db484680bc584d272a9903d229bd9576f;
      focused security/concurrency tests and terminal-audit scan passed; protected
      GitHub CI succeeded on Python 3.11, 3.12, and 3.13; PR #832 merged as b7ad6d1c2ebd2dc2c5200459161866f4bcc23f46;
      exact head is contained in origin/main.'
    created_at: '2026-08-11T18:12:13.761440+00:00'
    selected_ref: a8e0c10db484680bc584d272a9903d229bd9576f
    selected_sha: a8e0c10db484680bc584d272a9903d229bd9576f
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1094
    target_state: Merged
    evidence_fingerprint: b4d488eccd7e511bfb4f2b0e87a29921436881f652f34db27e642edab61408bc
    workflow_revision: null
    selected_ref: a8e0c10db484680bc584d272a9903d229bd9576f
    selected_sha: a8e0c10db484680bc584d272a9903d229bd9576f
    landing_revision: null
    audit_ids:
    - audit-5e5eb5ce8ed4
    - audit-4934ddf3f119
    kind: override
    applied: true
    retired_at: '2026-08-11T18:12:23.985568+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-5e5eb5ce8ed4
    project_id: proj-14849f1b
    task_id: OOMPAH-1094
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b4d488eccd7e511bfb4f2b0e87a29921436881f652f34db27e642edab61408bc
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-11T18:11:59.912879+00:00'
    eligible_at: '2026-08-11T18:11:59.912879+00:00'
    selected_ref: a8e0c10db484680bc584d272a9903d229bd9576f
    selected_sha: a8e0c10db484680bc584d272a9903d229bd9576f
    updated_at: '2026-08-11T18:12:23.985516+00:00'
  - version: 1
    audit_id: audit-4934ddf3f119
    project_id: proj-14849f1b
    task_id: OOMPAH-1094
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b4d488eccd7e511bfb4f2b0e87a29921436881f652f34db27e642edab61408bc
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-11T18:11:59.912879+00:00'
    prerequisite_audit_id: audit-5e5eb5ce8ed4
    selected_ref: a8e0c10db484680bc584d272a9903d229bd9576f
    selected_sha: a8e0c10db484680bc584d272a9903d229bd9576f
    updated_at: '2026-08-11T18:12:23.985547+00:00'
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-1085 and OOMPAH-1092. Live reproduction on 2026-08-11: an agent in /home/shedwards/src/oompah-1092 ran a required Makefile validation target with OOMPAH_TASK_VENV=/home/shedwards/src/oompah/.venv. Make setup rewrote the service-owned editable install to the task worktree. The next canonical OOMPAH-1085 branch gate correctly failed closed twice with trusted runtime corruption before the operator stopped the worktree gate and repaired main with make setup. OOMPAH-687 intended to prevent task worktrees from changing the service venv, and OOMPAH-972 repairs stale mappings, but an explicit or inherited OOMPAH_TASK_VENV still bypasses isolation. Implementation scope: at Makefile/test-setup and environment construction boundaries, resolve the invoking checkout, service checkout, requested task venv, editable source, device/inode/symlink aliases, and reject any non-service checkout that targets the live service venv before uv/pip mutation; provision or point to a task-private venv instead; keep canonical main make setup repair behavior; prevent concurrent worktrees from racing the trusted mapping; and make branch-gate preflight classify this as infrastructure without consuming candidate retry authority when automatic safe repair is available. Relevant files: Makefile setup/test/terminal-audit targets, scripts/run-tests.sh or setup helpers, task environment construction, quality_gate.py trusted runtime preflight, and tests/test_makefile_setup.py/tests/test_quality_gate.py. Required tests: direct absolute service-venv override from a task worktree, symlink/relative aliases, inherited override, two concurrent worktrees, canonical main repair, immutable candidate gate, and task-private success; prove service editable mapping remains main and no candidate gate attempt/alert is burned. Acceptance: no task-worktree Make target can rewrite the live service virtualenv, worktrees get isolated validation environments, OOMPAH-1085 exact-head gate can retry automatically after repair, focused setup/gate tests and full make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 17:03
---
Implementation pushed at exact head 1b36938b7a9d64534049af27963cba92b605a38d on branch OOMPAH-1094. Added a standard-library Make/setup mutation guard that resolves the invoking and primary service checkouts, compares resolved path plus device/inode aliases, carries exact service checkout/venv markers into worker environments, rejects task attempts to target the live service venv before uv, and serializes linked-worktree setup/repair with a shared Git flock. Canonical main setup remains repair authority; quality-gate preflight shares the lock and safely repairs proven canonical editable corruption before candidate execution. Verification: tests/test_makefile_setup.py + tests/test_client_auth.py 111 passed; tests/test_quality_gate.py 314 passed; terminal mutation scan 21/21. The live service direct_url mapping remained file:///home/shedwards/src/oompah before and after guarded task Make execution; task runtime remained file:///home/shedwards/src/oompah-1094. A redundant full make test reached 28% of 20,070 tests with no failures, then was operator-cancelled because four workers were blocked on jbd2 fsync and starving the critical release gate; all worker processes were confirmed gone. Per instruction, task is not submitted or merged and awaits independent review/canonical gate.
---
author: oompah
created: 2026-08-11 17:23
---
Second rejection repair pushed at exact head a8e0c10db484680bc584d272a9903d229bd9576f. The setup guard now treats the explicit service runtime, the explicit service checkout's conventional .venv, and any Git-derived primary .venv as additive protected targets, so a falsified cross-repository OOMPAH_SERVICE_VENV cannot erase the service checkout runtime boundary. Added a real unrelated-repository Make regression proving uv is not invoked and the service editable mapping remains unchanged. A different explicit service checkout cannot be rejected solely because it differs from the task repo's Git primary: that difference is required for legitimate cross-repo workers, so additive independent targets are the safest available proof. Verification: 115 focused setup/client-auth/quality-gate tests passed; terminal mutation scan passed 21/21; diff check clean. Branch is clean and pushed; exact head matches origin.
---
author: oompah
created: 2026-08-11 17:28
---
Fresh independent exact-head review ACCEPTED a8e0c10db484680bc584d272a9903d229bd9576f. Reviewer inspected all three commits and reproduced both prior bypasses through real Make paths: forged linked-worktree markers and correct cross-repo checkout plus forged service-venv both fail before uv and preserve the service editable mapping; legitimate task-private runtime still works. Evidence: 7 exact repair/shape tests, 121 broader focused tests, 30 repeated security/concurrency executions, compile/diff checks, terminal scan 21/21; remote exact and worktree clean.
---
author: oompah
created: 2026-08-11 17:28
---
Protect the live service virtualenv from linked-worktree and cross-repository task setup, including forged marker combinations; independently accepted at a8e0c10db484680bc584d272a9903d229bd9576f.
---
author: oompah
created: 2026-08-11 18:12
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 18:12
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Operator-directed manual completion while all Oompah schedulers are paused: independent exact-head audit ACCEPT at a8e0c10db484680bc584d272a9903d229bd9576f; focused security/concurrency tests and terminal-audit scan passed; protected GitHub CI succeeded on Python 3.11, 3.12, and 3.13; PR #832 merged as b7ad6d1c2ebd2dc2c5200459161866f4bcc23f46; exact head is contained in origin/main.
---
<!-- COMMENTS:END -->
