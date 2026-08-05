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
labels: []
assignee: null
created_at: '2026-08-05T18:44:50.597184Z'
updated_at: '2026-08-05T19:41:35.521747Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:53
---
Implementation in progress on the OOMPAH-763 root: native guard config now records an exact operator-installed Codex entrypoint plus service parent PID/start-ticks and inode/device. Only that direct node <entrypoint> exec bootstrap bypasses leasing, while the guarded PATH/SHELL remain active for real provider commands; lookalike paths and the same entrypoint from a task-controlled parent still queue normally. Added native process and backend-wiring regressions. Static compile and diff checks pass; focused tests are intentionally waiting for the currently occupied shared validation lane.
---
author: oompah
created: 2026-08-05 19:21
---
Independent review found and blocked two unsafe identities before testing: the first draft authenticated the Codex script but PATH-selected Node, and it did not pin the SDK launch to the authenticated Codex path. The repair now records exact operator Codex and Node path/device/inode identities, rejects any executable under task-writable workspace/git roots, bypasses PATH by execing the recorded Node identity, and passes the same exact Codex path through codex_path_override. Added lookalike Node, same-path replacement, wrong-parent/start-tick, descendant-guard, and backend identity-wiring regressions. Validation health now specifically identifies a legacy Codex provider-root owner and advertises the existing authenticated direct-owner recovery action that retires only that task generation while preserving its worktree. Static compile/diff checks pass; runtime tests remain queued behind the active shared lane.
---
author: oompah
created: 2026-08-05 19:23
---
Focused verification passed after the review repairs: 221/221 tests across native validation guard, validation-resource lease, and Codex backend. This includes exact Node/Codex identity pinning, task-writable and PATH lookalike rejection, entrypoint inode replacement, parent PID/start-tick fencing, provider descendant command leasing, legacy provider-root health classification, and recovery metadata. Static compile and diff checks remain clean. Awaiting a fresh independent post-repair review before commit.
---
author: oompah
created: 2026-08-05 19:41
---
Repaired the two independent-review blockers. Legacy worker bootstrap health now publishes a concrete POST owner-claim request containing the exact project/task/authority generation plus process identity; the existing authenticated owner-claim route revalidates that exact flagged durable lease, rejects auditor/cross-task/stale generation recovery, cancels only that generation, preserves the worktree, and verifies retirement before granting direct ownership. Codex executable detection now reads only a bounded 128-byte prefix. Added regression coverage including an end-to-end two-generation process test proving the flagged orphan is retired, the unrelated generation survives, and direct ownership is granted. Static compile and diff checks pass; focused runtime tests remain pending until the currently busy shared validation lane becomes idle.
---
<!-- COMMENTS:END -->
