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
updated_at: '2026-07-29T18:57:28.345283Z'
work_branch: epic-OOMPAH-460--task-OOMPAH-487
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
oompah.agent_run_id: 233a6da2-e5ae-4865-bf79-b2b14f99c25d
oompah.work_branch: epic-OOMPAH-460--task-OOMPAH-487
oompah.task_costs:
  total_input_tokens: 73425
  total_output_tokens: 6715
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 73425
      output_tokens: 6715
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 186
    output_tokens: 5823
    cost_usd: 0.0
    recorded_at: '2026-07-29T02:09:31.868575+00:00'
  - profile: default
    model: haiku
    input_tokens: 73239
    output_tokens: 892
    cost_usd: 0.0
    recorded_at: '2026-07-29T18:29:32.304640+00:00'
oompah.integration:
  version: 1
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-460--task-OOMPAH-487
  base_branch: epic-OOMPAH-460
  base_sha: b0ceda2643cbc37c166ac58bed9a9b6f3898b681
  updated_at: '2026-07-29T18:29:53.129296+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-487__20260729T182909Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: docs
    source_branch: epic-OOMPAH-460--task-OOMPAH-487
    source_sha: b0ceda2643cbc37c166ac58bed9a9b6f3898b681
    completed_at: '2026-07-29T18:29:32.309634+00:00'
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
author: oompah
created: 2026-07-29 18:29
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-29 18:29
---
Agent completed successfully in 42s (74131 tokens)
---
author: oompah
created: 2026-07-29 18:29
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 1
- Tokens: 73.2K in / 892 out [74.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 42s
- Log: OOMPAH-487__20260729T182909Z.jsonl
---
author: oompah
created: 2026-07-29 18:29
---
Agent completed without closing this issue (42s (74131 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-29 18:29
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-29 18:29
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-29 18:30
---
Understanding: This is a continuation run (attempt #1). Previous agent ran but didn't close the issue. I'll explore what was done, find gaps, and complete all acceptance criteria:
1. Add OOMPAH_AUDIT_MAX_ATTEMPTS to .env.example and ServiceConfig
2. Document auditor role, independence rules, project whitelist, audits, In Validation, failure routing, owner override, no-candidate recovery, upgrade grandfathering, restart behavior
3. Deprecate OOMPAH_VERIFY_COMPLETION and OOMPAH_VERIFY_COMPLETION_LLM with startup warnings and release note migration
4. Add config/env parsing tests, deprecation-warning tests, doc link/content checks
Starting with codebase exploration.
---
author: oompah
created: 2026-07-29 18:37
---
Discovery: The epic branch is at origin/epic-OOMPAH-460 (before OOMPAH-459/483/486 implementation is merged). I can see from main branch:
1. oompah/auditor.py, oompah/auditor_candidate_selector.py, oompah/auditor_dispatch.py exist in main
2. ServiceConfig.audit_max_attempts (int=3) parsed via OOMPAH_AUDIT_MAX_ATTEMPTS - NOT yet on epic branch
3. docs/auditor-dispatch-operations.md exists in main but NOT on epic branch
4. OOMPAH_VERIFY_COMPLETION/OOMPAH_VERIFY_COMPLETION_LLM still exist without deprecation warnings
5. task-epic-workflow.md does not include 'In Validation' status in lifecycle
6. No tests for audit_max_attempts config parsing or deprecation warnings

Implementation plan:
- Add OOMPAH_AUDIT_MAX_ATTEMPTS (+ related audit settings) to .env.example and ServiceConfig
- Create docs/auditor-dispatch-operations.md with full lifecycle docs and Mermaid diagram
- Update docs/task-epic-workflow.md to include In Validation status
- Add deprecation logging for OOMPAH_VERIFY_COMPLETION / OOMPAH_VERIFY_COMPLETION_LLM
- Add tests: config parsing, deprecation warnings, doc content checks
---
author: oompah
created: 2026-07-29 18:57
---
Implementation complete. Changes made:

1. **oompah/config.py**: Added audit_max_attempts, audit_attempt_ttl, audit_priority, audit_lane_scan_limit fields to ServiceConfig, with env var parsing (OOMPAH_AUDIT_MAX_ATTEMPTS etc.). Added warn_deprecated_verify_completion_vars() function that emits startup warnings when OOMPAH_VERIFY_COMPLETION or OOMPAH_VERIFY_COMPLETION_LLM are set. Called from from_workflow(). Added DEPRECATED comments to verify_completion/verify_completion_llm fields.

2. **.env.example**: Added independent completion-auditor dispatch section with OOMPAH_AUDIT_MAX_ATTEMPTS, OOMPAH_AUDIT_ATTEMPT_TTL, OOMPAH_AUDIT_PRIORITY, OOMPAH_AUDIT_LANE_SCAN_LIMIT. Updated OOMPAH_VERIFY_COMPLETION/LLM entries with DEPRECATED notices.

3. **docs/auditor-dispatch-operations.md**: New operator guide covering auditor role, independence rules, lifecycle Mermaid diagram, target-specific audit chains, failure routing table, configuration examples, owner override API, upgrade grandfathering, restart recovery, migration from completion verifier.

4. **docs/task-epic-workflow.md**: Updated status lifecycle table and flowchart to include 'In Validation' status with auditor verdict paths.

5. **docs/operator-runbook.md**: Added .oompah/roles.json to key files table; added Migration Notes section (§10.1) with deprecation migration steps.

6. **tests/test_config.py**: Added TestAuditDispatchConfiguration class with 19 tests covering config parsing, env var overrides, env.example coverage, doc existence/content checks, deprecation warnings, and task-epic-workflow doc content.
---
<!-- COMMENTS:END -->
