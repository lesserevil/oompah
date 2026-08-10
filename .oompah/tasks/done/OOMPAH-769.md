---
id: OOMPAH-769
type: epic
status: Done
priority: 1
title: Make one transition service the only task-status writer
parent: OOMPAH-763
children:
- OOMPAH-775
- OOMPAH-776
- OOMPAH-778
- OOMPAH-801
- OOMPAH-802
- OOMPAH-803
blocked_by: []
start_blocked_by: &id001
- OOMPAH-764
labels: []
assignee: null
created_at: '2026-08-04T13:56:01.554943Z'
updated_at: '2026-08-10T01:20:14.905100Z'
work_branch: epic-OOMPAH-769
target_branch: epic-OOMPAH-763
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.target_branch: epic-OOMPAH-763
oompah.work_branch: epic-OOMPAH-769
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-eb82ffaac667
    project_id: proj-14849f1b
    task_id: OOMPAH-769
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3999310191440c7f9b410904382dce4702afc8c2b0ee62bbc0909a9f77978698
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This nested epic scope is contained in the validated parent composition. It
      is closed as Done until the parent review lands, after which Merged provenance
      can be recorded without violating shared-epic landing constraints.
    created_at: '2026-08-08T16:30:12.998770+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-769
    target_state: Done
    evidence_fingerprint: 3999310191440c7f9b410904382dce4702afc8c2b0ee62bbc0909a9f77978698
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:30:22.141498+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Historical audited Done record lacks safe exact current landing proof;
      retain immutable terminal provenance and retire recurring reassessment without
      creating new work.
    marked_at: '2026-08-10T01:20:13.287129+00:00'
    updated_at: '2026-08-10T01:20:13.287129+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Historical audited Done record lacks safe exact current landing proof;
        retain immutable terminal provenance and retire recurring reassessment without
        creating new work.
      recorded_at: '2026-08-10T01:20:13.287129+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Introduce a project-scoped TaskTransitionService that owns every task-status mutation. A TransitionIntent must include task/project identity, expected status/version, requested status, evidence generation and exact head when relevant, actor/authority, stable reason code, idempotency key, and originating workflow job. Persist an append-only transition journal and use compare-and-swap/idempotent verification so stale generations cannot overwrite newer work. Initially preserve current behavior while routing all direct update_issue status calls from orchestrator.py, server.py, watchdogs, intake, audit enforcement, tools, and auxiliary modules through the service. Adapt TerminalTransitionCoordinator behind the service without weakening terminal audits. Add an automated architectural test that rejects direct production status writes outside the service and tracker adapters. Required tests: concurrent conflicting intents, replay/idempotency, actor/project isolation, terminal staging, stale evidence, restart between journal/request/apply/verify, and compatibility for existing API/CLI transitions. Acceptance: the service and tracker adapters are the only production status writers; every applied/rejected/superseded transition is journaled with objective reason; existing safety semantics and API behavior remain intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 16:30
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This nested epic scope is contained in the validated parent composition. It is closed as Done until the parent review lands, after which Merged provenance can be recorded without violating shared-epic landing constraints.
---
<!-- COMMENTS:END -->
