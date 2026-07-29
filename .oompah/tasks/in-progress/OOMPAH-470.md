---
id: OOMPAH-470
type: feature
status: In Progress
priority: 1
title: Seed the auditor role and select an independent provider-model candidate
parent: OOMPAH-458
children: []
blocked_by:
- OOMPAH-468
- OOMPAH-457
labels: []
assignee: null
created_at: '2026-07-28T13:06:10.311921Z'
updated_at: '2026-07-29T00:36:17.258538Z'
work_branch: epic-OOMPAH-458
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e2241edb48d51aa19dd51c349cf33ea284834053394f0393dcce2d7d457837e5
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T00:34:34.044036+00:00'
  matched_identifiers: []
  evidence: "Based on my review of the previous comments, the duplicate investigation\
    \ phase for OOMPAH-470 has already been **conclusively completed** on 2026-07-28\
    \ 22:52 with a **no_duplicate** verdict backed by thorough evidence:\n\n- No existing\
    \ auditor role or independent candidate selection implementation found\n- Blocking\
    \ dependencies (OOMPAH-468, OOMPAH-457) are merged and complete  \n- Relevant\
    \ architecture (RoleStore, WorkContributor, ProviderStore) exists but lacks auditor\
    \ implementation\n- No related tasks cover auditor role seeding or contributor\
    \ model exclusion\n\nThe investigation covered all appropriate search vectors\
    \ and confirmed this is fresh feature work ready for implementation.\n\n**Focus\
    \ handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** Thorough search of `.oompah/tasks/` (open,\
    \ backlog, archived, merged), git history, codebase patterns, and design docs\
    \ found no existing work on auditor role creation, independent provider-model\
    \ selection, or contributor model exclusion. RoleStore/Candidate classes exist\
    \ for fast/standard/deep/default roles but lack auditor implementation. OOMPAH-468\
    \ and OOMPAH-457 established prerequisite infrastructure (WorkContributor tracking,\
    \ checkpoint coalescing) but do not implement auditor role logic. This is confirmed\
    \ fresh feature work. Blocking dependencies are complete and unblocking. Implementation\
    \ can proceed.\n\n---\n\nNow handing off to implementation work. The task is ready\
    \ for a developer agent to begin building the auditor role seeding and independent\
    \ candidate selection logic."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
oompah.agent_run_id: bb1311c8-67ba-4084-9cce-f407e9146ad6
oompah.work_branch: epic-OOMPAH-458
oompah.task_costs:
  total_input_tokens: 743
  total_output_tokens: 11561
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 743
      output_tokens: 11561
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 242
    output_tokens: 7564
    cost_usd: 0.0
    recorded_at: '2026-07-28T22:52:40.437093+00:00'
  - profile: default
    model: haiku
    input_tokens: 443
    output_tokens: 686
    cost_usd: 0.0
    recorded_at: '2026-07-28T22:58:26.900302+00:00'
  - profile: default
    model: haiku
    input_tokens: 58
    output_tokens: 3311
    cost_usd: 0.0
    recorded_at: '2026-07-29T00:34:34.043055+00:00'
---
## Summary

Implementation scope

Create a reserved editable auditor role. On migration, seed it from the deduplicated union of deep, standard, and default role candidates, followed by remaining configured provider defaults; do not hardcode local provider IDs. Implement candidate filtering that first respects project provider whitelist, credentials, health, budget, and model validity, then excludes every contributor model. Prefer a provider not used by any contributor. Fall back to a contributing provider only when its candidate has an explicit model ID different from every contributed model on that provider. An SDK-managed unknown model on a contributing provider is not independently provable and must be excluded. Return normalized no-candidate reasons.

Tests

Cover different provider/model, same-provider different model fallback, same model on another provider, multi-contributor epic exclusion, unknown ACP models, round-robin ordering, whitelist, unhealthy/missing credentials, budget, empty role, migration seeding, and no-candidate diagnostics. Run focused tests and make test.

Acceptance criteria

Selected auditors are demonstrably independent under the agreed policy; unsafe or unverifiable candidates are never used; operators can edit auditor candidates through the existing role configuration path.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 22:17
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:17
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 17s
- Log: OOMPAH-470__20260728T221720Z.jsonl
---
author: oompah
created: 2026-07-28 22:50
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:52
---
Focus handoff: duplicate_detector

**Duplicate preflight verdict: no_duplicate**

**Matches: none**

**Evidence:**
Searched `.oompah/tasks/` (open, backlog, archived, merged), git history, codebase patterns, and design docs for related work on:
- auditor role creation/seeding
- independent provider-model candidate selection
- contributor model exclusion
- role candidate filtering by whitelist/credentials/health/budget

