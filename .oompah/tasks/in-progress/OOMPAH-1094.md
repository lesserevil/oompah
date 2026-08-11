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
updated_at: '2026-08-11T16:35:09.355637Z'
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

