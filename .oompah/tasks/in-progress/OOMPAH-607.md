---
id: OOMPAH-607
type: bug
status: In Progress
priority: 1
title: Canonicalize project aliases before terminal owner authorization
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T18:17:13.371379Z'
updated_at: '2026-07-30T18:54:07.452055Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ce6d54478b588c0237fd30bee5b1306c50341a853c166cc5852f9b78e4939340
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T18:27:09.068696+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I have searched extensively\
    \ through the task tracking system and codebase to determine whether OOMPAH-607\
    \ is a duplicate of an existing task.\n\n## Investigation Summary\n\n**Searches\
    \ Performed:**\n1. **Direct task file searches** in `.oompah/tasks/{open,merged,archived}`\
    \ for OOMPAH-605 and OOMPAH-606: No matches found\n2. **Keyword searches** for:\
    \ terminal, override, authorization, project alias, canonical project ID, owner\
    \ auth: No matches found\n3. **Function searches** for `_get_tracker_for_issue_or_project`,\
    \ `_project_by_id`, `_stage_terminal_transition`: None exist in the codebase\n\
    4. **Repository-wide search** for \"605\": Found only timestamp references and\
    \ log files, no OOMPAH-605 task reference\n\n**Open Tasks Found:**\n- Only OOMPAH-281\
    \ exists in open state (GitHub Actions runner setup - completely unrelated)\n\n\
    **Related Task Scope:**\n- Searched merged and archived tasks: No tasks address\
    \ project aliases, terminal authorization, or owner override logic\n- All tasks\
    \ are focused on different features and bug categories\n\n**Conclusion:**\nOOMPAH-607\
    \ (Canonicalize project aliases before terminal owner authorization) does not\
    \ match any existing active task in the system. This appears to be a new issue\
    \ that has not previously been tracked as a separate task.\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** Exhaustive search of `.oompah/tasks/` across all states\
    \ (open, merged, archived) found only OOMPAH-281 as an active task\u2014a completely\
    \ unrelated GitHub Actions runner setup task. Keyword searches for terminal/override/authorization/project\
    \ alias yielded no matches. Referenced trigger issue OOMPAH-605 has no corresponding\
    \ task file in the tracking system. The implementation functions mentioned in\
    \ the issue description do not exist in the codebase, indicating this represents\
    \ entirely new work. OOMPAH-607 is a fresh bug report with no duplicate candidate\
    \ in the act"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 85d8a8e7-484e-4493-be3d-9c22b0062aed
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-607__20260730T181838Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-607
    source_sha: b4fa5db81322ae24b90a5c80689d94d1a49a1f30
    completed_at: '2026-07-30T18:27:09.071562+00:00'
  - run_id: OOMPAH-607__20260730T182926Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-607
    source_sha: 213a0321c6bd78a58bffb77abc670365144ca8d1
    completed_at: '2026-07-30T18:51:35.421782+00:00'
  - run_id: OOMPAH-607__20260730T185157Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-sol
    focus: general
    source_branch: OOMPAH-607
    source_sha: 213a0321c6bd78a58bffb77abc670365144ca8d1
    completed_at: '2026-07-30T18:52:32.595100+00:00'
oompah.task_costs:
  total_input_tokens: 14849322
  total_output_tokens: 30831
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 14731954
      output_tokens: 29857
      cost_usd: 0.0
    opus:
      input_tokens: 117368
      output_tokens: 974
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 210
    output_tokens: 6104
    cost_usd: 0.0
    recorded_at: '2026-07-30T18:27:09.067689+00:00'
  - profile: default
    model: haiku
    input_tokens: 14731744
    output_tokens: 23753
    cost_usd: 0.0
    recorded_at: '2026-07-30T18:51:35.418453+00:00'
  - profile: deep
    model: opus
    input_tokens: 117368
    output_tokens: 974
    cost_usd: 0.0
    recorded_at: '2026-07-30T18:52:32.588272+00:00'
---
## Summary

Triggered by: OOMPAH-605

Implementation scope

Fix terminal status requests made with the supported project-name alias (for example `oompah task set-status ... --project oompah`) so the server carries the canonical managed project ID into `_stage_terminal_transition` and owner authorization. Today `_get_tracker_for_issue_or_project` can resolve the tracker through the alias while returning the alias unchanged; `_project_by_id` then returns no project and a valid configured owner receives a misleading HTTP 403. Preserve fail-closed authorization for unknown projects and unauthorized actors. Relevant files include oompah/server.py project/tracker resolution, task CLI project handling, and terminal status interfaces.

Tests

Add regressions showing a configured owner can use an audit override through both project ID and project-name alias; an unauthorized actor and unknown alias still fail closed; ordinary staged terminal requests retain the canonical project ID; error messages do not leak configuration. Run focused server terminal-interface/override/CLI tests and make test.

Acceptance criteria

Project aliases accepted by normal task CLI operations behave identically for terminal owner authorization, no valid owner sees a false 403 solely because an alias was used, and authorization is not weakened.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 18:18
---
Owner-approved liveness follow-up discovered during OOMPAH-605 recovery. Let the oompah server claim and implement this task; direct operator work is not needed while scheduler capacity is healthy.
---
author: oompah
created: 2026-07-30 18:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 18:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 18:27
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 78, Tool calls: 26
- Tokens: 210 in / 6.1K out [6.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 38s
- Log: OOMPAH-607__20260730T181838Z.jsonl
---
author: oompah
created: 2026-07-30 18:28
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 18:28
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 18:51
---
Agent completed successfully in 1390s (14755497 tokens)
---
author: oompah
created: 2026-07-30 18:51
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 47
- Tokens: 14.7M in / 23.8K out [14.8M total]
- Cost: $0.0000
- Exit: normal, Duration: 23m 10s
- Log: OOMPAH-607__20260730T182926Z.jsonl
---
author: oompah
created: 2026-07-30 18:51
---
Agent completed without closing this issue (1390s (14755497 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 18:51
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-30 18:51
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 18:52
---
Agent completed successfully in 37s (118342 tokens)
---
author: oompah
created: 2026-07-30 18:52
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 1
- Tokens: 117.4K in / 974 out [118.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 37s
- Log: OOMPAH-607__20260730T185157Z.jsonl
---
author: oompah
created: 2026-07-30 18:52
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 18:52
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 18:54
---
Understanding: The issue is that terminal status requests (set-status, set-status via label) with project aliases (e.g., 'oompah') don't properly authorize configured owners. When an alias is used, _stage_terminal_transition receives it, and although it calls _canonical_managed_project_id to convert it to a canonical ID, _project_by_id may fail to find the project, resulting in HTTP 403 for valid owners.

Approach: 
1. Examine _get_tracker_for_issue_or_project to confirm it canonicalizes project aliases and returns canonical IDs
2. Check all code paths that call _stage_terminal_transition to ensure canonical IDs are passed
3. Verify the terminal status CLI/API endpoints properly canonicalize before passing to _stage_terminal_transition
4. Add tests to ensure both project IDs and aliases work equally for terminal owner authorization
5. Run focused tests on terminal override and CLI endpoints
---
<!-- COMMENTS:END -->
