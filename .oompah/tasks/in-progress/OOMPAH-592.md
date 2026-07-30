---
id: OOMPAH-592
type: feature
status: In Progress
priority: 1
title: Alert on terminal-audit launch failures and backlog age
parent: OOMPAH-585
children: []
blocked_by:
- OOMPAH-589
- OOMPAH-590
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:28.755226Z'
updated_at: '2026-07-30T15:34:10.113923Z'
work_branch: epic-OOMPAH-585--task-OOMPAH-592
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e63ac8087f03fa3d8e428789060b5e66d27092edde9c2b197433ace96b4cd4ac
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T14:47:44.845272+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-590 (retry mechanics), OOMPAH-591 (backlog reconciliation),
    OOMPAH-460 (broader UI/observability epic), and OOMPAH-599 (final invariant verification).
    None owns the specific durable alerting and recovery-clear behavior described
    by OOMPAH-592.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 05fdcabe-8554-4489-b773-2a19f3e1c2c3
oompah.work_branch: epic-OOMPAH-585--task-OOMPAH-592
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-585--task-OOMPAH-592
  base_branch: epic-OOMPAH-585
  base_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
  updated_at: '2026-07-30T15:25:33.084874+00:00'
oompah.task_costs:
  total_input_tokens: 3151103
  total_output_tokens: 25005
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 3151103
      output_tokens: 25005
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 3151103
    output_tokens: 25005
    cost_usd: 0.0
    recorded_at: '2026-07-30T14:47:44.844076+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-592__20260730T143353Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-585--task-OOMPAH-592
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T14:47:44.853900+00:00'
---
## Summary

Implementation scope

Extend terminal-audit health so the operator alert surface includes auditor launch/transport failure counts, oldest pending age, retry exhaustion, and stale In Validation records. Keep the existing enforcement/quarantine signal distinct but aggregate them into truthful project/service health. Alerts must clear only after underlying recovery and must not expose provider secrets or model output. Relevant files include terminal audit health/metrics, oompah/server.py state and alerts APIs, and dashboard rendering.

Tests

Cover empty backlog, fresh normal queue, aged backlog, repeated launch failures, exhausted candidates, successful recovery/clear, restart persistence, and redaction. Run focused API/dashboard tests and make test.

Acceptance criteria

A state with failed auditor launches or materially stale pending audits cannot show an empty healthy alert list; recovered normal operation clears the alert deterministically.

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
created: 2026-07-30 14:33
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 14:33
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 14:47
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 2, Tool calls: 92
- Tokens: 3.2M in / 25.0K out [3.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 14m 0s
- Log: OOMPAH-592__20260730T143353Z.jsonl
---
author: oompah
created: 2026-07-30 15:04
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 15:04
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:25
---
Agent failed: RuntimeError: Codex exec exited with code 1: 2026-07-30T15:14:54.440078Z ERROR codex_core::tools::router: error=apply_patch verification failed: Failed to find expected lines in /home/shedwards/.oompah/worktrees/oompah/OOMPAH-592/oompah/orchestrator.py:
        self._alerts: list[
            dict[str, str]
        ] = []  # {"level": "warning", "message": "..."}
. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-07-30 15:25
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 63
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 20m 15s
- Log: OOMPAH-592__20260730T150921Z.jsonl
---
author: oompah
created: 2026-07-30 15:25
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 15:25
---
Focus: Frontend Developer
---
author: oompah
created: 2026-07-30 15:34
---
Understanding: Previous agents implemented most of the structure in .pyc form but failed to commit. I found: (1) terminal_audit_health.py with AuditHealthObservation, TerminalAuditHealth, build_terminal_audit_health, terminal_audit_health_alerts; (2) orchestrator changes adding _refresh_terminal_audit_health(), _audit_health field, extending _audit_metrics; (3) dashboard UI changes adding terminal-audit-health banner; (4) tests in test_terminal_audit_health.py, test_terminal_audit_health_api.py, test_dashboard_terminal_audit_health.py. Plan: Reconstruct all these files from .pyc decompilation data, write clean implementations, run tests, commit and push.
---
<!-- COMMENTS:END -->
