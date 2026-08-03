---
id: OOMPAH-741
type: bug
status: Open
priority: 1
title: Classify dashboard facts by current operator actionability
parent: OOMPAH-740
children: []
blocked_by:
- OOMPAH-735
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T22:56:13.861445Z'
updated_at: '2026-08-03T23:02:31.493154Z'
work_branch: epic-OOMPAH-740--task-OOMPAH-741
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: c7a1bdee4c6e9842740640e868811f3e155e2924d6a6e258d7ab165be372c60c
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T23:02:22.755502+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-735 covers integration recovery; OOMPAH-742\u2013\
    745 cover separate UI, transcript, resynchronization, and browser-test work. None\
    \ duplicates this cross-producer server-side actionability contract.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none\n\nEvidence: OOMPAH-735 covers integration recovery; OOMPAH-742\u2013745\
    \ cover separate UI, transcript, resynchronization, and browser-test work. None\
    \ duplicates this cross-producer server-side actionability contract."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 81b994b8-3626-428a-9515-b5d3354d5fe5
oompah.work_branch: epic-OOMPAH-740--task-OOMPAH-741
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-740--task-OOMPAH-741
  base_branch: epic-OOMPAH-740
  base_sha: 583fb236963493a820f36eabdd29789fa5497e6b
  updated_at: '2026-08-03T23:00:18.598601+00:00'
oompah.task_costs:
  total_input_tokens: 46242
  total_output_tokens: 259
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46242
      output_tokens: 259
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46242
    output_tokens: 259
    cost_usd: 0.0
    recorded_at: '2026-08-03T23:02:22.753889+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-741__20260803T230037Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-740--task-OOMPAH-741
    source_sha: 583fb236963493a820f36eabdd29789fa5497e6b
    completed_at: '2026-08-03T23:02:22.799945+00:00'
---
## Summary

Implement one structured server-side presentation contract for dashboard alerts and health facts.

Scope:
- Define explicit fields for action_required, severity, lifecycle or recovery state, stable identity, compact summary, sanitized detail, remediation, and active versus recovered status.
- Apply the contract to generic orchestrator alerts, terminal-audit health, branch quality gates, authentication health, repository hygiene, and integration retry alerts.
- Build on OOMPAH-735 for integration recovery rather than duplicating its classifier.
- Treat normal pending or running audits, active quality gates, healthy repository inventory, bounded retries, recovered failures, and intentional policy denials as status or history rather than global warnings.
- Preserve task-local failure evidence and metrics even when a condition is not globally actionable.
- Deduplicate equivalent facts at the snapshot boundary using stable source identity and prefer the highest current severity.
- Ensure recovery deterministically clears or downgrades the actionable fact.

Relevant files: oompah/orchestrator.py, oompah/terminal_audit_health.py, auth and repository health builders, oompah/server.py snapshot construction, and their existing unit tests.

Required tests:
- Each producer emits the structured contract without secrets.
- Normal operating states never become actionable warnings.
- Stale, exhausted, unowned, corrupt, or otherwise blocked states do become actionable.
- Recovery removes or downgrades the alert while retaining metrics and task diagnostics.
- Duplicate producers collapse to one stable fact.
- OOMPAH-735 integration behavior remains covered.

Acceptance criteria:
- The state API gives the frontend an unambiguous actionability decision without parsing message text.
- Every actionable warning describes a current condition requiring operator intervention.
- Historical and automatically recovering failures remain inspectable but do not occupy the global warning surface.
- Focused alert, health, state API, and WebSocket tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 23:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 23:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 23:02
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.2K in / 259 out [46.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 14s
- Log: OOMPAH-741__20260803T230037Z.jsonl
---
<!-- COMMENTS:END -->
