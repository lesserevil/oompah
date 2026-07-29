---
id: OOMPAH-473
type: feature
status: In Progress
priority: 1
title: Collect safe-retirement evidence for Archived audits
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-471
- OOMPAH-472
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:13.914904Z'
updated_at: '2026-07-29T06:34:10.105123Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 93f7062d478aebea3d6ead2993ecfb71bce8583d8d9e75ff7663c7820ddec830
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T01:23:23.670816+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: OOMPAH-471 and OOMPAH-472 cover Done and Merged collectors; OOMPAH-481
    wires archive producers; OOMPAH-488 tests the lifecycle. None implement ArchivedEvidenceCollector.
    OOMPAH-457 is terminal (Merged) and excluded.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 8acf12d9-bf3a-4925-a3b2-82b45307a62f
oompah.work_branch: epic-OOMPAH-458
oompah.task_costs:
  total_input_tokens: 1000782
  total_output_tokens: 5061
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1000782
      output_tokens: 5061
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1000782
    output_tokens: 5061
    cost_usd: 0.0
    recorded_at: '2026-07-29T01:23:23.669961+00:00'
---
## Summary

Implementation scope

Build a read-only ArchivedEvidenceCollector. Record the pre-archive status and verify its current Done/Merged audit when applicable, configured retention/disposition reason, no active worker/claim/retry, no open review, no active child or unresolved dependency, and no requirements/evidence-changing activity after the prior audit. For direct archive dispositions such as duplicate or obsolete work, require a structured reason and referenced replacement/source evidence rather than inventing a completion audit. Return the exact unsafe condition and recommended restoration state.

Tests

Cover retention-qualified Done/Merged items, recent items, active worker/retry/review, active child, unresolved dependency, changed requirements, changed branch SHA, duplicate with/without source link, obsolete reason, and safe restoration state. Run focused tests and make test.

Acceptance criteria

Automatic archive passes only when retirement is safe and justified; archival never hides active, changed, or unresolved work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 01:21
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 01:21
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 01:23
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 15
- Tokens: 1.0M in / 5.1K out [1.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 15s
- Log: OOMPAH-473__20260729T012115Z.jsonl
---
author: oompah
created: 2026-07-29 06:34
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 06:34
---
Focus: Maintenance Engineer
---
<!-- COMMENTS:END -->
