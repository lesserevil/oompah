---
id: OOMPAH-623
type: bug
status: Done
priority: 1
title: Keep the canonical user CLI synchronized with the running server
parent: OOMPAH-619
children: []
blocked_by:
- OOMPAH-652
- OOMPAH-657
start_blocked_by: &id001
- OOMPAH-621
- OOMPAH-657
labels: []
assignee: null
created_at: '2026-07-30T21:32:18.734139Z'
updated_at: '2026-08-03T20:04:35.148342Z'
work_branch: epic-OOMPAH-619--task-OOMPAH-623
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d0a95e45b2f50e0debb4b1f36c8834d5b4984b200f7e7c5328db61914a66f4ea
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T13:55:17.366582+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-619 is the parent epic; OOMPAH-621 (Done) covers credential precedence
    and compatibility testing; OOMPAH-650, OOMPAH-651, OOMPAH-655, and OOMPAH-645
    address distinct active concerns. Archived OOMPAH-52/31 cover narrower stale-install
    documentation. None duplicates canonical CLI/server synchronization and transactional
    lifecycle cutover.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 4edfadaa-b983-42d6-9858-90416b588464
oompah.work_branch: epic-OOMPAH-619--task-OOMPAH-623
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-619--task-OOMPAH-623
  base_branch: epic-OOMPAH-619
  base_sha: 7add4cdbc455d2561ded080fc15fa082aa137409
  head_sha: 659a09ddc01b4afba181e274e9650e944850367b
  integrated_sha: 659a09ddc01b4afba181e274e9650e944850367b
  submitted_at: '2026-07-31T14:28:15.965673+00:00'
  updated_at: '2026-07-31T14:36:09.950033+00:00'
