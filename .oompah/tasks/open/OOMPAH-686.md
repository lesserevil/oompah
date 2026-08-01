---
id: OOMPAH-686
type: task
status: Open
priority: null
title: Keep worker container-runtime failures out of Needs Human
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T22:19:41.486806Z'
updated_at: '2026-08-01T22:20:15.600279Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Context\nEXOCOMP-145 reached Needs Human after an implementation worker and its retry could not execute the mandatory Makefile gates. All three failed before the pinned builder started with "Failed to obtain podman configuration: set sticky bit on: chmod /run/user/1000/libpod: read-only file system". The same clean pushed head passed make test, make fmt-check, and make lint immediately from the operator environment, proving the code and configured builder were healthy and the escalation was caused by the spawned worker runtime boundary.\n\nImplementation scope\n- Trace worker environment construction in oompah/api_agent.py, oompah/agent.py, oompah/client_auth.py, the ACP backends, and the quality-gate execution path.\n- Give spawned workers a writable, private rootless-container runtime location when their sandbox makes the inherited XDG_RUNTIME_DIR or /run/user/<uid>/libpod read-only, or route mandatory Makefile gates through a trusted host-side gate executor with equivalent repository and credential scope.\n- Add a bounded preflight that distinguishes task/code failures from container-runtime transport failures. Retry or use the configured safe executor for infrastructure-only failures; do not send a task to Needs Human while an available configured executor can run the gate.\n- Preserve isolation: do not chmod or replace the host's shared /run/user directory, do not expose credentials, and clean private runtime artifacts after the worker exits.\n- Record actionable diagnostics identifying the attempted executor and fallback without leaking environment secrets.\n\nRelevant tests\n- Unit tests for environment construction with an inherited read-only/unusable XDG_RUNTIME_DIR.\n- An orchestration regression test reproducing the EXOCOMP-145 failure and proving a healthy fallback completes make-gate execution without transitioning the task to Needs Human.\n- Cleanup and credential-redaction tests for any private runtime directory.\n- Focused provider/backend tests plus the configured Makefile gate.\n\nAcceptance criteria\n- A worker whose provider sandbox cannot write the inherited libpod runtime can still run the project's pinned container-backed Makefile gates through a safe configured path.\n- Infrastructure-only container runtime failures are classified separately from code/CI failures and do not require operator intervention when a healthy executor is available.\n- EXOCOMP-145's exact read-only-libpod scenario is covered by a regression test.\n- No shared runtime directory permissions are mutated and no secrets appear in logs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

