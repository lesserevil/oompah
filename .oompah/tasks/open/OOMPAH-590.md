---
id: OOMPAH-590
type: bug
status: Open
priority: 1
title: Retry terminal audits after auditor launch or transport failure
parent: OOMPAH-585
children: []
blocked_by:
- OOMPAH-589
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:22.194798Z'
updated_at: '2026-07-30T14:31:30.346709Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-590
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 668767bd8dc2d7a2894cecc5ec77ed49df140e098ac2791ef421df1d1e9f916c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T14:31:23.762647+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Active task records available locally are OOMPAH-281 (self-hosted CI
    runner) and OOMPAH-282 (state-branch migration failure); neither covers terminal-audit
    retry or auditor transport/session failures. Repository-wide searches found no
    active matching task.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0ec70f19-d33b-4f1a-a892-a332b5a1d659
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-590
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-590
  base_branch: epic-OOMPAH-585
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T14:20:49.754823+00:00'
oompah.task_costs:
  total_input_tokens: 3976570
  total_output_tokens: 13609
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 3976570
      output_tokens: 13609
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 3976570
    output_tokens: 13609
    cost_usd: 0.0
    recorded_at: '2026-07-30T14:31:23.761710+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-590__20260730T142055Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-585--task-OOMPAH-590
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T14:31:23.771017+00:00'
---
## Summary

Implementation scope

Treat completion-auditor launch, malformed endpoint, transport, timeout, and provider-session failures as recoverable audit-attempt outcomes. Persist a safe failure classification, release the candidate claim, retry with bounded backoff and the next eligible independent candidate, and prevent duplicate concurrent attempts for one audit/evidence fingerprint. Preserve terminal-state idempotency and audit history. Relevant files include oompah/auditor_dispatch.py, oompah/terminal_transition_coordinator.py, orchestrator audit dispatch/reconciliation, and state metadata.

Tests

Cover launch exception, transport exception, timeout, next-candidate fallback, exhausted candidates, restart recovery, duplicate tick coalescing, and successful later completion. Run focused terminal/auditor tests and make test.

Acceptance criteria

A transient auditor-session failure cannot leave a request silently Pending forever; the request either passes on retry or reaches an explicit actionable exhausted/needs-human state.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 14:18
---
Project-owner-approved green recovery work; dispatch under recorded dependencies and acceptance criteria.
---
author: oompah
created: 2026-07-30 14:20
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 14:20
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 14:31
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 2, Tool calls: 43
- Tokens: 4.0M in / 13.6K out [4.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 37s
- Log: OOMPAH-590__20260730T142055Z.jsonl
---
<!-- COMMENTS:END -->