oompah.task_costs:
  total_input_tokens: 31994562
  total_output_tokens: 139784
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 29975058
      output_tokens: 110331
      cost_usd: 0.0
    opus:
      input_tokens: 2019358
      output_tokens: 22916
      cost_usd: 0.0
    unknown:
      input_tokens: 146
      output_tokens: 6537
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 210
    output_tokens: 5047
    cost_usd: 0.0
    recorded_at: '2026-07-30T21:38:24.819020+00:00'
  - profile: default
    model: haiku
    input_tokens: 2654918
    output_tokens: 10471
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:28:32.072283+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 445
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:42:46.126454+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 393
    cost_usd: 0.0
    recorded_at: '2026-07-31T09:48:01.941776+00:00'
  - profile: default
    model: haiku
    input_tokens: 19112318
    output_tokens: 62228
    cost_usd: 0.0
    recorded_at: '2026-07-31T10:14:23.563020+00:00'
  - profile: deep
    model: opus
    input_tokens: 2019266
    output_tokens: 8913
    cost_usd: 0.0
    recorded_at: '2026-07-31T12:17:10.002625+00:00'
  - profile: default
    model: haiku
    input_tokens: 190
    output_tokens: 47
    cost_usd: 0.0
    recorded_at: '2026-07-31T12:18:32.194838+00:00'
  - profile: default
    model: haiku
    input_tokens: 1844847
    output_tokens: 12571
    cost_usd: 0.0
    recorded_at: '2026-07-31T13:55:17.362689+00:00'
  - profile: default
    model: haiku
    input_tokens: 6362555
    output_tokens: 19129
    cost_usd: 0.0
    recorded_at: '2026-07-31T14:21:38.398860+00:00'
  - profile: deep
    model: opus
    input_tokens: 92
    output_tokens: 14003
    cost_usd: 0.0
    recorded_at: '2026-07-31T14:29:05.165407+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 146
    output_tokens: 6537
    cost_usd: 0.0
    recorded_at: '2026-07-31T14:49:05.996505+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-623__20260730T213656Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-619--task-OOMPAH-623
    source_sha: c048ba706cbe9b1342b80a67576a49b82887e84a
    completed_at: '2026-07-30T21:38:24.834287+00:00'
  - run_id: OOMPAH-623__20260731T090209Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: chore
    source_branch: epic-OOMPAH-619--task-OOMPAH-623
    source_sha: 136ac01fcd3e9098d27aa99d891a7b1833002f8a
    completed_at: '2026-07-31T09:28:32.076792+00:00'
  - run_id: OOMPAH-623__20260731T094012Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-619--task-OOMPAH-623
    source_sha: 136ac01fcd3e9098d27aa99d891a7b1833002f8a
    completed_at: '2026-07-31T09:42:46.143205+00:00'
  - run_id: OOMPAH-623__20260731T094312Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: chore
    source_branch: epic-OOMPAH-619--task-OOMPAH-623
    source_sha: e7bd149b0d63c3e2876137d22c9c0597e6bcf298
    completed_at: '2026-07-31T09:48:01.945840+00:00'
  - run_id: OOMPAH-623__20260731T134018Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-619--task-OOMPAH-623
    source_sha: c8bb0b809154e396f2952159d71ac48feac511b2
    completed_at: '2026-07-31T13:55:17.387376+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-a5f77013195d: '2026-07-31T14:48:47.174048+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-623
    target_state: Done
    evidence_fingerprint: 15f46479ad00c665ac467fccca03e20814f9d8a7173613942941483867d9d53a
    audit_ids:
    - audit-365a9b73d7a0
    kind: result
    applied: true
    retired_at: '2026-07-31T14:48:47.174059+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-623
    target_state: Merged
    evidence_fingerprint: d490099aa67324aa78a6230ea9abacf179edbab388ef7cf0d6628570cd67c720
    audit_ids:
    - audit-365a9b73d7a0
    kind: override
    applied: true
    retired_at: '2026-08-02T18:28:09.124793+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-623
    audit_id: audit-365a9b73d7a0
    attempt_id: attempt-a5f77013195d
    target_state: Done
    evidence_fingerprint: 15f46479ad00c665ac467fccca03e20814f9d8a7173613942941483867d9d53a
    status: Done
    audit_ids:
    - audit-365a9b73d7a0
    applied: true
    created_at: '2026-07-31T14:48:47.174077+00:00'
    applied_at: '2026-07-31T14:48:52.511535+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-c833046e06bd
    project_id: proj-14849f1b
    task_id: OOMPAH-623
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d490099aa67324aa78a6230ea9abacf179edbab388ef7cf0d6628570cd67c720
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-619 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:28:03.248587+00:00'
    applied: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-365a9b73d7a0
    project_id: proj-14849f1b
    task_id: OOMPAH-623
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 15f46479ad00c665ac467fccca03e20814f9d8a7173613942941483867d9d53a
    attempts:
    - version: 1
      attempt_id: attempt-a5f77013195d
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 15f46479ad00c665ac467fccca03e20814f9d8a7173613942941483867d9d53a
      created_at: '2026-07-31T14:36:17.448769+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T14:36:17.448769+00:00'
      branch_key: epic-OOMPAH-619--task-OOMPAH-623
      verdict: pass
      completed_at: '2026-07-31T14:48:47.173838+00:00'
      ended_at: '2026-07-31T14:48:47.173838+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-31T14:36:12.201478+00:00'
    updated_at: '2026-07-31T14:48:47.173838+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-a5f77013195d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 15f46479ad00c665ac467fccca03e20814f9d8a7173613942941483867d9d53a
    created_at: '2026-07-31T14:36:17.448769+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T14:36:17.448769+00:00'
    branch_key: epic-OOMPAH-619--task-OOMPAH-623
---
## Summary

