---
id: OOMPAH-810
type: task
status: In Validation
priority: null
title: Return completed auditor command results without stranding the ACP session
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: &id001 []
labels: []
assignee: null
created_at: '2026-08-04T22:01:00.091773Z'
updated_at: '2026-08-05T19:18:09.854201Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-810
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: eb5988541933bb61ffa8da942cca688895a4da328725747475570afc6aaaac22
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T22:06:45.704776+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-806 addresses gate-authority regression, OOMPAH-809\
    \ addresses scheduler capacity starvation, and OOMPAH-770 is a broader liveness\
    \ epic; none covers completed ACP command-result delivery.\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \n\nEvidence:\
    \ OOMPAH-806 addresses gate-authority regression, OOMPAH-809 addresses scheduler\
    \ capacity starvation, and OOMPAH-770 is a broader liveness epic; none covers\
    \ completed ACP command-result delivery."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-810
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-763--task-OOMPAH-810
  base_branch: epic-OOMPAH-763
  base_sha: b1c089614b81076b961c7681b6ddad64ca68191e
  head_sha: bb42de1e71f355a8f0eb2c4c0ddd958715b646e6
  integrated_sha: bb42de1e71f355a8f0eb2c4c0ddd958715b646e6
  submitted_at: '2026-08-05T17:46:35.612561+00:00'
  updated_at: '2026-08-05T18:14:04.464750+00:00'
oompah.task_costs:
  total_input_tokens: 46797
  total_output_tokens: 4100
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46708
      output_tokens: 435
      cost_usd: 0.0
    unknown:
      input_tokens: 89
      output_tokens: 3665
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46708
    output_tokens: 435
    cost_usd: 0.0
    recorded_at: '2026-08-04T22:06:45.703190+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 89
    output_tokens: 3665
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:17:57.677538+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-810__20260804T220544Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-810
    source_sha: f1e7925b7263f980517f943291102c8c83335ed2
    completed_at: '2026-08-04T22:06:45.735007+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-af70e1b81ff1
    project_id: proj-14849f1b
    task_id: OOMPAH-810
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c37b3647f25b881d76c64e2ca782c859944ed97f1235879018cb0f69c93b7d90
    attempts:
    - version: 1
      attempt_id: attempt-4d0bf58a6399
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c37b3647f25b881d76c64e2ca782c859944ed97f1235879018cb0f69c93b7d90
      created_at: '2026-08-05T18:16:10.681061+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T18:16:10.681061+00:00'
      branch_key: epic-OOMPAH-763--task-OOMPAH-810
      ended_at: '2026-08-05T19:18:05.116942+00:00'
      failure_reason: auditor session abandoned after attempt TTL
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-05T18:14:08.249508+00:00'
    updated_at: '2026-08-05T18:16:10.681061+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4d0bf58a6399
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c37b3647f25b881d76c64e2ca782c859944ed97f1235879018cb0f69c93b7d90
    created_at: '2026-08-05T18:16:10.681061+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T18:16:10.681061+00:00'
    branch_key: epic-OOMPAH-763--task-OOMPAH-810
    ended_at: '2026-08-05T19:18:05.116942+00:00'
    failure_reason: auditor session abandoned after attempt TTL
---
## Summary

