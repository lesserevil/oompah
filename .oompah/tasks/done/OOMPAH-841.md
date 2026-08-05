---
id: OOMPAH-841
type: task
status: Done
priority: null
title: Keep native validation guards off provider bootstrap processes
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T18:44:50.597184Z'
updated_at: '2026-08-05T21:41:02.019225Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: integrated
  attempts: 2
  task_branch: OOMPAH-841
  base_branch: epic-OOMPAH-763
  base_sha: bb42de1e71f355a8f0eb2c4c0ddd958715b646e6
  head_sha: 58ffd477b19f370c7ed53a191e1a05580b016c85
  integrated_sha: 58ffd477b19f370c7ed53a191e1a05580b016c85
  submitted_at: '2026-08-05T20:42:54.818726+00:00'
  updated_at: '2026-08-05T21:17:45.607388+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-ef651c224859: '2026-08-05T21:40:49.646308+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-841
    target_state: Done
    evidence_fingerprint: 805911c9b49a6e8b9d4fb47a2e87368a9cd865f7b5fc8ea0580247d8fd4047f2
    audit_ids:
    - audit-57b9189aa8e6
    kind: result
    applied: true
    retired_at: '2026-08-05T21:40:49.646320+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-841
    audit_id: audit-57b9189aa8e6
    attempt_id: attempt-ef651c224859
    target_state: Done
    evidence_fingerprint: 805911c9b49a6e8b9d4fb47a2e87368a9cd865f7b5fc8ea0580247d8fd4047f2
    status: Done
    audit_ids:
    - audit-57b9189aa8e6
    applied: true
    created_at: '2026-08-05T21:40:49.646338+00:00'
    applied_at: '2026-08-05T21:40:59.264763+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-57b9189aa8e6
    project_id: proj-14849f1b
    task_id: OOMPAH-841
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 805911c9b49a6e8b9d4fb47a2e87368a9cd865f7b5fc8ea0580247d8fd4047f2
    attempts:
    - version: 1
      attempt_id: attempt-ef651c224859
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 805911c9b49a6e8b9d4fb47a2e87368a9cd865f7b5fc8ea0580247d8fd4047f2
      created_at: '2026-08-05T21:18:20.629995+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T21:18:20.629995+00:00'
      branch_key: OOMPAH-841
      verdict: pass
      completed_at: '2026-08-05T21:40:49.646093+00:00'
      ended_at: '2026-08-05T21:40:49.646093+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-05T21:17:48.052797+00:00'
    updated_at: '2026-08-05T21:40:49.646093+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ef651c224859
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 805911c9b49a6e8b9d4fb47a2e87368a9cd865f7b5fc8ea0580247d8fd4047f2
    created_at: '2026-08-05T21:18:20.629995+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T21:18:20.629995+00:00'
    branch_key: OOMPAH-841
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
author: oompah
created: 2026-08-05 19:44
---
Focused post-repair gate passed: make test-setup terminal-audit-scan succeeded and 242/242 targeted tests passed across native guard, validation-resource leasing, Codex backend, authenticated owner-claim recovery, and aggregate health. The end-to-end recovery test launched two independent durable worker generations, retired only the exact health-advertised legacy provider process, preserved the unrelated generation, and granted direct ownership. Validation lane returned idle. Branch remains uncommitted pending one fresh independent final review.
---
author: oompah
created: 2026-08-05 20:15
---
Security/race review repairs are implemented and focused verification is green. Native guard runtime/config/shims now live under an operator-only ~/.oompah/native-validation-guards root outside workspace, git, /tmp, and effective temp roots; both direct and Node Codex executables are rejected if task-writable. Legacy-provider health requires the startup-captured exact Codex and Node path/device/inode plus direct service-or-init parent identity, so inherited SDK markers and task-owned lookalikes cannot trigger recovery. Owner recovery now requires all four advertised process fields and atomically compares the sole exact generation/process row before writing a cancellation tombstone, preventing same-generation ABA cancellation. Gate result: terminal mutation scan passed; 248/249 focused tests passed in the combined run, with the sole failure an incorrect new assertion about pre-session error events; after correcting only that assertion, its isolated rerun passed (effective 249/249). Static compile and diff checks pass. Awaiting fresh independent final review; no commit or push yet.
---
author: oompah
created: 2026-08-05 20:22
---
Clean final focused rerun after the durable-owner retirement and live-session PID fences: make test-setup + terminal-audit-scan passed, then 251/251 targeted tests passed in 27.59s across native guard, validation-resource leasing, Codex backend, authenticated owner-claim recovery, and aggregate health. Static compile/diff checks remain clean. Fresh independent review is in progress; branch remains uncommitted/unpushed.
---
author: oompah
created: 2026-08-05 20:29
---
Final consolidated focused gate is clean after all review-driven changes: terminal mutation scan passed and 252/252 targeted tests passed in 27.88s. This includes API-level same-generation ABA replacement, descendant-held durable-owner retirement, live-session provider PID, operator-path/inode/parent identity, and task-writable temp/workspace rejection. Static compile/diff checks remain clean; independent final review remains the only pre-commit step.
---
author: oompah
created: 2026-08-05 20:40
---
Final post-repair verification passed on reviewed head 58ffd477b: terminal mutation scan passed, 254/254 focused tests passed in 27.91s, py_compile and git diff --check passed, and make check-secrets passed. Independent final review returned READY. The clean branch is pushed and up to date.
---
author: oompah
created: 2026-08-05 20:41
---
Prevented native provider bootstrap processes from acquiring validation capacity, pinned trusted executable identities, and added exact safe recovery for legacy provider-root leases; 254 focused tests and all static/security checks passed.
---
author: oompah
created: 2026-08-05 20:42
---
Integration could not verify `OOMPAH-841`: task worktree head bb42de1e71f355a8f0eb2c4c0ddd958715b646e6 differs from the published task head 58ffd477b19f370c7ed53a191e1a05580b016c85; refusing to reset a preserved recovery snapshot

