---
id: OOMPAH-645
type: task
status: Backlog
priority: null
title: Clear recovered terminal-audit transport failures without contaminating later
  audits
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:47:58.732088Z'
updated_at: '2026-07-31T06:47:58.732088Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live reproduction on 2026-07-31: OOMPAH-607 auditor attempt 1 ended with a transport failure at the configured turn limit, attempt 2 launched successfully and completed the terminal transition, and OOMPAH-607 left In Validation. The terminal_audit_health:launch_failures error nevertheless remained degraded with transport_failure_count=1 and text claiming failures for pending audits. When OOMPAH-641 subsequently entered validation, the stale OOMPAH-607 failure appeared to describe the unrelated new audit. This violates OOMPAH-592 acceptance that alerts clear after underlying recovery.

Implementation scope: model launch/transport failures as unresolved per-audit attempt health, not a process-lifetime historical error gauge. A successful replacement launch may keep diagnostic history but must establish active recovery; a successful verdict/terminal transition must resolve the prior failure and clear the actionable alert. A later unrelated pending audit must never inherit another task’s failure. Preserve durable alerts for genuinely unresolved retries, repeated transport failures, retry exhaustion, unavailable transports, and restart recovery. Relevant files: oompah/terminal_audit_health.py, terminal audit coordinator/orchestrator observation construction, persisted attempt metadata, state/alerts serialization, and dashboard tests.

Required tests: transport failure then successful retry/verdict clears degradation; active replacement is represented as recovering rather than requiring operator transport restoration; one recovered audit plus a different pending audit stays clean; restart between failure/retry/success; repeated failure and retry exhaustion remain actionable; multi-project isolation; alert text/counts refer only to unresolved audit identities. Acceptance: after OOMPAH-607-style recovery the health alert disappears, later audits are not contaminated, historical counters remain observable separately from actionable health, focused terminal-audit health tests pass, terminal mutation scan passes, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

