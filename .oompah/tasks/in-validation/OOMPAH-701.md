---
id: OOMPAH-701
type: bug
status: In Validation
priority: 1
title: Retire hidden provider processes when task ownership is revoked
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T20:20:26.676545Z'
updated_at: '2026-08-02T23:38:32.127268Z'
work_branch: OOMPAH-701
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/665
review_number: '665'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 601e266c07016cf60e471433d3ea1f76693a2e97d1a05d44d8da537e676a3f84
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Duplicate-screening worker exited with reason normal.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 2
  retry_after: '2026-08-02T21:56:04.107049+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 20
  total_output_tokens: 3189
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 20
      output_tokens: 3189
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1514
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:51:56.244095+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1675
    cost_usd: 0.0
    recorded_at: '2026-08-02T21:54:04.104962+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-701__20260802T215133Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-701
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T21:51:56.256868+00:00'
  - run_id: OOMPAH-701__20260802T215336Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-701
    source_sha: 366129d0a5046c5ed7caed4acf26cd8cd2a3fbdd
    completed_at: '2026-08-02T21:54:04.122274+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-701
  head_sha: 455cde3b1a393b869240dc32404a17022d77cc8c
  submitted_at: '2026-08-02T22:48:04.313149+00:00'
  updated_at: '2026-08-02T22:48:04.313149+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/665
oompah.review_number: '665'
oompah.work_branch: OOMPAH-701
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c05a51f9c48e
    project_id: proj-14849f1b
    task_id: OOMPAH-701
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3ffccdccadddc3e7c3185cc51cd8dbdce2c47023b32f832158721ad41edf4385
    attempts:
    - version: 1
      attempt_id: attempt-d2dd8c20dae6
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 3ffccdccadddc3e7c3185cc51cd8dbdce2c47023b32f832158721ad41edf4385
      created_at: '2026-08-02T23:38:26.852336+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T23:38:26.852336+00:00'
      branch_key: OOMPAH-701
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T23:37:08.506986+00:00'
    updated_at: '2026-08-02T23:38:26.852336+00:00'
  - version: 1
    audit_id: audit-c521d3856622
    project_id: proj-14849f1b
    task_id: OOMPAH-701
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3ffccdccadddc3e7c3185cc51cd8dbdce2c47023b32f832158721ad41edf4385
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-02T23:37:08.506986+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d2dd8c20dae6
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3ffccdccadddc3e7c3185cc51cd8dbdce2c47023b32f832158721ad41edf4385
    created_at: '2026-08-02T23:38:26.852336+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T23:38:26.852336+00:00'
    branch_key: OOMPAH-701
---
## Summary

Triggered by: OOMPAH-698

