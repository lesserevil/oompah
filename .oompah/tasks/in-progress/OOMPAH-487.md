---
id: OOMPAH-487
type: feature
status: In Progress
priority: 1
title: Document auditor configuration, overrides, migration, and recovery
parent: OOMPAH-460
children: []
blocked_by:
- OOMPAH-483
- OOMPAH-486
- OOMPAH-459
labels: []
assignee: null
created_at: '2026-07-28T13:08:26.170630Z'
updated_at: '2026-07-29T18:28:54.077801Z'
work_branch: epic-OOMPAH-460
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: e6e3f14cf037c045da64b0f3e5b5bb7d31ae4e132ba23991152738e863c246a9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-29T02:09:31.869089+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I have completed the duplicate\
    \ detection phase for OOMPAH-487.\n\n## Investigation Summary\n\nI searched extensively\
    \ across:\n- All task states (.oompah/tasks/open, merged, archived)\n- Key terms:\
    \ \"auditor\", \"audit\", \"OOMPAH_AUDIT\", \"OOMPAH_VERIFY_COMPLETION\", \"configuration\"\
    , \"documentation\", \"deprecation\", \"migration\", \"recovery\", \"override\"\
    \n- Task IDs for blocked-by issues (OOMPAH-483, OOMPAH-486, OOMPAH-459)\n- Repository-wide\
    \ searches in README.md, WORKFLOW.md, docs/, and plans/\n- External issue imports\
    \ mapping (found OOMPAH-282 reference from GitHub #459, but file doesn't exist)\n\
    \n## Findings\n\n**Active Tasks:** Only OOMPAH-281 exists as an open task (GitHub\
    \ Actions runner setup \u2014 completely unrelated).\n\n**Related Design Documents:**\
    \ Plans exist for terminal-transition-coordinator and auditor architecture, but\
    \ these are design specs, not duplicate task work.\n\n**Blocked-By Tasks:** The\
    \ three tasks blocking OOMPAH-487 (483, 486, 459) do not yet exist in the tracker.\n\
    \n**Conclusion:** OOMPAH-487 describes documentation and configuration work for\
    \ auditor behavior (configuration parsing, deprecation warnings, recovery procedures,\
    \ etc.) that is **not covered by any existing active task**. This is a fresh,\
    \ unique issue.\n\n---\n\n**Focus handoff: duplicate_detector**\n\n**Duplicate\
    \ preflight verdict: no_duplicate**\n\n**Matches: none**\n\n**Evidence:** Comprehensive\
    \ search of all task states, GitHub imports, and repository content found no existing\
    \ task covering auditor configuration documentation, OOMPAH_VERIFY_COMPLETION\
    \ deprecation, or related configuration/recovery procedures. OOMPAH-281 (only\
    \ open task) concerns GitHub Actions runners. Blocked-by tasks (483, 486, 459)\
    \ do not yet exist. This is a fresh feature request with no active duplicate."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 2eeecd8d-67c6-4744-9ad6-c5841e6eb4cb
oompah.work_branch: epic-OOMPAH-460
oompah.task_costs:
  total_input_tokens: 186
  total_output_tokens: 5823
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 186
      output_tokens: 5823
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 186
    output_tokens: 5823
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:09:31.868575+00:00'
---
## Summary

Implementation scope

Add OOMPAH_AUDIT_MAX_ATTEMPTS to .env.example and ServiceConfig using existing parsing conventions. Document the auditor role, independence rules, project whitelist effects, each target-specific audit, In Validation, failure routing, explicit owner override, no-candidate recovery, upgrade grandfathering, and restart behavior in docs/. Update status/workflow references and CLI help examples. Deprecate OOMPAH_VERIFY_COMPLETION and OOMPAH_VERIFY_COMPLETION_LLM with startup warnings and a release-note migration entry; retain parsing for one compatibility release but do not let them disable mandatory audits. Use Mermaid for any lifecycle diagram.

Tests

Add config/default/env parsing tests, deprecation-warning tests, documentation link/content checks, .env.example coverage, and examples that match actual CLI/API flags. Run focused tests and make test.

Acceptance criteria

A junior operator can configure at least two independent auditor candidates, diagnose Needs Human due to no candidate, execute an owner override, and understand upgrade behavior using only public docs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 02:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-29 02:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-29 02:09
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 61, Tool calls: 35
- Tokens: 186 in / 5.8K out [6.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 24s
- Log: OOMPAH-487__20260729T020810Z.jsonl
---
author: oompah
created: 2026-07-29 18:28
---
Agent dispatched (profile: default)
---
<!-- COMMENTS:END -->
