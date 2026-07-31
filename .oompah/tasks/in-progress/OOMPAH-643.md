---
id: OOMPAH-643
type: task
status: In Progress
priority: null
title: Reconcile stale terminal-audit enforcement records and live queue metrics
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:17:38.708513Z'
updated_at: '2026-07-31T06:21:35.696082Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9abbcf4dd79879d506fdc5f606cc6e4c8640347bccd38c7c18d8bad4639174ac
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T06:19:18.495206+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: No active task matches terminal-audit enforcement reconciliation. OOMPAH-281
    and OOMPAH-282 are unrelated; archived audit-related tasks are terminal and excluded.
    No files or tracker state were modified.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: ceb8d701-da58-45ea-bc6f-05bffed5768e
oompah.task_costs:
  total_input_tokens: 250094
  total_output_tokens: 1841
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 250094
      output_tokens: 1841
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 250094
    output_tokens: 1841
    cost_usd: 0.0
    recorded_at: '2026-07-31T06:19:18.494485+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-643__20260731T061819Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-643
    source_sha: bb0fd760c3b2938d15ec2026ef5bfc2fd34b0682
    completed_at: '2026-07-31T06:19:18.499560+00:00'
---
## Summary

Runtime recovery evidence on 2026-07-31 shows terminal_audit_health pending_count=0 and in_progress_count=0 while terminal_audit_enforcement still reports pending_audits=209, metrics queued=157, and an oldest queued OOMPAH-309 record that is not dispatchable. stale_discarded also rises on successive state reads/ticks (223 to 275) because TerminalAuditMetrics.sync_pending appears to rehydrate stale entries from TerminalAuditEnforcement.pending_audits after the runtime health scan discards them.

Implementation scope: make the enforcement persistence record, dispatchable audit set, health scan, and observability gauges converge after restart and terminal authority changes. Reconcile or remove pending entries whose task is no longer In Validation, whose audit/evidence revision is superseded, or whose transition was owner-overridden; ensure stale records are counted at most once and are not re-added on the next sync. The queued/running gauges and oldest queue identity must describe only genuinely dispatchable live audits, while lifetime queued_total and outcome counters remain monotonic. Relevant files: oompah/terminal_audit_enforcement.py, oompah/terminal_audit_observability.py, oompah/terminal_transition_coordinator.py, orchestrator startup/recovery synchronization, and their tests.

Required tests: persisted restart state containing mixed live and stale audits; terminal override and status/evidence revision changes; missing/archived task; multi-project isolation; repeated sync/tick idempotency; one legitimately queued audit remains visible and launchable. Acceptance: after recovery, enforcement pending count equals the live coordinator set, queued/running/oldest gauges are accurate, stale_discarded does not grow without a new stale event, terminal_audit_health agrees with observability, focused tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 06:19
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 7
- Tokens: 250.1K in / 1.8K out [251.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 4s
- Log: OOMPAH-643__20260731T061819Z.jsonl
---
author: oompah
created: 2026-07-31 06:19
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 06:19
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-31 06:20
---
Understanding: Investigating the reconciliation issue between stale terminal_audit_enforcement records and live queue metrics. The problem is that after runtime recovery, stale entries are being rehydrated by sync_pending, causing incorrect counts and metrics. Need to ensure enforcement records, dispatchable audits, health scans, and observability gauges all converge correctly. Will examine terminal_audit_enforcement.py, terminal_audit_observability.py, and related files to understand the data flow and implement reconciliation logic.
---
author: oompah
created: 2026-07-31 06:21
---
Discovery: The issue involves reconciliation between three components: 1) TerminalAuditEnforcement (persists pending_audits), 2) TerminalAuditMetrics (tracks queued/running gauges), 3) TerminalTransitionCoordinator (manages live audit set). Root cause: sync_pending() rehydrates stale entries from enforcement.pending_audits after health scan discards them, causing stale_discarded counter to grow. Solution approach: (1) Reconcile enforcement.pending_audits with live coordinator set during recovery, (2) Filter stale entries in sync_pending, (3) Ensure health scan accuracy, (4) Add comprehensive reconciliation tests.
---
<!-- COMMENTS:END -->
