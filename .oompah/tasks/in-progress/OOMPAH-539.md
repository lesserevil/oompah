---
id: OOMPAH-539
type: task
status: In Progress
priority: null
title: Keep Open-task duplicate-screening board state synchronized with live workers
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T00:43:25.964028Z'
updated_at: '2026-07-29T02:14:12.630348Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7ec666279170df02c313e16207813bf4b9b572e4924eef4bcfaada25dfd17744
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:14:02.259466+00:00'
  matched_identifiers: []
  evidence: "I've completed a thorough search across all active tasks and the full\
    \ task archive. Here's my assessment:\n\n**Active (non-terminal) tasks reviewed:**\n\
    - **OOMPAH-281** (Open): Containerized self-hosted GitHub Actions runner \u2014\
    \ unrelated\n- **OOMPAH-282** (Backlog): UnicodeEncodeError in state_branch_migration\
    \ \u2014 unrelated\n\n**Search terms checked across all `.oompah/tasks`, `plans/`,\
    \ `docs/`, `README.md`:**\n- `duplicate_screening`, `duplicate_preflight`, `preflight`,\
    \ `screening`\n- `board.*state`, `state.*sync`, `stale.*snapshot`, `snapshot.*stale`\n\
    - `issue.*board`, `board.*sync`, `refresh.*issue`\n- `work_kind`, `WebSocket`,\
    \ `broadcast.*issue`\n- `unchecked`, `no_duplicate`, `duplicate_candidate`\n-\
    \ `live.*worker`, `worker.*state`\n\n**All returned zero matches.** All 200+ archived\
    \ and merged tasks are in terminal states (Archived/Merged) and are excluded as\
    \ duplicate targets per the investigation rules.\n\nOOMPAH-539 describes a novel\
    \ bug: the `/api/v1/issues` board snapshot presenting stale `duplicate_screening.state`\
    \ (showing `unchecked` while a live preflight worker is running, or showing `running`\
    \ after the worker has completed), requiring snapshot invalidation and refresh\
    \ tied to duplicate-preflight claim lifecycle events. This is a first-of-its-kind\
    \ synchronization bug with no active duplicate.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: A comprehensive\
    \ search across all non-terminal tasks (OOMPAH-281 \u2014 GitHub Actions runner;\
    \ OOMPAH-282 \u2014 UnicodeEncodeError migration bug) and across all archived/merged\
    \ task bodies found zero matches for any of the key concepts in OOMPAH-539: duplicate\
    \ screening state synchronization, board snapshot staleness, duplicate_preflight\
    \ claim lifecycle, issue payload refresh, or WebSocket broadcast of screening\
    \ state. The issue describes a unique production race condition between the live\
    \ `/api/v1/state` worker view and the cached `/api/v1/issues` board snapshot during\
    \ duplicate scr"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: d1a8f463-984a-47d1-84c4-749087137b34
oompah.task_costs:
  total_input_tokens: 12
  total_output_tokens: 2833
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 12
      output_tokens: 2833
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 12
    output_tokens: 2833
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:14:02.259014+00:00'
---
## Summary

Production observation on 2026-07-29 while OOMPAH-538 was being screened. The live /api/v1/state payload correctly reported OOMPAH-538 with work_kind=duplicate_screening and duplicate_preflight=true, but /api/v1/issues continued to serialize the same Open task as duplicate_screening.state=unchecked for roughly the active run. Near completion the inverse occurred: the board snapshot reported running after the live worker had exited and the canonical state-branch record already contained a checked no_duplicate verdict. This makes operators believe no Open tasks are being screened.\n\nImplementation scope:\n- Invalidate and refresh the issue-board snapshot when a duplicate-preflight claim is acquired, renewed/released, or completed.\n- Broadcast the refreshed canonical issue data after the tracker mutation, while retaining the separate live running-agent chip.\n- Preserve the task's Open column placement and do not optimistically mark preflight as In Progress.\n- Avoid a stale payload-before-refresh ordering that can overwrite a newer screening badge.\n\nRequired tests:\n- Claim acquisition changes an Open card from unchecked to running promptly in the issues payload/WebSocket update.\n- Completion changes running to checked (or duplicate candidate/retry) promptly and cannot regress to an older snapshot.\n- Worker state and issue summary agree through start, renewal, completion, and failure races.\n- Normal implementation optimistic movement remains unchanged. Run focused dashboard/server snapshot tests and make test.\n\nAcceptance criteria:\nDuring a live Open-task preflight, both the running-agent chip and the Open card/detail panel show screening; after exit, all surfaces show the final canonical verdict within the normal UI refresh window; no stale update can reverse the displayed lifecycle; and the task never appears In Progress solely because of screening.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:12
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-07-29 02:12
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:14
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 25, Tool calls: 18
- Tokens: 12 in / 2.8K out [2.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 5s
- Log: OOMPAH-539__20260729T021301Z.jsonl
---
author: oompah
created: 2026-07-29 02:14
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 02:14
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