Results:
- No existing tasks or implementations of an 'auditor' role candidate selector
- OOMPAH-468 (already merged) established WorkContributor tracking; OOMPAH-457 (already merged) stabilized checkpoint coalescing; neither implement auditor role selection
- Terminal audit infrastructure exists (test_terminal_audit.py, terminal_audit.py) but is separate from provider/model role selection
- RoleStore/Candidate classes (oompah/roles.py) exist for standard roles (fast/standard/deep/default) but lack auditor role or independent-candidate filtering
- No design docs or code for 'exclude contributors', 'prefer independent provider', or 'seed from deduplicated union' logic

**Closest reviewed tasks (all unrelated):**
- OOMPAH-311: detect independently-merged epic children (different concept)
- TASK-407.7: role candidate UI (covers matrix editor, not auditor role logic)
- OOMPAH-468: contributor provenance tracking (prerequisite, not implementation)

**Conclusion:** OOMPAH-470 is a fresh feature. The blocking dependencies (OOMPAH-468, OOMPAH-457) are complete and unblocking work can proceed.
---
author: oompah
created: 2026-07-28 22:52
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 83, Tool calls: 46
- Tokens: 242 in / 7.6K out [7.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 55s
- Log: OOMPAH-470__20260728T225047Z.jsonl
---
author: oompah
created: 2026-07-28 22:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-28 22:53
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 22:54
---
Understanding phase: OOMPAH-470 is confirmed not a duplicate. Blocking dependencies (OOMPAH-468, OOMPAH-457) are merged. Beginning implementation.

The task requires:
1. Create reserved editable auditor role
2. Seed from deduplicated union of deep/standard/default role candidates + configured provider defaults
3. Filter candidates by: whitelist, credentials, health, budget, model validity
4. Exclude contributor models; prefer independent providers
5. Fall back to same-provider different-model only
6. Reject unknown SDK models on contributing providers
7. Return normalized no-candidate diagnostics

Will explore oompah/roles.py (RoleStore/Candidate), WorkContributor tracking (OOMPAH-468), and role configuration patterns.
---
author: oompah
created: 2026-07-28 22:54
---
Discovery: Found relevant architecture:

1. **RoleStore** (oompah/roles.py): Manages roles with multiple candidates + strategy (priority/round_robin). Validation already respects ProviderStore.

2. **WorkContributor** (oompah/work_contributors.py): Tracks provider_id + model_id for each completed run. Can query epic contributors via collect_epic_contributors().

3. **ProviderStore** (oompah/providers.py): Manages ModelProvider instances with health checks, credentials, budget tracking (model_costs), and mode (api/acp).

4. **Provider Health** (oompah/provider_health.py): Tests provider health with normalized error reasons (missing_credentials, auth_failed, etc).

5. **ProjectConfig** (oompah/models.py): Has provider_whitelist field for filtering providers by name.

Key insight: No existing auditor role implementation. Need to:
- Create 'auditor' as reserved editable role
- Seed from deduplicated union of deep/standard/default + configured provider defaults
- Filter by whitelist, credentials, health, budget, validity
- Exclude ALL contributor models; prefer independent providers
- Handle same-provider fallback (different model) safely
- Reject unknown SDK models on contributing providers
- Provide normalized no-candidate diagnostics
---
author: oompah
created: 2026-07-28 22:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 34
- Tokens: 443 in / 686 out [1.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 39s
- Log: OOMPAH-470__20260728T225349Z.jsonl
---
author: oompah
created: 2026-07-29 00:33
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 00:33
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 00:34
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 15, Tool calls: 6
- Tokens: 58 in / 3.3K out [3.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 48s
- Log: OOMPAH-470__20260729T003348Z.jsonl
---
author: oompah
created: 2026-07-29 00:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-29 00:36
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-29 00:36
---
**Understanding:** This issue requires creating a reserved 'auditor' role that selects an independent provider-model candidate. The implementation must:
1. Seed from deduplicated union of deep/standard/default role candidates + configured provider defaults
2. Filter by whitelist, credentials, health, budget, model validity
3. Exclude all contributor models; prefer independent providers
4. Fall back to same-provider different-model only when safe
5. Reject unknown SDK models on contributing providers
6. Return normalized no-candidate diagnostics
7. Support operator editing via existing role configuration paths

**Plan:** Explore oompah/roles.py (RoleStore/Candidate), oompah/work_contributors.py (WorkContributor), oompah/providers.py (ProviderStore), and test patterns to understand the architecture, then implement the auditor role with independent candidate selection logic and comprehensive tests.
---
<!-- COMMENTS:END -->
