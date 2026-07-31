---
id: OOMPAH-658
type: bug
status: In Progress
priority: 2
title: Deduplicate duplicate-preflight runs across deferred dispatch ticks
parent: null
children: []
blocked_by:
- OOMPAH-657
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T11:19:01.632127Z'
updated_at: '2026-07-31T11:25:29.734672Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4a1bb0e26842985230ec626f23ddef4727bf4b92c77c3423b2df84e9e0e9abb1
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T11:21:27.879571+00:00'
  matched_identifiers: []
  evidence: "No implementation or tracker mutation performed.\n\nFocus handoff: duplicate_detector\
    \  \nDuplicate preflight verdict: no_duplicate  \nMatches: none  \nEvidence: Active\
    \ OOMPAH-655 and OOMPAH-657 address service isolation and immutable gate snapshots,\
    \ not duplicate-preflight deduplication. Historical OOMPAH-529\u2013532, OOMPAH-535,\
    \ and OOMPAH-540 are terminal and therefore excluded as duplicate targets; they\
    \ cover prerequisite evidence, claims, scheduling, lifecycle recovery, and dependency\
    \ bypass\u2014not this deferred-tick regression."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: e4544404-5ab9-418b-875b-6ffe44dc9d65
oompah.task_costs:
  total_input_tokens: 928198
  total_output_tokens: 4930
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 928198
      output_tokens: 4930
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 928198
    output_tokens: 4930
    cost_usd: 0.0
    recorded_at: '2026-07-31T11:21:27.878524+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-658__20260731T111938Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-658
    source_sha: 54dd2509c6cbc73aaadbda2a3fdc7cfbb14530eb
    completed_at: '2026-07-31T11:21:27.888975+00:00'
---
## Summary

Triggered by: OOMPAH-655

Live scheduler reproduction on OOMPAH-655: after one unchanged Open transition, duplicate screening ran at 11:09-11:11 (comments 36-38), then ran again at 11:13-11:15 (comments 39-41) before the implementation agent dispatched. No task status, description, branch head, dependency, or duplicate-screening input changed between runs. This wastes provider capacity and can starve implementation while a finish-order dependency delays dispatch. Implementation scope: persist or retain duplicate-preflight completion keyed to the exact task intake/evidence revision, treat a completed normal/no-duplicate result as satisfied across scheduler ticks and dependency waits, invalidate it only when relevant title/description/source/parent/revision inputs change, and keep concurrent ticks single-flight. Relevant code includes duplicate-preflight focus/dispatch selection, claimed/completed state recovery, retry handling, and task metadata. Add deterministic multi-tick and restart tests with an Open task held behind an unfinished finish-order dependency; prove exactly one screening launches for an unchanged revision, implementation dispatch follows when eligible, changed intake triggers exactly one new screen, failures retry according to policy, and project/task isolation holds. Acceptance: unchanged Open work cannot launch duplicate investigators repeatedly; no valid rescreen is suppressed; focused scheduler tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 11:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 11:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 11:19
---
Finish-order dependency on OOMPAH-657: implement in parallel, but final gate/review must use the immutable exact-head lifecycle.
---
author: oompah
created: 2026-07-31 11:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 15s
- Log: OOMPAH-658__20260731T111912Z.jsonl
---
author: oompah
created: 2026-07-31 11:19
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 11:19
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 11:21
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 14
- Tokens: 928.2K in / 4.9K out [933.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 56s
- Log: OOMPAH-658__20260731T111938Z.jsonl
---
author: oompah
created: 2026-07-31 11:21
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 11:21
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-31 11:21
---
## Understanding

The issue is that duplicate-preflight (duplicate screening) runs are being dispatched multiple times across scheduler ticks when the task intake/evidence hasn't changed. For example, it ran twice (11:09-11:11 and 11:13-11:15) with no input changes, wasting provider capacity.

**Root Cause:** Duplicate-preflight completion/result is not being persisted and retained across scheduler ticks. Each tick re-evaluates whether to dispatch duplicate screening, even though the previous run already completed with a no-duplicate result.

**Solution Approach:**
1. Investigate how duplicate-preflight dispatch selection works in the scheduler
2. Find where completed duplicate-preflight results are handled (claimed/completed state recovery)
3. Implement caching/persistence of duplicate-preflight completion keyed to task intake/evidence revision
4. Invalidate cache only when relevant inputs (title/description/source/parent/revision) change
5. Add tests to verify exactly one screening launches for unchanged revision across ticks
6. Ensure implementation dispatch follows correctly when eligible

**Next Steps:**
- Locate duplicate-preflight focus/dispatch logic
- Trace scheduler tick and dependency wait flow
- Examine task metadata and claimed/completed state handling

Starting exploration of the codebase.
---
author: oompah
created: 2026-07-31 11:25
---
## Discovery

Found the duplicate-preflight logic chain:
1. \`_select_duplicate_preflight_candidates\` loops through candidates fetched via \`fetch_candidate_issues()\`
2. For each candidate, calls \`_duplicate_screening_assessment(issue)\` which calls \`assess_screening(issue)\`
3. \`assess_screening\` checks the issue's \`duplicate_screening\` metadata to determine if screening was already done
4. If CHECKED state found, task is skipped; otherwise, selected for screening
5. When screening completes, \`_finish_duplicate_preflight_sync\` saves a CHECKED record via \`save_duplicate_screening_record\`

**Suspected Root Cause:**
The metadata is stored in the issue description (embedded in a hidden comment block). When \`fetch_candidate_issues()\` fetches issues for selection, the description metadata might not be fully loaded if GitLab's list API returns truncated descriptions. This causes \`assess_screening\` to not find the existing CHECKED record and incorrectly returns UNCHECKED, triggering re-dispatch of duplicate screening.

**Solution:**
Ensure the \`duplicate_screening\` metadata from a completed screening is retained/cached at the task/fingerprint level so that subsequent scheduler ticks recognize it as satisfied, or explicitly reload metadata before assessment if needed.

Next: Verify this hypothesis by checking if descriptions are fully loaded in list responses.
---
<!-- COMMENTS:END -->
