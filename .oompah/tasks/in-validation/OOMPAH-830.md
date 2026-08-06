---
id: OOMPAH-830
type: bug
status: In Validation
priority: 1
title: Project the active terminal-audit stage in multi-target chains
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:41:41.865936Z'
updated_at: '2026-08-06T01:35:43.322688Z'
work_branch: OOMPAH-830
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/726
review_number: '726'
review_head: d101c5712fe359efdbfbc295b41ed0a9680faa83
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0ebabe0dcb3929768728384482444ffd290f8ccd1740d87e38a6ac5682c51012
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T18:25:59.271067+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active duplicate was confirmed in the supplied corpus.\
    \ The closest reviewed tasks were archived and addressed unrelated deduplication\
    \ or workflow issues.\nFocus handoff: duplicate_detector  \nDuplicate preflight\
    \ verdict: no_duplicate  \nMatches: none  \n\nEvidence: No active duplicate was\
    \ confirmed in the supplied corpus. The closest reviewed tasks were archived and\
    \ addressed unrelated deduplication or workflow issues."
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
oompah.task_costs:
  total_input_tokens: 46476
  total_output_tokens: 303
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46476
      output_tokens: 303
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46476
    output_tokens: 303
    cost_usd: 0.0
    recorded_at: '2026-08-05T18:25:59.267699+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-830__20260805T181905Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-830
    source_sha: b53bdbc77c7a50d332a97096ebc85d7923280854
    completed_at: '2026-08-05T18:25:59.312915+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-830
  head_sha: d101c5712fe359efdbfbc295b41ed0a9680faa83
  submitted_at: '2026-08-06T00:24:04.803952+00:00'
  updated_at: '2026-08-06T00:24:04.803952+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/726
oompah.review_number: '726'
oompah.work_branch: OOMPAH-830
oompah.target_branch: main
oompah.review_head: d101c5712fe359efdbfbc295b41ed0a9680faa83
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1eb4b5b5bf8f
    project_id: proj-14849f1b
    task_id: OOMPAH-830
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ea04ec1700e74b31a1d48a63e3115fe906780bb64052f41e2580faf2f05c32be
    attempts:
    - version: 1
      attempt_id: attempt-9b848a80f557
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ea04ec1700e74b31a1d48a63e3115fe906780bb64052f41e2580faf2f05c32be
      created_at: '2026-08-06T01:35:38.240531+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T01:35:38.240531+00:00'
      branch_key: OOMPAH-830
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-06T01:34:41.033554+00:00'
    updated_at: '2026-08-06T01:35:38.240531+00:00'
  - version: 1
    audit_id: audit-c3b5cec9c554
    project_id: proj-14849f1b
    task_id: OOMPAH-830
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ea04ec1700e74b31a1d48a63e3115fe906780bb64052f41e2580faf2f05c32be
    attempts: []
    requested_by:
      version: 1
      identity: yolo-merge
      source: oompah
    previous_state: In Review
    created_at: '2026-08-06T01:34:41.033554+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9b848a80f557
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ea04ec1700e74b31a1d48a63e3115fe906780bb64052f41e2580faf2f05c32be
    created_at: '2026-08-06T01:35:38.240531+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T01:35:38.240531+00:00'
    branch_key: OOMPAH-830
---
## Summary

Triggered by: OOMPAH-825