Live reproduction on 2026-08-04: OOMPAH-793 audit audit-8b63c91a6c05 / attempt-7e65eccae518 invoked the approved make test-serial command at 21:44:04. The pytest and shell children remained live and were correctly protected while running, then exited around 21:56. The ACP JSONL never emitted a tool_result after the permission grant, RunningEntry retained the provider with no command child, and the server detected a stall at 21:58:46 before forced shutdown. This is distinct from merged OOMPAH-648 (do not false-stall a live child), OOMPAH-719 (bound oversized run_command output), and OOMPAH-612 (submit_audit_result same-loop deadlock): the approved command finished, but completion/output never returned to the auditor.\n\nImplementation scope:\n- Trace the ACP run_command subprocess completion, ToolLivenessMonitor cleanup, CommandOutputStore truncation/paging, MCP response bridge, and provider transport after a large configured Makefile command exits.\n- Guarantee exactly one bounded tool_result reaches the session promptly after process exit, regardless of output size, pass/fail exit, cancellation, or concurrent stall inspection; expose an opaque continuation ID without synchronously serializing unbounded output.\n- Clear tool-liveness ownership only after the result is durably deliverable, and distinguish running, result_pending, result_delivered, and provider_stalled in state metrics.\n- If result delivery cannot complete within a bounded deadline, retire/retry the audit once with a precise transport classification; never leave a provider visible indefinitely or repeat an expensive successful validation blindly when durable command evidence can be reused safely.\n- Preserve read-only audit authority, output redaction, per-session isolation, command deadlines, independent-candidate rotation, and terminal exact-head fencing. Coordinate with OOMPAH-781 durable terminal-audit cutover instead of adding another process-local lifecycle.\n\nRequired tests:\n- An approved command emits more than 1 MB, exits successfully after a silent interval, and produces one bounded tool_result plus pageable continuation without provider-private paths.\n- Passing and failing exits, child exit concurrent with stall scan, cancellation, provider disconnect, and restart each clear liveness and yield exactly one durable outcome/retry.\n- A completed command cannot remain RunningEntry-only with no child and no ACP event beyond the result-delivery deadline.\n- Reproduce OOMPAH-793 with make test-serial-shaped output and prove the auditor can submit its verdict and exit normally.\n- Focused ACP/tool-liveness/auditor tests and make test pass.\n\nAcceptance criteria: once an approved auditor command exits, the ACP session receives its bounded result or a precise recoverable transport failure within a fixed deadline; no completed command strands In Validation work or consumes a provider slot; OOMPAH-793-style recovery does not require operator mutation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 22:05
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 22:05
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 22:06
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.7K in / 435 out [47.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 24s
- Log: OOMPAH-810__20260804T220544Z.jsonl
---
author: oompah
created: 2026-08-05 15:56
---
Additional live worker reproduction (not only auditors): OOMPAH-523 run OOMPAH-523__20260805T141858Z requested approved `make test 2>&1 | tail -50` at 15:18:28, waited fairly for the validation lease, acquired it after OOMPAH-815 exact gate, ran PID 2028835/pytest 2029072, and released the lane around 15:54:03. No ACP tool_result was ever appended. In the same boundary the stall supervisor used 5,726s accumulated no-event age, terminated the otherwise healthy Sonnet worker, and escalated it to deep. Extend OOMPAH-810 acceptance to implementation-worker ACP run_command as well as terminal auditors: child exit/result_pending must suppress the generic stall decision until exactly one bounded result is delivered or a precise delivery timeout is persisted.
---
author: oompah
created: 2026-08-05 15:59
---
Graph correction: removed the OOMPAH-768 hard-start. OOMPAH-523 proves this common ACP result-delivery race affects implementation workers required to complete 768, so keeping the repair behind 768 is circular operationally even though the tracker graph is acyclic. The transport/result_pending fix can coordinate with OOMPAH-781 durable replay without depending on the whole domain epic landing first.
---
author: oompah
created: 2026-08-05 16:04
---
Deadlock correction: the earlier dependency removal omitted --hard-start, so the actual start_dependencies edge on OOMPAH-768 remained despite the comment. Removed that exact hard-start edge now. OOMPAH-810/833 may proceed independently and no longer wait behind the workflow whose ACP result-delivery race they repair.
---
author: oompah
created: 2026-08-05 17:00
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 17:01
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 17:16
---
Understanding: the approved auditor command can exit successfully while its result remains trapped between subprocess completion, liveness cleanup, output paging, and ACP/provider delivery. I will trace those boundaries, establish one bounded durable result or precise transport failure with race-safe state transitions, add focused regression tests, and verify the affected Makefile checks.
---
author: oompah
created: 2026-08-05 17:17
---
Discovery: _exec_run_command waits on communicate() and clears ToolLivenessMonitor in finally, while the monitor uses Popen.poll(). A shell may exit before descendants close inherited stdout/stderr, making reconciliation see no live child and retire the ACP session while the handler is still draining output. There is no result_pending/durable-delivery state, so the liveness owner can disappear before an ACP tool_result is emitted. I am tracing backend event delivery and will close this race with bounded, exactly-once result state.
---
author: oompah
created: 2026-08-05 17:27
---
Implementation: added a race-safe ToolLivenessMonitor handoff lifecycle with running/result_pending/result_delivered/provider_stalled phases, a fixed 30-second result-delivery deadline, precise timeout classification, and bounded lifecycle metrics. Real API/ACP tool bridges defer cleanup until their bounded tool_result is persisted/emitted; child exit during communicate() is treated as pending. Exposed per-run and aggregate opaque liveness metrics, and added large-output, silent-interval, pass/fail, deadline, exactly-once, and continuation regressions.
---
author: oompah
created: 2026-08-05 17:42
---
Verification: focused liveness/output/ACP/project-tool suites pass (87 tests); API-budget/auditor/console suites pass (212 tests, only pre-existing tempfile warnings); event-driven/orchestrator reconciliation suites pass (504 tests); state/API/WebSocket-adjacent checks pass (40 tests); compileall and diff checks pass. An ACP handoff-model subset remains environment-blocked before session construction because its fixture writes the read-only global agent-log directory, unrelated to this change.
---
author: oompah
created: 2026-08-05 17:46
---
Completion: pushed bb42de1e7. Approved ACP/API commands now retain liveness through bounded result preparation and provider-visible delivery, transition to precise provider_stalled on the fixed handoff deadline, and expose result lifecycle metrics without provider-private paths. Large make-shaped output remains bounded/pageable, pass/fail and race regressions are covered, and focused plus reconciliation/state suites pass. Canonical make test/terminal-audit targets were attempted but task-private uv bootstrap is blocked by the environment DBus transient-scope error; make check-secrets passes.
---
author: oompah
created: 2026-08-05 17:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 146
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 45m 45s
- Log: OOMPAH-810__20260805T170109Z.jsonl
---
author: oompah
created: 2026-08-05 17:46
---
Preserve bounded ACP/API command results through exactly-once provider delivery with race-safe liveness phases, precise delivery timeout recovery, and lifecycle metrics; pushed bb42de1e7.
---
author: oompah
created: 2026-08-05 18:14
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 18:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 18:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 19:18
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 64
- Tokens: 89 in / 3.7K out [3.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 1h 1m 42s
- Log: OOMPAH-810__20260805T181639Z.jsonl
---
<!-- COMMENTS:END -->
