---
id: OOMPAH-710
type: bug
status: Ready to Integrate
priority: null
title: Keep oversized auditor tool results inside the read-only authority boundary
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T23:45:39.918535Z'
updated_at: '2026-08-03T01:31:45.401346Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f64744d5cece2f0044fdcdb2efdf7ceb2d7c11e4cc2e54b922d072574a454bd6
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T23:51:51.808644+00:00'
  matched_identifiers: []
  evidence: Project-owner review searched current Oompah tasks before creation; no
    existing task covers provider-private oversized auditor output escaping the strict
    read-only authority boundary. OOMPAH-701 records the live reproduction and OOMPAH-710
    is the dedicated follow-up.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: '2026-08-02T23:51:51.808644+00:00'
  owner_login: oompah-cli
  owner_resolution_reason: Project-owner review searched current Oompah tasks before
    creation; no existing task covers provider-private oversized auditor output escaping
    the strict read-only authority boundary. OOMPAH-701 records the live reproduction
    and OOMPAH-710 is the dedicated follow-up.
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 51468
  total_output_tokens: 4280
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 51468
      output_tokens: 4280
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1342
    cost_usd: 0.0
    recorded_at: '2026-08-02T23:46:36.307344+00:00'
  - profile: default
    model: haiku
    input_tokens: 51448
    output_tokens: 1662
    cost_usd: 0.0
    recorded_at: '2026-08-02T23:48:58.135833+00:00'
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1276
    cost_usd: 0.0
    recorded_at: '2026-08-02T23:51:35.796327+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-710__20260802T234610Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-710
    source_sha: 3a231ee97337db95bb131abc0dd27ca12133c257
    completed_at: '2026-08-02T23:46:36.314348+00:00'
  - run_id: OOMPAH-710__20260802T234817Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-710
    source_sha: 3a231ee97337db95bb131abc0dd27ca12133c257
    completed_at: '2026-08-02T23:48:58.152118+00:00'
  - run_id: OOMPAH-710__20260802T235114Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-710
    source_sha: 3a231ee97337db95bb131abc0dd27ca12133c257
    completed_at: '2026-08-02T23:51:35.811481+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-710
  head_sha: 205f413440767c5c2c94c641504f96f6a71c77bb
  submitted_at: '2026-08-03T00:04:50.427138+00:00'
  updated_at: '2026-08-03T00:04:50.427138+00:00'
---
## Summary

Triggered by: OOMPAH-701 terminal audit audit-c521d3856622 on 2026-08-02.

Production evidence: two independent Claude completion auditors (opus and sonnet) were terminated by the bounded repeated-policy-denial guard after using the approved read_file tool on a large source file. The ACP backend persisted the oversized 1,452,395-character result under ~/.claude/projects/.../tool-results outside the read-only terminal-audit worktree and instructed the model that it MUST read that path. The strict auditor authority boundary then denied the required follow-up access. Both transports failed, OOMPAH-701 remained In Validation, terminal_audit_health:launch_failures alerted with two transport failures, and the public running-agent list was empty while terminal-audit running remained 1.

Implementation scope:
- Keep oversized read/search output needed by an auditor inside an explicitly approved read-only result channel or audit-scoped temp root; do not direct a strict auditor to provider-private paths outside its authority.
- Prefer bounded/chunked tool responses that the model can continue reading through the approved MCP surface.
- Classify repeated policy denial caused by provider output persistence precisely and continue through eligible independent transports without stranding the audit.
- Make queued/running/in-progress audit counters describe the same durable/provider lifecycle while between candidates or exhausted.
- Clear launch/transport health once the affected audit is resolved so later audits are not contaminated.

Relevant code: oompah/acp_backends/claude.py and ACP tool-result bridging/truncation; oompah/api_agent.py approved file tools; oompah/authority_boundary.py auditor policy; oompah/orchestrator.py terminal-audit retry bookkeeping; terminal-audit health snapshot code.