Fetch the private branch, preserve its commits, push a clean current head, and submit it again.
---
author: oompah
created: 2026-08-05 20:43
---
Canonical direct-claim worktree reconciled to the already reviewed and published head 58ffd477b; retry integration.
---
author: oompah
created: 2026-08-05 21:17
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 21:18
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 21:18
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 21:40
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 58ffd477b19f370c7ed53a191e1a05580b016c85
- remote_head: 58ffd477b19f370c7ed53a191e1a05580b016c85
- working_tree: clean
- [REDACTED-credential-key]: passed
- commit_stat: 10 files changed, 2048 insertions(+), 36 deletions(-)
- files_touched: oompah/acp_backends/codex.py, oompah/native_validation_guard.py, oompah/orchestrator.py, oompah/server.py, oompah/validation_resource_lease.py, tests/test_acp_codex_backend.py, tests/test_native_validation_guard.py, tests/test_owner_claim.py, tests/test_terminal_audit_health_api.py, tests/test_validation_resource_lease.py
- guard_bootstrap_tests: trusted_provider_node_bootstrap, retains_guard_for_heavy_descendant, ignores_task_path_node_lookalike, executables_cannot_be_task_writable, install_rejects_entrypoint_inode_replacement, task_controlled_shape_cannot_bypass (4-way)
- codex_backend_tests: managed_native_cli_fences_exact_provider_bootstrap, reads_only_prefix_of_large_direct_binary, rejects_task_writable_direct_codex
- lease_recovery_tests: owner_claim_retires_exact_advertised_legacy_provider_only, stale_validation_generation_cannot_cancel_current_runtime, same_generation_aba_replacement_fails_closed, exact_owner_cancellation_rejects_same_generation_aba_replacement, legacy_provider_root_detection_is_specific (5-way), legacy_provider_root_validation_owner_degrades_aggregate_health
---
<!-- COMMENTS:END -->
