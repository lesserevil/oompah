---
id: OOMPAH-791
type: feature
status: In Progress
priority: 1
title: Cut epic and nested-epic rollup over to LandingFact-driven jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:17.853130Z'
updated_at: '2026-08-04T20:30:12.378133Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-791
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: fb3aa3abc582ec1af953ebc1e286b3a58b83eabb84d54e02ce3789f58c3182cb
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:25:44.417468+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Duplicate preflight verdict: no_duplicate\nMatches: none\n\
    Acknowledged. OOMPAH-793 (implementation/ownership domain) has been submitted\
    \ at ef5e8c30e. This is a sibling task to OOMPAH-791 under the OOMPAH-768 epic\
    \ and does not affect my duplicate screening conclusion.\n\nMy duplicate screening\
    \ for **OOMPAH-791** is **complete**. The verdict stands:\n\n**Focus handoff:\
    \ duplicate_detector**  \n**Duplicate preflight verdict: no_duplicate**  \n**Matches:\
    \ none**\n\nOOMPAH-791 is a unique, non-duplicate feature task for migrating the\
    \ epic rollup domain to LandingFact-driven jobs.\n\n---\n\nI am exiting duplicate-screening\
    \ mode now per the reserved boundary. This was a read-only qualification run;\
    \ I have not modified the repository, tracker state, or branch. The screening\
    \ result is ready for oompah's integration verification."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 822dba52-2fd5-4853-a32c-633c8f9469ed
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-791
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-791
  base_branch: epic-OOMPAH-768
  base_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
  updated_at: '2026-08-04T20:30:07.942135+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 556
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 556
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 556
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:25:44.402970+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-791__20260804T202331Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-791
    source_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
    completed_at: '2026-08-04T20:25:44.437531+00:00'
---
## Summary

Migrate epic readiness, child landing verification, rollup review creation, nested target resolution, auto-close, terminal validation, rebase/repair, cleanup, and restart reconciliation to shared facts/decisions/jobs. Enforce acyclic containment; require normal child Done plus landing proof and nested epic landing on immediate parent; never make child eligibility depend on a parent status derived from that child. Preserve patch-equivalence and durable evidence after source pruning. Required real-Git scenarios: multi-level nested epics, parent open to main while child landed to parent, deleted refs, rebase, direct maintenance, new/reopened child during review creation, and OOMPAH-731/739/748. Acceptance: no parent-child proof cycle, all epic consumers share target/landing facts, and rollups converge without manual status overrides.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:23
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 20:23
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:25
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 4, Tool calls: 0
- Tokens: 10 in / 556 out [566 total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 32s
- Log: OOMPAH-791__20260804T202331Z.jsonl
---
author: oompah
created: 2026-08-04 20:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 20:30
---
Focus: Refactoring Specialist
---
<!-- COMMENTS:END -->