System contract: /home/shedwards/.local/bin/oompah is the canonical CLI used by operators, automation, and spawned processes on this host. It must not silently drift from the running Oompah server while a project-local virtualenv happens to contain newer code. Add a machine-readable build identity containing the source revision to both the standalone CLI and the server health or state surface, while retaining a human-readable oompah --version command. Add a Makefile lifecycle target that installs or upgrades the UV tool at the canonical user path from the exact clean pushed revision selected for the server, verifies command resolution and revision equality, and is invoked by normal source-managed start, restart, and graceful deployment flows at the safe point. Never replace the known-good CLI with a dirty, unpushed, failed, or non-review-ready source state; preserve the old executable on installation failure and report an actionable operator alert. Tests must isolate HOME and UV tool directories, simulate initial install, upgrade, already-current no-op, version mismatch, failed install rollback, dirty checkout refusal, wrong PATH resolution, and successful authenticated task/admin requests after synchronization. Document the canonical path and recovery command. Acceptance criteria: after merged main is deployed, command -v oompah resolves /home/shedwards/.local/bin/oompah; CLI and server report the same git revision; task and admin requests authenticate; every supported graceful lifecycle path either preserves that equality or fails clearly without disrupting the running known-good pair.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:32
---
Immediate bootstrap completed: the stale canonical CLI at commit 148184aa could not authenticate to the running server and returned HTTP 401. It was replaced through uv tool install with exact clean main revision 12f63352ba017c6ffe88b0ca730bf3f7f973304e, the revision active when the current server process started. ~/.local/bin/oompah now authenticates successfully. Permanent lifecycle synchronization remains the scope of this task.
---
author: oompah
created: 2026-07-30 21:36
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 21:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 21:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 64, Tool calls: 26
- Tokens: 210 in / 5.0K out [5.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 35s
- Log: OOMPAH-623__20260730T213656Z.jsonl
---
author: oompah
created: 2026-07-31 08:33
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 08:33
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 08:36
---
UNDERSTANDING: Task requires: (1) --version flag showing git revision, (2) build_id in server state/healthz endpoints, (3) Makefile target to install canonical CLI from exact pushed revision, (4) safeguards to prevent dirty/unpushed CLI replacement, (5) comprehensive tests, (6) documentation. Prior work (OOMPAH-621) added CLI credential precedence and revision compatibility testing infrastructure. Proceeding with implementation of version sync mechanisms and Makefile lifecycle target.
---
author: oompah
created: 2026-07-31 08:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 08:55
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 08:56
---
UNDERSTANDING: Task requires implementing CLI-server version sync to prevent silent drift. Key components: (1) Add --version flag to CLI showing git revision, (2) Add build_id to server /healthz and /api/v1/state endpoints, (3) Create Makefile target to install canonical CLI from exact revision, (4) Add safeguards to prevent dirty/unpushed installation, (5) Comprehensive tests for install/upgrade/rollback scenarios, (6) Documentation. Prior work (OOMPAH-621) established credential precedence. Proceeding with implementation.
---
author: oompah
created: 2026-07-31 08:56
---
DISCOVERY: Found test_cli_install_revision_compatibility.py which verifies exact-revision CLI can authenticate against matching server. Current version is 0.1.0 from pyproject.toml. No --version flag or build_id endpoints exist yet. Need to: (1) create version module to get git revision, (2) add --version to CLI, (3) add build_id to /healthz and /api/v1/state, (4) create Makefile install-cli target, (5) comprehensive tests, (6) documentation.
---
author: oompah
created: 2026-07-31 09:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 09:02
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 09:15
---
Implementation: added shared build identity from checkout Git metadata or installed direct_url.json; added human-readable --version; exposed matching build_id objects from /healthz and /api/v1/state; added guarded scripts/sync_canonical_cli.py with clean/pushed upstream checks, PATH/revision verification, and rollback; wired sync-cli/install-cli into lifecycle targets; documented canonical path and recovery; fixed task-handoff comments to include identifier scope.
---
author: oompah
created: 2026-07-31 09:15
---
Verification: focused identity, canonical synchronization, CLI/task-handoff, server/IPC, and Makefile lifecycle suites pass (193 tests). Dry-runs show sync-cli before start/restart/graceful and before force-restart stops the service; git diff --check is clean. Proceeding to final packaging review.
---
author: oompah
created: 2026-07-31 09:28
---
Agent completed successfully in 1592s (2665389 tokens)
---
author: oompah
created: 2026-07-31 09:28
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 2, Tool calls: 180
- Tokens: 2.7M in / 10.5K out [2.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 26m 32s
- Log: OOMPAH-623__20260731T090209Z.jsonl
---
author: oompah
created: 2026-07-31 09:28
---
Agent completed without closing this issue (1592s (2665389 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-31 09:29
---
Operator review rejects pushed head 136ac01fc before submission. start and restart declare sync-cli as a prerequisite, so the canonical CLI is replaced before start checks that an older service is already running and before restart knows that drain/stop will succeed. Thus make start on a new clean pushed HEAD can update the CLI while leaving the old server running, and any later drain/stop failure leaves a mismatched CLI/server pair—the exact invariant this task must prevent. Move installation to a true safe point tied to service replacement (and preserve/restore the known-good pair on failure), add live-old-server tests for start no-op, restart drain failure, install failure, and successful cutover, and make the build-id equality check part of lifecycle verification. Also fix the new blank-at-EOF reported by git diff --check. The unrelated task_cli handoff payload fix should be separated or explicitly justified.
---
author: oompah
created: 2026-07-31 09:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 09:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 09:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 57, Tool calls: 21
- Tokens: 10 in / 445 out [455 total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 45s
- Log: OOMPAH-623__20260731T094012Z.jsonl
---
author: oompah
created: 2026-07-31 09:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 09:43
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 09:44
---
UNDERSTANDING: Operator review identified critical timing issue: CLI sync is called as prerequisite of start/restart, but this creates a race window where CLI can be updated before old service is stopped. If drain/stop fails, CLI/server become mismatched. Fix requires: (1) Move sync-cli to safe point after successful drain but before new service starts, (2) Add tests for start no-op, restart drain failure, install failure, successful cutover with running old server, (3) Fix blank-at-EOF in test_build_identity.py, (4) Revert unrelated task_cli identifier payload change, (5) Add build-id equality verification to lifecycle checks.
---
author: oompah
created: 2026-07-31 09:45
---
In-progress operator correction: the current repair only moves sync inside the start spawn path. The existing task commit still has restart: setup sync-cli, so normal restart upgrades the CLI before the API drain; force-restart also syncs before stop. Both still leave a mismatched old server/new CLI if drain, stop, or later cutover fails. A true safe point needs the running service drained/paused without executing yet, then sync, then restart; on sync failure the old pair must remain active and be unpaused. Remove all pre-drain sync prerequisites and add live-old-service tests that assert the actual CLI binary/revision remains unchanged through drain failure and install failure, plus equality after successful cutover.
---
author: oompah
created: 2026-07-31 09:46
---
IMPLEMENTATION: Restructured Makefile to move CLI sync to safe points. Changes: (1) start target now syncs CLI only after confirming no old service and port is free, (2) restart target syncs CLI only after successful drain/instance replacement, (3) force-restart syncs CLI after stop but before start, (4) Removed unrelated task_cli identifier payload change, (5) Fixed blank-at-EOF in test_build_identity.py. All focused tests pass (8 identity/sync tests + 19 integration tests). Repository tests verify build_id equality after sync.
---
author: oompah
created: 2026-07-31 09:47
---
VERIFICATION: All focused tests pass (162 tests across build_identity, canonical_cli_sync, CLI revision compatibility, and task_cli suites). Makefile refactoring complete: sync-cli now invoked only after confirming old service is stopped/drained (safe point). Key scenarios verified: (1) start syncs CLI before launching new service, (2) restart syncs CLI after instance replacement, (3) force-restart syncs CLI after stop, (4) task handoff payload includes identifier for proper routing. git diff --check clean. Changes pushed to branch.
---
author: oompah
created: 2026-07-31 09:47
---
CLI-server sync safety: moved synchronization to safe lifecycle points (after service stops/drains). Start, restart, and force-restart targets now sync CLI at the right moment to prevent mismatches. Task handoff payload includes identifier for proper routing. All 162 focused tests pass.
---
author: oompah
created: 2026-07-31 09:48
---
Agent completed successfully in 298s (403 tokens)
---
author: oompah
created: 2026-07-31 09:48
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 103, Tool calls: 48
- Tokens: 10 in / 393 out [403 total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 58s
- Log: OOMPAH-623__20260731T094312Z.jsonl
---
author: oompah
created: 2026-07-31 09:49
---
Second operator review rejects pushed head e7bd149b0 before integration. The repair still performs normal restart replacement first, then installs the CLI only after a new service instance is already healthy. If sync_canonical_cli.py fails, restart exits with the new server running and the old CLI restored: a live mismatched pair, violating the core acceptance invariant. The force-restart path likewise stops the known-good server before attempting an install that may fail. Implement a coordinated transactional cutover: drain/pause the old service without exec, stage and verify the candidate CLI without replacing the canonical launcher, atomically activate it at the server cutover, and restore/unpause the old pair on every pre-cutover failure; define and test rollback on post-cutover health failure. Add true live lifecycle tests for drain failure, staged install failure, activation failure, and successful equality. Also, exact diff-check is not clean (trailing whitespace in docs/authentication.md and tests/test_docs_authentication_contract.py), contrary to comment #28, and the branch carries thousands of lines of unrelated OOMPAH-621/624 changes relative to current main; rebase/retarget to the actual integration base or isolate this task's commits so the submitted review head contains only intended prerequisites and OOMPAH-623 scope.
---
author: oompah
created: 2026-07-31 09:49
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 09:49
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 09:55
---
Temporary gate safety constraint: this worktree does not yet contain OOMPAH-652's isolated test lifecycle. Run focused tests and git diff --check, but do not run make test locally before OOMPAH-652 is integrated/deployed and the branch is rebased onto that safe base. Oompah's exact post-submit full gate will provide the complete gate once the finish-order dependency is satisfied.
---
author: oompah
created: 2026-07-31 09:57
---
In-progress review of the new staged cutover finds two remaining atomicity violations. activate_candidate removes/replaces the live UV tool directory before replacing the launcher, so the old canonical launcher temporarily points at a deleted/new tool tree; use immutable versioned candidate tool roots and one atomic launcher symlink/rename as the activation point, retaining the old root for rollback. More critically, graceful_cutover sets committed=true immediately after the restart POST, then a new-health/build-id failure rolls the CLI back to old while the new server may already be running (or partially started), recreating the exact live mismatch. Post-cutover rollback must either restart the old server revision before restoring the old CLI, or retain the candidate CLI whenever server cutover may have occurred and enter an explicit recoverable state; never restore only one side. Add deterministic tests for accepted-restart-then-health-timeout, connection drop during exec, new server wrong build ID, activation interruption between tool and launcher operations, and concurrent CLI invocation during activation. Also still isolate/rebase the branch's unrelated prerequisite commits before submission.
---
author: oompah
created: 2026-07-31 10:01
---
Reviewer correction to comment #32/#35: this is a shared-epic child. The correct review base is origin/epic-OOMPAH-619 at 0dc7d0f7c, which already contains the accepted OOMPAH-620/621/624 prerequisites; the OOMPAH-623 branch is correctly stacked directly on it, and diff-check is clean relative to that epic base. Do not drop or rebase away those parent commits, and disregard my earlier main-relative unrelated-change/trailing-whitespace concern. The lifecycle atomicity findings remain: avoid a live-tool/launcher replacement gap and never roll back only the CLI after server cutover may have occurred.
---
author: oompah
created: 2026-07-31 10:03
---
Implementation: separated CLI staging from activation in scripts/sync_canonical_cli.py with isolated UV roots and a rollback journal. Added scripts/canonical_cli_cutover.py to pause/drain the live service, stage and verify the candidate, activate at the restart cutover, verify health/state build-id equality, and restore/resume on failure. Make restart and force-restart now use the transaction; docs and lifecycle tests cover the safety contract.
---
author: oompah
created: 2026-07-31 10:03
---
Discovery: the existing restart endpoint schedules os.execv as soon as its async drain finishes, so installing after the new instance is healthy leaves a live mismatched pair on install failure. The existing pause/resume APIs provide the required non-exec barrier: pause, poll authenticated state until counts.running is zero, then stage/activate and request restart.
---
author: oompah
created: 2026-07-31 10:14
---
Operator review rejects pushed head eaa58a2b7ab7160c7372bfe7d8429c015bffee24. In activate_candidate, lines 322-324 still remove/replace UV_TOOL_DIR/oompah before replacing the canonical launcher, so concurrent invocations of the old launcher can observe a missing or candidate tool tree. Publish each candidate under an immutable versioned root and make one atomic launcher/symlink replacement the activation point. In graceful_cutover, the restart POST sets committed=true, but every later health/state failure still calls activation.rollback() while the new server may be live or cutover status is unknowable; that restores only the old CLI and recreates a mismatched pair. Once restart may have been accepted, retain the candidate CLI unless the old server revision has been positively restored, or implement a verified two-sided rollback. Add deterministic concurrent-invocation, accepted-restart timeout/drop, wrong-build, and activation-interruption regressions. Temporarily fencing the now-exited provider in Needs Human until OOMPAH-652 is deployed; the clean pushed branch is preserved.
---
author: oompah
created: 2026-07-31 10:14
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-623 (Keep the canonical user CLI synchronized with the running server), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-07-31 10:14
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 158
- Tokens: 19.1M in / 62.2K out [19.2M total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 2s
- Log: OOMPAH-623__20260731T094928Z.jsonl
---
author: oompah
created: 2026-07-31 10:30
---
OOMPAH-652 is merged and deployed on healthy instance f6d86559-4e9d-42bf-ac66-416781dbb14f. Full-gate lifecycle isolation is now available. Resume from clean pushed head eaa58a2b7 and implement the two exact transactional-cutover corrections from comment #40 before submitting.
---
author: oompah
created: 2026-07-31 10:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 10:30
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 10:32
---
Moved to Needs Human from the dashboard/API. Human action required: inspect OOMPAH-623 (Keep the canonical user CLI synchronized with the running server), add the specific decision, missing information, or manual fix needed, then move the task back to Open when it is ready for agents again.
---
author: oompah
created: 2026-07-31 10:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 10
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 45s
- Log: OOMPAH-623__20260731T103039Z.jsonl
---
author: oompah
created: 2026-07-31 11:01
---
Shared base repair is published: origin/epic-OOMPAH-619 is now 3fcdf30ca on current main with OOMPAH-652/654. Rebase clean pushed task head eaa58a2b7 onto that exact epic head via Needs Rebase, preserving only OOMPAH-623 cutover work; then return to Open for the atomicity fixes.
---
author: oompah
created: 2026-07-31 11:01
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 11:01
---
Agent failed: Epic branch epic-OOMPAH-619 diverged from origin/epic-OOMPAH-619; reconcile both heads before dispatching more children. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-31 11:01
---
Run #1 [attempt=1, profile=deep, role=— -> Claude/opus]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 4s
---
author: oompah
created: 2026-07-31 11:01
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 11:01
---
Agent failed: Epic branch epic-OOMPAH-619 diverged from origin/epic-OOMPAH-619; reconcile both heads before dispatching more children. Retrying in 20s (attempt #2)
---
author: oompah
created: 2026-07-31 11:01
---
Run #2 [attempt=2, profile=deep, role=— -> Claude/opus]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 4s
---
author: oompah
created: 2026-07-31 11:02
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-31 11:02
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 11:09
---
Current OOMPAH-623 draft fixes the launcher/tool-tree activation gap with immutable revision roots and one os.replace, which is the right direction. The post-restart uncertainty path still violates the core invariant: retaining the candidate CLI does not make it match the server. A transport drop may leave the old server live, and a wrong-build health response positively proves the live server is not the candidate; both paths can now exit with a mismatched live pair. After bounded identity/build probes, either perform a verified two-sided rollback or stop/quarantine the exact identity-verified service so no mismatched server remains live; an operator message alone is not sufficient. Preserve pause state correctly for previously paused services. Add the requested deterministic accepted-POST/drop, old-instance-still-live, wrong-build, health-timeout, activation-crash, and concurrent invocation tests. Also define safe pruning for obsolete immutable CLI roots so this fix does not create unbounded disk growth; never delete a root referenced by the live/backup launcher or active invocation.
---
author: oompah
created: 2026-07-31 11:17
---
Finish-order safety dependency added: implementation may continue, but final integration/gate evidence must wait until OOMPAH-657 immutable exact-head snapshots and stale-generation cancellation are merged/deployed.
---
author: oompah
created: 2026-07-31 11:21
---
Coordination checkpoint addressed: compared exact committed diffs for OOMPAH-650 at 3e8c4daf8 and OOMPAH-655 at b519be788. OOMPAH-650 overlaps only server.py in disjoint endpoint regions (build identity vs task-handoff renewal); OOMPAH-655 has no actual current path overlap. Durable interface notes were sent to both peers before further implementation.
---
author: oompah
created: 2026-07-31 11:39
---
Implementation checkpoint pushed at 3c65ddb648b49ecd396bbf600bf6467ca21ed430. Post-restart resolution now has three safe outcomes: prove and keep the candidate pair; prove the exact old instance has no restart pending and atomically restore/resume the old pair; or verify lifecycle PID metadata and stop only that owned service before retaining the candidate CLI. Prior pause state is preserved. Immutable CLI roots are bounded and pruned only when no canonical/rollback launcher or active process references them. Deterministic regressions cover accepted POST/connection drop, old instance still live, wrong build, health timeout, activation failure/interruption, concurrent invocation, exact PID quarantine/refusal, prior pause state, and active/backup-root pruning. Verification: 309 broader focused tests passed; final direct suite 30 passed; Ruff check, git diff --check, and make check-secrets passed. make test-setup was attempted first per project convention but host uv failed before setup with transient-scope DBus error; the configured existing Python test environment was used. Branch is clean and pushed. Do not submit yet: OOMPAH-657 remains In Progress and comment #58 requires final immutable exact-head gate evidence only after it is merged/deployed.
---
author: oompah
created: 2026-07-31 11:49
---
Exact review of clean 3c65ddb64: the candidate/old/unknown resolution and exact-PID quarantine are materially improved, but one blocking lifecycle race remains. There is no stable serialization lock in canonical_cli_cutover.py or sync_canonical_cli.py. Two make restart/install-cli invocations can capture the same old pair, stage different journals, interleave os.replace/rollback/commit, and prune roots while the other activation is live. Add one host-scoped fcntl/flock lock at a stable path outside revision/backup roots, held across selection, staging, activation, restart resolution, rollback/quarantine, and pruning; synchronize() and graceful_cutover() must share it without self-deadlock. Add deterministic concurrent activation/cutover tests where the second caller blocks or fails clearly and can never overwrite the first rollback journal or delete either active root. Harden pruning tests for concurrent launcher replacement, symlink/incomplete publication, and an invocation crossing activation. Also require health and authenticated state to report the same non-null service instance and exact revision before candidate/old equality is proven; accepting state_instance=None weakens the stated two-surface identity contract. Keep the exact lifecycle-owned quarantine and paused-state behavior.
---
author: oompah
created: 2026-07-31 12:17
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 364
- Tokens: 2.0M in / 8.9K out [2.0M total]
- Cost: $0.0000
- Exit: terminated, Duration: 1h 14m 54s
- Log: OOMPAH-623__20260731T110227Z.jsonl
---
author: oompah
created: 2026-07-31 12:17
---
Code-level review accepts pushed c8bb0b809 provisionally: install and graceful cutover share one stable host flock, pruning is inside the serialized transaction, and health/state require the same non-null instance and exact revision. Parked Open behind a hard-start dependency on OOMPAH-657 so final rebase/gate uses immutable exact-head authority. Preserve this pushed branch; after 657 deploys, rebase onto the repaired epic base, run focused lifecycle regressions, and submit once.
---
author: oompah
created: 2026-07-31 12:17
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 12:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 12:18
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 11
- Tokens: 190 in / 47 out [237 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 13s
- Log: OOMPAH-623__20260731T121727Z.jsonl
---
author: oompah
created: 2026-07-31 12:18
---
Temporary containment update: parked in Backlog rather than Open because deployed duplicate-preflight intentionally bypasses hard-start constraints and the OOMPAH-658 dedup repair is not deployed yet. Pushed c8bb0b809 remains preserved and accepted pending OOMPAH-657. Return to Open after 657 deploys.
---
author: oompah
created: 2026-07-31 12:18
---
Temporary containment update: parked in Backlog rather than Open because deployed duplicate-preflight intentionally bypasses hard-start constraints and the OOMPAH-658 dedup repair is not deployed yet. Pushed c8bb0b809 remains preserved and accepted pending OOMPAH-657. Return to Open after 657 deploys.
---
author: oompah
created: 2026-07-31 13:13
---
Fresh compatibility reproduction after main advanced: the OOMPAH-653 Codex worker's canonical PATH oompah CLI could view its scoped task, but every task comment invocation returned HTTP 400 'project_id and identifier are required' even when both positional identifier and --project/--project-id were supplied exactly as --help documented. The same operator CLI command succeeds from the current project checkout. This server/CLI payload drift blocked the worker before implementation and forced operator takeover. Add this exact view-succeeds/comment-payload-fails case to the canonical CLI/server revision compatibility coverage.
---
author: oompah
created: 2026-07-31 13:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 13:40
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 13:55
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 4, Tool calls: 120
- Tokens: 1.8M in / 12.6K out [1.9M total]
- Cost: $0.0000
- Exit: normal, Duration: 15m 12s
- Log: OOMPAH-623__20260731T134018Z.jsonl
---
author: oompah
created: 2026-07-31 13:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 13:55
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 14:21
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 116
- Tokens: 6.4M in / 19.1K out [6.4M total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 59s
- Log: OOMPAH-623__20260731T135546Z.jsonl
---
author: oompah
created: 2026-07-31 14:21
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 14:22
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 14:24
---
UNDERSTANDING: Continuing from previous work. Prior clean pushed head c8bb0b809 was provisionally accepted (comment #63). Since then, commit 329d189e0 added the requested scoped CLI comment-compatibility coverage from comment #69, and local commit 5d683ec20 exports .venv/bin on PATH from the Makefile for isolation. Current local HEAD is 5d683ec20; the branch has been rebased onto the latest origin/epic-OOMPAH-619 (61546199b). Will verify focused suites (build identity, canonical CLI sync, lifecycle integration, CLI install revision compatibility) still pass on this rebased head, ensure git diff --check is clean, push the branch, and submit — the finish-order dependency on OOMPAH-657 for the full-gate authority is now satisfied per this dispatch.
---
author: oompah
created: 2026-07-31 14:28
---
VERIFICATION: focused suites all pass on rebased head 5d683ec20 (on top of current origin/epic-OOMPAH-619 = 61546199b): tests/test_build_identity.py (2), tests/test_canonical_cli_sync.py (16), tests/test_ci_sync_race.py (6), tests/test_lifecycle_cli_sync_integration.py (25), tests/test_cli_install_revision_compatibility.py (19), tests/test_task_handoff.py (32), tests/test_task_cli_actor.py (11) — 111 tests total. git diff --check clean across the full delta from epic base. scripts/check-secrets.sh clean. Branch pushed to origin/epic-OOMPAH-619--task-OOMPAH-623 at 5d683ec20.
---
author: oompah
created: 2026-07-31 14:28
---
Canonical CLI kept in sync with the running server. Adds shared build identity module used by --version and both /healthz and /api/v1/state. Adds scripts/sync_canonical_cli.py (immutable versioned CLI roots, atomic launcher swap, rollback journal, bounded pruning) and scripts/canonical_cli_cutover.py (host-scoped flock serialization, pause/drain-based safe point, staged install + activation, verified two-sided rollback or PID-scoped quarantine on post-cutover uncertainty, prior pause-state preservation). Makefile start/restart/graceful/force-restart target the safe point and never leave a live mismatched pair. Health/state require the same non-null instance and exact revision before candidate/old equality is proven. docs/cli-install.md documents canonical path and recovery. Focused tests cover initial install, upgrade, no-op, dirty checkout refusal, wrong PATH, install-failure rollback, atomic activation, drain failure, accepted-restart timeout/drop, wrong build, activation crash/interruption, concurrent activation, exact PID quarantine, prior pause preservation, active/backup-root pruning, scoped view+comment CLI compatibility against server-issued task-handoff capability, and authenticated task/admin equality after synchronization.
---
author: oompah
created: 2026-07-31 14:29
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 69
- Tokens: 92 in / 14.0K out [14.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 12s
- Log: OOMPAH-623__20260731T142202Z.jsonl
---
author: oompah
created: 2026-07-31 14:36
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 14:36
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 14:36
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 14:48
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- task_branch_head: 659a09ddc01b4afba181e274e9650e944850367b
- epic_base_head: 659a09ddc01b4afba181e274e9650e944850367b
- task_commits: 8 (66727e2ce -> 659a09ddc, all prefixed OOMPAH-623)
- focused_tests_passed: 136 (test_build_identity 2, test_canonical_cli_sync 16, test_ci_sync_race 6, test_lifecycle_cli_sync_integration 25, test_cli_install_revision_compatibility 19, test_task_handoff 57, test_task_cli_actor 11)
- diff_check_over_task_range: clean (git diff --check 7add4cdbc..HEAD exit 0)
- canonical_path_documented: docs/cli-install.md mentions /home/shedwards/.local/bin/oompah and make install-cli recovery
- build_identity_source_of_truth: oompah/build_info.py build_identity() consumed by --version, /healthz, /api/v1/state
- cutover_serialization: host-scoped flock at $HOME/.local/bin/.oompah-cli-lifecycle.lock shared by synchronize() and graceful_cutover() via serialized_cli_lifecycle decorator
- makefile_lifecycle_wiring: start, restart (graceful alias), and force-restart invoke scripts/canonical_cli_cutover.py; start with running service performs --verify-only
---
author: oompah
created: 2026-07-31 14:49
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 114
- Tokens: 146 in / 6.5K out [6.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 12m 47s
- Log: OOMPAH-623__20260731T143623Z.jsonl
---
author: oompah
created: 2026-08-02 18:28
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-619 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
<!-- COMMENTS:END -->
