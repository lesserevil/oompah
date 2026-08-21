---
id: OOMPAH-1268
type: task
status: In Progress
priority: 3
title: Archive workflow_job_events for Archived tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-18T16:49:48.891025Z'
updated_at: '2026-08-21T05:43:53.399257Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 3211e93d-73f6-4a41-99a7-1bdcaa479ed0
  request_fingerprint: 2efda9a8ba2e984ce57f567673ef41d1f8d9cc0aaaf21d0aff8871d9296ce4a0
oompah.lifecycle_revision: 2
oompah.last_batch:
  batch_id: batch-1c1d234dcdd64c5ba5a90080c24b1e3a
  actor: shedwards
  committed_at: '2026-08-21T00:45:50.707738Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9acc3dee254bf9e0788859a48d116e4fd830a920b6ff7247e40afbf338354bac
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-21T02:15:37.370740+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed all 23 included similarity candidates in the\
    \ project task corpus. OOMPAH-1268 is uniquely focused on archiving workflow_job_events\
    \ from a durable cold table with high-water mark preservation. All related tasks\
    \ in the corpus address terminal audit identity, epic workflows, implementation\
    \ workflows, transition lifecycle, and review processes\u2014none duplicate the\
    \ event archival and database maintenance scope of OOMPAH-1268.\nLooking at the\
    \ task corpus provided, I'll conduct a systematic duplicate investigation for\
    \ OOMPAH-1268.\n\n## Task Analysis\n\n**OOMPAH-1268** addresses a specific problem:\n\
    - Database storage bloat: `workflow_jobs.sqlite3` grown to ~5GB\n- Root cause:\
    \ `workflow_job_events` is append-only and never pruned (19.8M rows)\n- Solution:\
    \ Archive old events for Archived tasks to a cold table, preserve sequences and\
    \ high-water mark\n\nThe comments indicate work has already been implemented in\
    \ PR #883 (workflow-event-archival) and fixed in PR #884 (migration trigger issues),\
    \ both with auto-merge enabled.\n\n## Corpus Review\n\nI reviewed all 23 included\
    \ similarity candidates. The closest matches are workflow-related tasks, but examining\
    \ each:\n\n- **OOMPAH-1000 through OOMPAH-1013**: Terminal audit identity, gates,\
    \ health, and epic validation issues\n- **OOMPAH-1014**: Orphaned terminal-audit\
    \ authority cleanup\n- **OOMPAH-1073 through OOMPAH-1086**: Backlog claims, epic\
    \ retirements, branch quality gates, review propagation, audit successor dispatch,\
    \ and transition journal lifecycle\n- **OOMPAH-1207**: Restart reconstruction\
    \ for imperative implementation jobs\n\n**None of these address event archival\
    \ or database storage maintenance.** They concern workflow execution, audit/review\
    \ processes, and task lifecycle management\u2014orthogonal concerns to OOMPAH-1268's\
    \ data retention/archival scope.\n\n## Verdict\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: Reviewed\
    \ all 23 included similarity candidates in the project task corpus. OOMPAH-1268\
    \ is uniquely focused on archiving workflow_job_events from a durable cold table\
    \ with high-water mark preservation. All related tasks in the corpus address terminal\
    \ audit identity, epic workflows, implementation workflows, transition lifecycle,\
    \ and review processes\u2014none duplicate the event archival and database maintenance\
    \ scope of OOMPAH-1268."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: e791c401-f12c-4106-b824-992e11de7412
oompah.work_contributors:
  runs:
  - run_id: a7a7ed26dc7141aa8f14c4ba306d46e0--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1268
    source_sha: 2da1c8073e0617b21959af89a4443b9f50c9a1d7
    completed_at: '2026-08-21T02:15:37.375025+00:00'
  - run_id: 3986d2996c2740a1ae79f6a96a54897b--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: general
    source_branch: OOMPAH-1268
    source_sha: null
    completed_at: ''
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1631
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1631
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1631
    cost_usd: 0.0
    recorded_at: '2026-08-21T02:15:37.369596+00:00'
---
## Summary

The durable workflow_jobs.sqlite3 grew to ~5GB because workflow_job_events is append-only and never pruned (19.8M rows). Add a bounded maintenance job that relocates job events for tasks with a durable lifecycle-final:Archived retirement proof into a new workflow_job_events_archive cold table, preserving original sequences and a persisted high-water mark so the snapshot-authority ABA fence (capture_snapshot_authority) never regresses.

Scope/files:
- oompah/workflow_jobs.py: schema V8 (archive table + guard row + task index), high-water meta key advanced in _append_event_locked, capture_snapshot_authority reads max(live, high-water), new archive_lifecycle_final_events(max_tasks,max_events).
- oompah/orchestrator.py: schedule _archive_workflow_events in _run_non_lifecycle_housekeeping (min_interval 300s).
- tests: tests/test_workflow_jobs.py (move/high-water/budget/skip/guard), tests/test_workflow_retirement_architecture.py (housekeeping bundle).

Acceptance: append-only DELETE still blocked outside archival; archived events moved to cold table with sequences preserved; snapshot authority high-water preserved after archival; maintenance job runs bounded and restart-safe; full suite green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-18 16:51
---
Implemented in PR #883 (branch workflow-event-archival), auto-merge enabled pending CI. Schema V8 archive table + high-water fence; bounded maintenance job in non-lifecycle housekeeping (300s). Local suites green (test_workflow_jobs, test_workflow_retirement_architecture, test_orchestrator_handlers, test_storage_cleanup = 543 passed). Will restart service onto merged revision after CI merges.
---
author: oompah
created: 2026-08-18 22:30
---
Follow-up fix in PR #884: existing stores kept their pre-V8 unconditional workflow_job_events DELETE trigger (CREATE TRIGGER IF NOT EXISTS won't replace it), so archival failed every sweep with IntegrityError and never made progress (20.1M hot events, 0 archived). Migration now drops+recreates the guarded trigger. Verified on the live DB: archival moved events successfully. Auto-merge enabled.
---
author: oompah
created: 2026-08-21 02:12
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-21 02:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-21 02:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 4s
- Log: OOMPAH-1268__20260821T021350Z.jsonl
---
author: oompah
created: 2026-08-21 05:43
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