Production reproduction on 2026-08-02: after OOMPAH-700 was moved out of automatic dispatch and claimed for direct owner work, the public agent list became empty but its Claude provider process remained a child of the server with the OOMPAH-700 prompt. At the same time OOMPAH-698 remained In Validation with terminal-audit metrics reporting queued=1 and running=0 while a live auditor provider process repeatedly triggered auditor_shell_mutation authority denials. These hidden processes survived after scheduler ownership disappeared and left lifecycle state and observability contradictory.\n\nImplementation scope:\n- Keep an authoritative run/session record until every provider subprocess actually exits; never remove a run from agents or audit running metrics merely because task state or scheduler ownership changed.\n- When a task is reopened, reassigned, directly claimed, superseded, or otherwise loses the run generation, cancel and await the exact provider process group with bounded escalation and persisted recovery evidence.\n- Bound repeated read-only auditor policy denials; fail the attempt and enter the normal independent retry path instead of allowing an invisible model loop.\n- Reconcile orphaned provider children during startup and graceful restart without killing unrelated current-generation runs.\n- Make UI agent state, terminal-audit queued/running counters, claimed issue ownership, and actual OS process liveness converge atomically.\n\nRelevant code: oompah/orchestrator.py run ownership and worker exit paths; oompah/terminal_audit.py dispatch and retry bookkeeping; oompah/agent.py and provider adapters process lifecycle; service-state and dashboard agent/audit metrics.\n\nRequired tests:\n- Transition an implementation task away from an active run and prove its provider process exits before the agent record is retired.\n- Reproduce an auditor repeatedly requesting a disallowed mutation and prove the attempt terminates, records a bounded failure, and retries through a different eligible candidate.\n- Simulate the state-change versus provider-exit race and prove no hidden child or stale claim remains.\n- Restart with an orphaned provider child and prove deterministic cleanup plus persisted audit recovery.\n- Assert agent UI state and terminal-audit running metrics remain truthful throughout cancellation and exit.\n\nAcceptance criteria:\n- No provider process survives without a visible current-generation run record.\n- OOMPAH-698 style audits cannot remain In Validation with queued/running metrics that contradict a live provider process.\n- Graceful restart drains or terminates every superseded provider process and retries durable pending work exactly once.\n- Focused race tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 20:27
---
Additional live evidence: normal make restart entered its one-hour drain despite an empty public agent list. Emergency cutover execed the service at the same PID, and the superseded OOMPAH-700 Claude child survived that exec. Restart recovery then launched a second Codex implementation run for OOMPAH-700 while direct owner work was active. Adding human-only plus a Backlog/In Progress ownership fence finally terminated both provider processes, but also created automatic recovery checkpoint commits in the shared worktree. OOMPAH-698 was incorrectly reopened to Open despite its earlier recorded PASS and merged PR, requiring the owner to re-request the same audit ID. Cover graceful drain, exec cutover inheritance, restart redispatch fencing, and completed-PASS recovery in this bug.
---
author: oompah
created: 2026-08-02 21:10
---
Additional production reproduction from OOMPAH-700 on 2026-08-02: after PR #661 merged, auto-update began graceful shutdown and closed port 8090, but PID 3339192 remained alive. During that shutdown window the old process created detached audit worktree OOMPAH-700--terminal-audit-attempt-5f093d4b47fb and launched a Sonnet completion auditor, leaving health unavailable for more than 40 seconds. make force-restart was required to cut over to merge 39d1f2ec; owner override then cleared the stale persisted audit. Acceptance coverage must include preventing any new provider launch once shutdown/drain starts and ensuring the old PID cannot retain child transports after HTTP shutdown.
---
author: oompah
created: 2026-08-02 21:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 21:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 21:51
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.5K out [1.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 33s
- Log: OOMPAH-701__20260802T215133Z.jsonl
---
author: oompah
created: 2026-08-02 21:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 21:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 21:54
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 33s
- Log: OOMPAH-701__20260802T215336Z.jsonl
---
author: oompah
created: 2026-08-02 21:56
---
Claimed for direct project-owner implementation after two duplicate-preflight contract/truncation retries. Added human-only to fence further scheduler dispatch; OOMPAH-706 tracks the duplicate-screening cause.
---
author: oompah
created: 2026-08-02 22:48
---
Direct implementation complete at pushed head 455cde3b1a393b869240dc32404a17022d77cc8c. Provider runs now retain exact process identities and visible retirement state until descendants exit; lifecycle drain fences final provider launches and persists recovery; startup reaps inherited workspace children; repeated auditor policy denials terminate through the durable independent-retry path. Verification: 15,020 passed, 7 skipped, 1 xfailed via make test; final focused post-rebase suite 12 passed; make check-secrets passed; terminal mutation scan passed.
---
author: oompah
created: 2026-08-02 22:48
---
Retired revoked provider processes with exact descendant tracking, lifecycle launch fencing, inherited-child recovery, truthful UI/audit state, and bounded auditor denial retries. Full make test: 15,020 passed; secret scan passed.
---
author: oompah
created: 2026-08-02 23:27
---
Branch quality gate passed for `455cde3b1a393b869240dc32404a17022d77cc8c` using `make test` in 434.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 23:37
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-02 23:37
---
YOLO: merged PR #665.
---
author: oompah
created: 2026-08-02 23:38
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 23:38
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