Required tests:
- Reproduce an auditor reading a >1 MB file and prove every continuation path remains within its approved read-only worktree/tool channel.
- Run two candidate failures followed by a healthy independent candidate and prove the audit retries and completes exactly once.
- Assert public running agents, audit queued/running counters, health in_progress_count, and process liveness agree between attempts and after exhaustion.
- Assert the transport-failure alert clears after successful recovery and does not leak into a later audit.
- Focused ACP/auditor tests and make test/check-secrets pass.

Acceptance criteria:
- A compliant read-only auditor cannot be forced into an authority denial by Oompah/provider oversized-output handling.
- OOMPAH-701-style audits either launch a visible candidate or expose a truthful queued/exhausted state, never running=1 with no provider and in_progress=0.
- Recovery completes the terminal transition and clears the alert without an owner override.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 23:46
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 23:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 23:46
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 29s
- Log: OOMPAH-710__20260802T234610Z.jsonl
---
author: oompah
created: 2026-08-02 23:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 23:48
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 23:49
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 51.4K in / 1.7K out [53.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 44s
- Log: OOMPAH-710__20260802T234817Z.jsonl
---
author: oompah
created: 2026-08-02 23:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 23:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 23:51
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 25s
- Log: OOMPAH-710__20260802T235114Z.jsonl
---
author: oompah
created: 2026-08-02 23:51
---
Duplicate screening was inconclusive 3 times. Human action required: a project owner must review the authoritative task corpus and use the authenticated duplicate-screening owner-resolution action (POST /api/v1/issues/OOMPAH-710/duplicate-screening/owner-resolution) with a conclusive verdict and reason. This records the owner decision, resets the retry budget, and returns no_duplicate tasks to Open (or routes a verified duplicate to Duplicate Candidate). A plain verdict comment is not authoritative.
---
author: oompah
created: 2026-08-02 23:57
---
Reopened from premature Done: the authenticated owner-resolution raced the active third duplicate investigator, then direct owner work was moved to Done during its exit/deployment despite an uncommitted dirty worktree and no submission. Implementation remains actively owned here; a dedicated follow-up will cover that race.
---
author: oompah
created: 2026-08-03 00:01
---
Owner resumed direct implementation after the current deployed watchdog incorrectly reset active owner work to Open. OOMPAH-707 contains the durable-claim fix and is awaiting integration.
---
author: oompah
created: 2026-08-03 00:04
---
Direct owner implementation complete at exact pushed head 205f413440767c5c2c94c641504f96f6a71c77bb. Oompah now chunks read_file results before provider transport across Claude, Codex, and OpenCode; bounds search output; exposes offset/limit continuation through the approved tool; reconciles the terminal-audit running gauge after the last auditor exits; and verifies healthy third-candidate rotation after two transport failures. Post-rebase focused suite: 295 passed. Required make check-secrets passed.
---
author: oompah
created: 2026-08-03 00:04
---
Bound oversized auditor tool results before provider transport, kept continuations inside the approved read-only tool channel, reconciled stale audit gauges, and added provider-rotation regressions.
---
author: oompah
created: 2026-08-03 01:03
---
Live delivery note: the exact-head branch gate was not a test failure. It was interrupted as superseded at 00:57:42Z concurrently with OOMPAH-709 auditor retirement, with the OOMPAH-710 remote head unchanged. OOMPAH-714 now tracks the cross-task cancellation/stranding bug. This task remains valid and should be retried at the same accepted head after current review capacity frees.
---
author: oompah
created: 2026-08-03 01:23
---
Direct owner re-armed the unchanged exact head 205f413440767c5c2c94c641504f96f6a71c77bb. Its previous branch gate was interrupted by the cross-task cancellation bug tracked in OOMPAH-714, not by a test failure. Focused verification remains 295 passed plus make check-secrets; resubmitting for a clean isolated full gate.
---
author: oompah
created: 2026-08-03 01:23
---
Re-armed unchanged exact head after unrelated auditor retirement incorrectly canceled its first gate; OOMPAH-714 owns the root-cause fix.
---
author: oompah
created: 2026-08-03 01:31
---
Branch quality gate passed for `205f413440767c5c2c94c641504f96f6a71c77bb` using `make test` in 432.5s. Review creation may proceed.
---
<!-- COMMENTS:END -->
