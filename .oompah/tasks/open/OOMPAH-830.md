---
id: OOMPAH-830
type: bug
status: Open
priority: 1
title: Project the active terminal-audit stage in multi-target chains
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T13:41:41.865936Z'
updated_at: '2026-08-05T18:18:49.269068Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 0ebabe0dcb3929768728384482444ffd290f8ccd1740d87e38a6ac5682c51012
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d2fdb514-8cb0-437c-a1c4-1f4a56f59598
  claim_owner: 3a62b7a5-bbb7-4494-ae8d-738d99774e0d
  claimed_at: '2026-08-05T18:18:26.880826+00:00'
  claim_expires_at: '2026-08-05T18:48:26.880826+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8dad7f24-0220-49d8-a372-7c235aa16db9
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
<!-- COMMENTS:END -->
