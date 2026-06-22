---
id: OOMPAH-21
type: task
status: In Progress
priority: 2
title: Add the release/1.0 branch cut checklist
parent: OOMPAH-17
children: []
blocked_by:
- OOMPAH-19
labels: []
assignee: null
created_at: '2026-06-22T01:16:34.236540Z'
updated_at: '2026-06-22T02:34:38.853040Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d1bbaf33-295b-4e79-a2f2-cb6cae070010
oompah.task_costs:
  total_input_tokens: 4172004
  total_output_tokens: 28370
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 4172004
      output_tokens: 28370
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 1979968
    output_tokens: 16496
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:20:06.216681+00:00'
  - profile: standard
    model: unknown
    input_tokens: 2192036
    output_tokens: 11874
    cost_usd: 0.0
    recorded_at: '2026-06-22T02:27:52.427725+00:00'
---
## Summary

Plan: plans/oompah-1.0-release.md#release-readiness-checklist

WHAT TO DO
Add a release/1.0 branch cut checklist that maintainers can follow before creating v1.0.0-draft.

THE CHECKLIST MUST COVER
- confirming main is clean
- cutting release/1.0
- setting package version to 1.0.0
- running quality gates
- creating or force-moving v1.0.0-draft
- verifying draft artifacts
- preserving immutable final tag semantics

HOW TO VERIFY
A maintainer can follow the checklist without needing hidden context from this task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:11
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 02:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:20
---
Agent completed successfully in 503s (1996464 tokens)
---
author: oompah
created: 2026-06-22 02:20
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 37
- Tokens: 2.0M in / 16.5K out [2.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 23s
- Log: OOMPAH-21__20260622T021151Z.jsonl
---
author: oompah
created: 2026-06-22 02:20
---
Agent completed without closing this issue (503s (1996464 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-06-22 02:20
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-06-22 02:20
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:21
---
Understanding: I will first check for duplicate release-branch checklist tasks, then update the 1.0 release plan with a self-contained branch-cut checklist covering main cleanliness, release/1.0 creation, versioning, quality gates, draft tag movement, artifact verification, and final tag immutability.
---
author: oompah
created: 2026-06-22 02:23
---
Discovery: Not a duplicate. OOMPAH-18 updated 1.0 examples, OOMPAH-19 handled draft-tag validation, OOMPAH-38/OOMPAH-39/OOMPAH-41 are release execution tasks, and OOMPAH-17 is the parent epic. OOMPAH-21 is the distinct checklist documentation/test task. Prior local edits already add the checklist in docs/cli-release.md and plans/oompah-1.0-release.md with coverage in tests/test_cli_release_packaging.py; I am reviewing and verifying those now.
---
author: oompah
created: 2026-06-22 02:27
---
Agent completed successfully in 442s (2203910 tokens)
---
author: oompah
created: 2026-06-22 02:27
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 36
- Tokens: 2.2M in / 11.9K out [2.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 22s
- Log: OOMPAH-21__20260622T022034Z.jsonl
---
author: oompah
created: 2026-06-22 02:27
---
Agent completed without closing this issue (442s (2203910 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-06-22 02:28
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-06-22 02:28
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:30
---
Verification: All 7056 tests pass (28 skipped). The new tests test_release_docs_include_branch_cut_checklist and test_release_plan_includes_self_contained_branch_cut_checklist both pass, confirming the checklist content is present and correct in both docs/cli-release.md and plans/oompah-1.0-release.md.
---
author: oompah
created: 2026-06-22 02:34
---
Completion: Added the release/1.0 branch cut checklist. Changes pushed to epic-OOMPAH-17:

1. plans/oompah-1.0-release.md — Replaced the placeholder bullet list under '## Release Readiness Checklist' with a self-contained 7-step numbered checklist covering: (1) confirming main is clean, (2) cutting release/1.0, (3) setting version to 1.0.0, (4) running quality gates, (5) creating/force-moving v1.0.0-draft, (6) verifying draft artifacts, (7) preserving final tag immutability.

2. docs/cli-release.md — Added 'Cut the release branch' section (pre-flight steps 1-4) and expanded 'Create a draft release' with artifact verification and final-tag immutability note.

3. tests/test_cli_release_packaging.py — Added test_release_docs_include_branch_cut_checklist and test_release_plan_includes_self_contained_branch_cut_checklist to verify required content is present.

All 7056 tests pass. The checklist is self-contained — a maintainer can follow it without any hidden context from this task.
---
<!-- COMMENTS:END -->
