---
id: OOMPAH-873
type: bug
status: Open
priority: 1
title: Make issue-list and full-sync snapshots match fresh state-branch detail reads
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:50:20.335247Z'
updated_at: '2026-08-07T07:21:28.381062Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d1ee86e4ec16c18e915ca678ab368225568d7d5bd26df38fa56b992b965d3f41
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T07:21:21.253138+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: ** The supplied corpus of 30 similarity candidates are\
    \ all in terminal/Archived state. None describe the same underlying issue as OOMPAH-873\
    \ (stale snapshot-vs-detail-read consistency for native tracker state). The closest\
    \ related tasks (OOMPAH-10: native tracker sync, OOMPAH-160: atomic task writes)\
    \ address different root causes. No active duplicate exists in the provided corpus.\
    \ The corpus notes 392 omitted similarity candidates beyond the 30 included; if\
    \ a true duplicate exists, it would be in that omitted set, requiring a second\
    \ screening pass with different selection criteria.\nLooking at OOMPAH-873 and\
    \ the supplied project task corpus, I'll analyze whether this is a duplicate of\
    \ an existing issue.\n\n**Task Analysis:**\n\nOOMPAH-873 is specifically about:\n\
    - A live regression where native tracker snapshots return stale data\n- GET /api/v1/issues\
    \ full snapshots publish \"Done\" state while detail reads correctly show \"In\
    \ Progress\"\n- Mismatch between issue-list snapshots and fresh state-branch detail\
    \ reads\n- Cache and source-generation issues in the native Markdown tracker's\
    \ fetch_all_issues path\n- WebSocket full-sync payload staleness preventing UI\
    \ convergence\n\n**Corpus Review:**\n\nExamining the 30 supplied similarity candidates:\n\
    - **OOMPAH-10**: Native markdown tracker sync failures (git rebase issues) \u2014\
    \ different problem\n- **OOMPAH-11** through **OOMPAH-192**: All archived/terminal\
    \ state tasks covering various tracker features, GitHub intake, epic workflows,\
    \ release addendums, and documentation\n\n**Status Check:**\n\nAll 30 provided\
    \ similarity candidates are in **Archived** state (terminal). Per the duplicate\
    \ screening rules, terminal tasks cannot be duplicate targets since completed\
    \ work is historical context, not an active duplicate target.\n\n**Conclusion:**\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\n**Evidence:** The supplied corpus of 30 similarity candidates\
    \ are all in terminal/Archived state. None describe the same underlying issue\
    \ as OOMPAH-873 (stale snapshot-vs-detail-read consistency for native tracker\
    \ state). The closest related tasks (OOMPAH-10: native tracker sync, OOMPAH-160:\
    \ atomic task writes) address different root causes. No active duplicate exists\
    \ in the provided corpus. The corpus notes 392 omitted similarity candidates beyond\
    \ the 30 included; if a true duplicate exists, it would be in that omitted set,\
    \ requiring a second screening pass with different selection criteria."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1be8d429-6ceb-4b7f-b928-1b0678cecb43
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2181
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2181
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2181
    cost_usd: 0.0
    recorded_at: '2026-08-07T07:21:21.245354+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-873__20260807T071751Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-873
    source_sha: 45e2b83356dd041200d7cad0970c7e6f939dc757
    completed_at: '2026-08-07T07:21:21.273925+00:00'
---
## Summary

Triggered by: OOMPAH-768

Live regression after OOMPAH-664 and OOMPAH-691 through OOMPAH-695: the canonical state-branch file for OOMPAH-768 is .oompah/tasks/in-progress/OOMPAH-768.md with status In Progress and updated_at 2026-08-07T04:20:57Z, and GET issue detail returns In Progress with tracker_state_fresh=true, but repeated GET /api/v1/issues full snapshots publish tracker_state/state Done and place the task in the Done column. Because the authoritative full-sync payload is itself stale, WebSocket gap detection cannot converge the UI. Reproduce and repair the native tracker fetch_all_issues/snapshot cache/source-generation path so list serialization and detail reads share one exact state-branch authority generation. Relevant code: native Markdown tracker read/cache invalidation and atomic status-file moves, server _ensure_issues_snapshot_refresh/_fetch_and_serialize_issues/source generation checks, full-sync response construction. Required tests: status-file move or lifecycle write followed by fresh detail and forced issue snapshot yields identical state; paused projects still refresh API-mutated tracker state; snapshot generation never advances while serving an older task object; concurrent move/read is atomic; WebSocket full sync contains the same state as detail. Acceptance: every full issue snapshot and full-sync response for a reported source revision exactly matches direct detail reads from that revision, so sequence recovery cannot install stale task columns.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 07:17
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 07:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 07:21
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.2K out [2.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 57s
- Log: OOMPAH-873__20260807T071751Z.jsonl
---
<!-- COMMENTS:END -->
