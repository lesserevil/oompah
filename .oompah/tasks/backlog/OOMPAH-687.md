---
id: OOMPAH-687
type: task
status: Backlog
priority: null
title: Isolate branch-gate runtime from task worktree environments
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T23:00:54.291962Z'
updated_at: '2026-08-01T23:00:54.291962Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Context\nWhile recovering OOMPAH-683/684 on 2026-08-01, a managed task worktree contained a thin .venv/bin/python wrapper that resolved to the service checkout's .venv. Running the task worktree's normal make test-setup caused uv to rewrite the service venv editable install from /home/shedwards/src/oompah to the OOMPAH-684 worktree. The branch-quality sandbox later mounted that service-owned venv as its trusted runtime, but the editable .pth target was outside the sandbox. Eight tests/test_installed_cli_smoke.py commands then failed on the otherwise-valid OOMPAH-683 head. Reinstalling the service checkout through make test-setup restored the editable path and all 13 current-install CLI smoke tests passed.\n\nImplementation scope\n- Make the quality-gate trusted Python/CLI runtime immutable to task worktrees and concurrent agent setup. A managed worktree must never cause uv/pip to rewrite the service venv's editable source mapping.\n- Audit task-worktree .venv creation/wrappers, Makefile setup discovery, provider environment inheritance, BranchQualityGate._sandbox_command runtime binds, and the current-install CLI smoke fixture.\n- Give workers either a real task-private test environment or a read-only trusted environment with setup targets safely disabled. Do not use a writable wrapper that makes uv select the operator/service venv.\n- Before every branch gate, validate that the mounted trusted runtime imports oompah from the deployed service checkout or from the exact immutable candidate mapping. Classify a mismatched editable mapping as executor/runtime corruption, repair or replace it safely, and do not report it as candidate CI failure.\n- Preserve gate isolation: candidate code must not gain write access to the service venv, operator checkout, credentials, or lifecycle state.\n- Add diagnostics that identify the expected and actual editable source roots without exposing secrets.\n\nRelevant code and tests\n- Makefile setup/test-setup targets and generated worktree runtime helpers.\n- oompah/quality_gate.py snapshot/runtime bind construction.\n- ProjectStore/workspace/provider setup that prepares task worktrees.\n- tests/test_quality_gate.py, tests/test_makefile_setup.py, tests/test_installed_cli_smoke.py, plus provider/worktree tests.\n\nAcceptance criteria\n- Running make test-setup from two task worktrees concurrently cannot change the service venv's editable source mapping.\n- A branch gate always executes its installed CLI against the exact candidate head using an immutable trusted runtime.\n- A deliberately poisoned service editable mapping is detected and recovered or reported as infrastructure failure, never as task CI failure.\n- The OOMPAH-683 eight-smoke-test reproduction passes deterministically under concurrent task gates.\n- Focused quality-gate/worktree/setup tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