Live OOMPAH-825 observability regression on 2026-08-05. A standalone merge correctly created a two-stage terminal chain: audit-5ffc50b0397d targeted Done and passed, then audit-073bdc9f703b targeted Merged and passed. Durable result intents correctly held In Validation after the Done stage and ultimately applied Merged. However, server._issue_terminal_audit_summary always projects document.pending_chain[0], so list/detail/UI surfaces reported phase=passed and target_state=Done while the Merged record was pending and running, and continued showing the stale Done stage after final Merged completion. This made normal sequential dispatch look like a duplicate auditor and PASS-without-finalization race. Implementation scope: define one authoritative terminal-audit chain projection that distinguishes completed stages, current active stage, next queued target, and final requested target; use it consistently in issue list/detail/activity/dashboard and any event payloads; preserve single-record compatibility and safe field redaction. Relevant code: oompah/server.py _issue_terminal_audit_summary and terminal audit metadata/result-intent helpers. Required tests: single-stage pending/running/pass/fail; Done running with Merged queued; Done PASS plus Merged pending; Merged running and PASS; restart and result-intent application windows; retries, supersession, and completed historical records; list/detail/activity/event parity for the same chain. Acceptance criteria: operator surfaces never label an active Merged stage as a duplicate Done audit, the current/next/final targets are truthful throughout the durable chain, completed chains show the final applied stage, and existing consumers remain backward compatible. Focused server/terminal-audit observability tests and make test must pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 18:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 18:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 18:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.5K in / 303 out [46.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 12s
- Log: OOMPAH-830__20260805T181905Z.jsonl
---
author: oompah
created: 2026-08-05 18:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 18:30
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 18:56
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 26m 22s
- Log: OOMPAH-830__20260805T183022Z.jsonl
---
author: oompah
created: 2026-08-05 18:57
---
Temporary direct-owner fence applied after verifying the worktree was clean: the native Codex provider bootstrap itself was waiting on/holding heavyweight validation capacity due OOMPAH-841, so allowing this session to start would reproduce the live whole-session lease deadlock. No implementation work was discarded. Keep fenced until standalone deployment OOMPAH-842 is live, then release back to normal server dispatch.
---
author: oompah
created: 2026-08-05 23:58
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 23:58
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 23:59
---
Understanding: the bug is a stale first-stage projection of durable terminal-audit chains. I will identify the authoritative chain/result-intent state, define a truthful current/next/final projection with single-record compatibility, update all server surfaces and event payloads, add focused regression tests, then verify, commit, push, and submit.
---
author: oompah
created: 2026-08-06 00:21
---
Verification: focused server/dashboard/lifecycle/enforcement coverage passed (212 tests). The full Makefile workflow passed 15,665 tests, with 7 skipped, 1 xfailed, and 44 warnings; terminal mutation scan passed 8/8. The native setup wrapper could not create its read-only lease, so the gate used the provisioned project runtime after setup was bypassed.
---
author: oompah
created: 2026-08-06 00:22
---
Implementation: centralized  in . It projects live active/current/next/final stages, completed and superseded history, stage-matched attempts, and redacted result-intent handoff state. The legacy flat summary fields now follow the active stage or final completed stage. List, detail, activity, and websocket board payloads already share this helper; dashboard cards/details now render current, next, and final targets. Added regression coverage in .
---
author: oompah
created: 2026-08-06 00:22
---
Implementation update: centralized terminal-audit chain projection in server.py. It projects live active/current/next/final stages, completed and superseded history, stage-matched attempts, and redacted result-intent handoff state. Legacy flat summary fields now follow the active stage or final completed stage. List, detail, activity, and websocket board payloads share this helper; dashboard cards/details render current, next, and final targets. Regression coverage is in tests/test_terminal_status_interfaces.py. (A prior comment attempt contained shell backticks; this plain-text update is authoritative.)
---
author: oompah
created: 2026-08-06 00:23
---
Completion: delivered and pushed commit d101c5712. Terminal-audit observability now projects the active stage in multi-target chains, exposes truthful current/next/final and completed-stage context, handles result-intent windows and supersession safely, and keeps list/detail/activity/dashboard payloads aligned with legacy fields preserved. Focused and full Makefile verification passed.
---
author: oompah
created: 2026-08-06 00:24
---
Projected active terminal-audit stages across multi-target chains; added redacted chain/result-intent observability, aligned dashboard surfaces, and regression coverage. Full Makefile gate passed.
---
author: oompah
created: 2026-08-06 00:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 99
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 25m 31s
- Log: OOMPAH-830__20260805T235859Z.jsonl
---
author: oompah
created: 2026-08-06 01:22
---
Branch quality gate passed for `d101c5712fe359efdbfbc295b41ed0a9680faa83` using `make test` in 637.9s. Review creation may proceed.
---
author: oompah
created: 2026-08-06 01:34
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-06 01:34
---
YOLO: merged PR #726.
---
<!-- COMMENTS:END -->
