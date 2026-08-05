---
id: OOMPAH-841
type: task
status: In Progress
priority: null
title: Keep native validation guards off provider bootstrap processes
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-05T18:44:50.597184Z'
updated_at: '2026-08-05T18:46:20.207594Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction on 2026-08-05: OOMPAH-829 acquired the sole validation slot at provider startup. The durable owner row has requester_pid=child_pid=the Codex node provider root, while pstree shows no make/pytest/validation subprocess and the agent has resumed file edits. OOMPAH-830, OOMPAH-831, and OOMPAH-523 then wait behind a lease whose deadline spans the whole agent turn. Root cause: install_native_validation_guard prepends shims for node before the Codex CLI is launched; the Codex npm shebang resolves node through the shim, and generic node classification can treat the provider bootstrap itself as heavyweight validation.\n\nImplementation scope: ensure launching the native Codex provider/SDK process can never acquire validation capacity. Preserve command-scoped leasing for genuine project node/npm/make/pytest invocations. If a trusted bootstrap bypass is used, bind it to the exact operator-installed executable/entrypoint and invocation shape recorded in the read-only guard config so a task-controlled lookalike cannot bypass validation. The durable owner must attach to the actual outer heavyweight command process, release when that command exits, and never use the long-lived provider root as child_pid. Add truthful health/recovery evidence for a provider-root lease created by an older process and an authority-safe task-scoped recovery path that preserves dirty work before retry. Coordinate with OOMPAH-810 result delivery and validation_resource_lease fencing; do not weaken crash-safe inherited-fd ownership.\n\nRelevant files: oompah/native_validation_guard.py, oompah/acp_backends/codex.py, oompah/validation_resource_lease.py, tests/test_native_validation_guard.py, tests/test_acp_codex_backend.py, and state/health regressions.\n\nRequired tests: starting a Codex subscription session through the npm node shebang leaves owner_count=0; a genuine node test command acquires/releases exactly one slot; concurrent make/pytest commands remain serialized; task-controlled fake codex paths/argv cannot obtain the bypass; actual validation survives service/provider crash via inherited fd; stale legacy provider-root ownership is detected and recovered without killing unrelated processes; waiters advance immediately after command exit.\n\nAcceptance criteria: validation capacity is held only for an actual heavyweight command lifetime, never an entire native provider session; exact process identity and crash fencing remain intact; no legitimate worker/auditor waits behind an idle editing agent.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

