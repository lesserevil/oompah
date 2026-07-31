---
id: OOMPAH-664
type: task
status: In Progress
priority: null
title: Make issue-list snapshots advance with canonical state-branch task changes
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T16:04:06.140108Z'
updated_at: '2026-07-31T18:33:38.126211Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: cb124d284cc953ce215037f31063daa984016881cbf20dd585b575b67d4cd2a9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T18:16:36.825754+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-305 and OOMPAH-306 are the closest matches, but both are Archived
    terminal tasks. Active OOMPAH-651 and OOMPAH-665 cover unrelated security and
    audit-alert issues. No active duplicate exists.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 87dfad04-582f-46f6-93ca-0ea8552ab073
oompah.task_costs:
  total_input_tokens: 1952826
  total_output_tokens: 7746
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1952826
      output_tokens: 7746
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1952826
    output_tokens: 7746
    cost_usd: 0.0
    recorded_at: '2026-07-31T18:16:36.824552+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-664__20260731T181337Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-664
    source_sha: a1dd3287d1faeeccf777c57764b9283cb653304d
    completed_at: '2026-07-31T18:16:36.837903+00:00'
---
## Summary

Live reproduction on 2026-07-31: the canonical native tracker contained OOMPAH-651 and OOMPAH-655 in Needs Human, and task detail plus task CLI reported those states, while GET /api/v1/issues?project_id=proj-14849f1b returned an empty Needs Human set. This caused an operator recovery pass to miss two authoritative tasks until the state-branch files were inspected directly. Prior OOMPAH-305/306 cache work did not prevent this recurrence. Implementation scope: bind every list/board snapshot to the exact project state-branch generation or commit, invalidate it synchronously after checkpoint and direct status mutations, and ensure list, detail, task CLI, websocket, and canonical Markdown agree. Never silently serve a stale empty lane as fresh; expose the existing stale indicator when a fresh authoritative read is unavailable. Relevant files include oompah/server.py issue snapshot/detail caches, state-branch checkpoint callbacks in oompah/oompah_md_tracker.py, websocket broadcasts, and state-cache regression tests. Required deterministic tests: barrier between a cached list read and Needs Human status moves from a separate tracker instance; checkpoint commit invalidation; two projects isolated; list/detail parity; restart; read failure preserves a stale-marked snapshot rather than claiming an empty current lane. Acceptance: an authoritative status move becomes visible in all read surfaces without TTL delay, OOMPAH-651/655-style tasks cannot disappear from lane queries, and focused plus full Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 18:13
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 18:13
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 18:16
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 24
- Tokens: 2.0M in / 7.7K out [2.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 3s
- Log: OOMPAH-664__20260731T181337Z.jsonl
---
author: oompah
created: 2026-07-31 18:16
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 18:17
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 18:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 93
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 24s
- Log: OOMPAH-664__20260731T181701Z.jsonl
---
author: oompah
created: 2026-07-31 18:33
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-31 18:33
---
Focus: Event Api Redaction Specialist
---
<!-- COMMENTS:END -->
