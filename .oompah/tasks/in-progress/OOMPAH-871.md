---
id: OOMPAH-871
type: bug
status: In Progress
priority: 1
title: Prevent provenance-only terminal tasks from watchdog reopen and redispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T05:24:14.554398Z'
updated_at: '2026-08-07T07:29:55.180670Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d5315e2b5150ac71c464336b3c712f7ea42c50006472f8171c1b4fe8b0d3179d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T07:20:47.816766+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-871 is a novel follow-up bug triggered by OOMPAH-576\
    \ (post-merge) that requires new architectural changes to persist \"provenance-only\"\
    \ state and prevent watchdog from redispatching terminal tasks. The closest archived\
    \ tasks (OOMPAH-160, OOMPAH-212, OOMPAH-219) address related domains (atomic writes,\
    \ duplicate records, commit races) but do not cover provenance-only suppression\
    \ or watchdog reopen prevention. No active task in the corpus describes this problem.\n\
    Looking at OOMPAH-871 and the supplied task corpus, I need to determine whether\
    \ this is a duplicate of an existing active task.\n\n**Issue Summary:**\nOOMPAH-871\
    \ describes a bug where a task retained solely as terminal provenance (after being\
    \ merged) is later reopened and redispatched by the watchdog. The fix requires\
    \ defining and persisting an authoritative \"provenance-only\" or \"terminal-suppression\"\
    \ state that watchdog, reconciliation, dependency rollup, and restart recovery\
    \ all honor.\n\n**Corpus Analysis:**\nI've reviewed all 33 included similarity\
    \ candidates plus the current task. Examining the closest topically-related archived\
    \ tasks:\n\n1. **OOMPAH-160** (Archived) - \"Make native task writes atomic and\
    \ block intake reimports for corrupt tasks\" - Focuses on atomic writes and preventing\
    \ duplicate task reimports due to corruption, not on provenance-only state or\
    \ watchdog reopen prevention.\n\n2. **OOMPAH-212** (Archived) - \"Prevent duplicate\
    \ native task records from appearing on the board\" - Addresses duplicate task\
    \ records in the board view, not watchdog reopening of provenance-only tasks.\n\
    \n3. **OOMPAH-219** (Archived) - \"Detect shared-worktree commits that absorb\
    \ another task's changes\" - Handles shared worktree commit races and stale incomplete-session\
    \ state, not provenance-only suppression.\n\nAll remaining tasks in the corpus\
    \ are unrelated (epic strategies, release addendums, docs, etc.).\n\n**Key Distinction:**\n\
    OOMPAH-871 is explicitly triggered by OOMPAH-576 (mentioned in the description),\
    \ implying 576 was already completed. This is a follow-up bug discovered after\
    \ that implementation merged\u2014not a re-filing of the same issue. The problem\
    \ is specifically about **preventing watchdog from reopening tasks retained only\
    \ as provenance**, which requires new state-persistence and dispatch-eligibility\
    \ logic not covered by any existing task.\n\n---\n\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-871\
    \ is a novel follow-u"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 1e76ca5f-6357-400c-9205-713f0357030f
oompah.task_costs:
  total_input_tokens: 40
  total_output_tokens: 1745
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 40
      output_tokens: 1745
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1736
    cost_usd: 0.0
    recorded_at: '2026-08-07T07:20:47.801719+00:00'
  - profile: default
    model: haiku
    input_tokens: 30
    output_tokens: 9
    cost_usd: 0.0
    recorded_at: '2026-08-07T07:29:19.336540+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-871__20260807T071552Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-871
    source_sha: 45e2b83356dd041200d7cad0970c7e6f939dc757
    completed_at: '2026-08-07T07:20:47.824750+00:00'
---
## Summary

Triggered by: OOMPAH-576

Reproduce OOMPAH-576 after its original implementation merged and an operator explicitly retained the record only as terminal provenance. A watchdog later reopened and redispatched the task, causing a new documentation-only accepted head and another full validation/review cycle. Define and persist an authoritative provenance-only or terminal-suppression state that every watchdog, reconciliation path, dependency rollup, and restart recovery honors. Relevant code: watchdog task reconciliation, terminal-state evidence, archived/provenance metadata, dispatch eligibility, restart recovery. Required tests: terminal provenance records remain non-dispatchable across repeated watchdog ticks and service restart; legitimate owner-requested revision creates a new authority generation and can dispatch; stale branch or historical review observations cannot reopen the record; alerts explain malformed provenance metadata without mutating status. Acceptance: a task retained solely as merged/archived provenance cannot re-enter a dispatchable or validation state unless a project owner explicitly starts a new revision.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 07:15
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 07:15
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 07:20
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.7K out [1.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 40s
- Log: OOMPAH-871__20260807T071552Z.jsonl
---
author: oompah
created: 2026-08-07 07:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 07:25
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 07:29
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 1
- Tokens: 30 in / 9 out [39 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 38s
- Log: OOMPAH-871__20260807T072559Z.jsonl
---
<!-- COMMENTS:END -->
