---
id: OOMPAH-1094
type: task
status: In Progress
priority: null
title: Reject task-worktree attempts to reuse the live service virtualenv
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T16:34:25.712698Z'
updated_at: '2026-08-11T17:28:31.396256Z'
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
  creation_marker: 2085cefb-e493-48ea-a2dc-b6da41839427
  request_fingerprint: 1fceb852ea92bacae86c813af1227771694691f593bab362552d2db026ff7610
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
<!-- COMMENTS:END -->
