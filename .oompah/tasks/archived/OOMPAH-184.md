---
id: OOMPAH-184
type: task
status: Archived
priority: 2
title: Document release-addendum workflow and operator migration
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-183
labels: []
assignee: null
created_at: '2026-07-13T02:37:55.470386Z'
updated_at: '2026-07-20T08:27:51.426513Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 18d960f9-4a72-4cdc-b281-fbc4516e1e2e
oompah.task_costs:
  total_input_tokens: 1605187
  total_output_tokens: 10912
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1605187
      output_tokens: 10912
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 1605058
    output_tokens: 7166
    cost_usd: 0.0
    recorded_at: '2026-07-13T06:44:10.173161+00:00'
  - profile: standard
    model: unknown
    input_tokens: 129
    output_tokens: 3746
    cost_usd: 0.0
    recorded_at: '2026-07-13T06:55:05.146960+00:00'
---
## Summary

Read the full plans/release-branch-addendums.md. Update user-facing docs, operator/configuration documentation, project-definition help, API reference, and generated agent guidance to describe the main-first release-addendum workflow: supported release lines, selecting release targets, immediate queueing, per-branch lifecycle, task/epic snapshots, branch inspection, retries, and legacy migration. Remove active instructions that tell users to create or work child backport tasks; retain historical references only when clearly labelled. Use Mermaid for any diagrams. Update documentation tests or add targeted assertions for generated guidance. Acceptance: a junior operator can configure supported lines, approve a merged task for two branches, inspect outcomes, and understand migration without consulting source code.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 06:39
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 06:39
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 06:44
---
Agent completed successfully in 294s (1612224 tokens)
---
author: oompah
created: 2026-07-13 06:44
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 16
- Tokens: 1.6M in / 7.2K out [1.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 54s
- Log: OOMPAH-184__20260713T063920Z.jsonl
---
author: oompah
created: 2026-07-13 06:44
---
Agent completed without closing this issue (294s (1612224 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-13 06:45
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-13 06:45
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 06:49
---
Understanding: This is NOT a duplicate. OOMPAH-185 was previously archived as the duplicate of this task. Confirmed no other duplicate exists.

Scope assessment:
- docs/release-addendums.md: COMPLETE - comprehensive operator guide covering all workflow aspects
- docs/task-epic-workflow.md: COMPLETE - has Release Delivery section
- docs/operator-runbook.md: COMPLETE - has Supported Release Lines paragraph in §1.3
- oompah/agent_instructions.py OOMPAH_TASK block: COMPLETE - has Release Addendums section
- oompah/agent_instructions.py GITHUB_ISSUES block: MISSING - needs Release Addendums section
- docs/managed-project-onboarding.md: MISSING - no release lines step in the checklist
- tests/test_agent_instructions.py: PARTIAL - has test for oompah_task instructions but MISSING test for github_issues instructions describing release addendums
- docs/README.md: COMPLETE - indexes release-addendums.md

Plan: (1) Add Release Addendums section to GITHUB_ISSUES_AGENT_INSTRUCTIONS; (2) Add step to managed-project-onboarding.md; (3) Add test for github_issues instructions; (4) Add assertions for release-addendums.md doc coverage.
---
author: oompah
created: 2026-07-13 06:54
---
Implementation: Added missing pieces to complete the release-addendum documentation suite:

1. oompah/agent_instructions.py: Added '### Release Addendums' section to GITHUB_ISSUES_AGENT_INSTRUCTIONS (it was already in OOMPAH_TASK block). Both generated AGENTS.md variants now explicitly prohibit child backport tasks and link to docs/release-addendums.md.

2. docs/managed-project-onboarding.md: New §4 'Optional: Configure Supported Release Lines' walks an operator through configuring the feature at project setup time. Sections 5-7 renumbered. Updated onboarding flow diagram to include the release-lines step.

3. docs/release-addendums.md (committed, was untracked): Complete user-facing operator guide covering supported release lines configuration, queuing, per-branch lifecycle table, retries, branch inspection, epic snapshots, and legacy migration mapping. Includes Mermaid sequence diagram.

4. tests/test_agent_instructions.py: Two new tests:
   - test_rendered_github_issues_instructions_describe_release_addendums: asserts the GitHub Issues variant also has the Release Addendums section
   - test_release_addendums_doc_covers_operator_workflow: asserts docs/release-addendums.md covers all six lifecycle statuses, retry, inspection, epic snapshots, migration, Mermaid diagrams, and no active child-backport instructions

Also committed the previously-untracked/unstaged docs (docs/README.md index, task-epic-workflow.md release delivery section, operator-runbook.md §1.3, github-issue-intake.md target-branch clarification, projects.html label improvement).

All 7993 tests pass.
---
author: oompah
created: 2026-07-13 06:54
---
Completion: OOMPAH-184 is fully delivered. A junior operator can now:

1. Configure supported release lines: docs/managed-project-onboarding.md §4 (dashboard + PATCH API)
2. Approve a merged task for two branches: docs/release-addendums.md 'Queue a merged task' section (dialog + POST API, Mermaid diagram)
3. Inspect outcomes: docs/release-addendums.md lifecycle table + branch inspection section
4. Understand migration: docs/release-addendums.md 'Migration from release picks' section with status mapping table

Generated agent guidance (both AGENTS.md variants) explicitly prohibits creating/working child backport tasks. Historical migration references are clearly labelled. 2 new targeted documentation tests added. 7993/7993 tests pass.
---
author: oompah
created: 2026-07-13 06:54
---
Documented release-addendum workflow across all operator touchpoints: new docs/release-addendums.md, managed-project-onboarding §4, task-epic-workflow release delivery section, operator-runbook §1.3, Release Addendums section added to GITHUB_ISSUES_AGENT_INSTRUCTIONS, 2 new doc coverage tests. 7993 tests pass.
---
author: oompah
created: 2026-07-13 06:55
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 88
- Tokens: 129 in / 3.7K out [3.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 8s
- Log: OOMPAH-184__20260713T064601Z.jsonl
---
<!-- COMMENTS:END -->
