---
id: OOMPAH-618
type: bug
status: In Progress
priority: 1
title: Keep ACP shell commands off the scheduler event loop
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T21:03:01.411786Z'
updated_at: '2026-07-30T21:04:33.600646Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: fix the live scheduler stall reproduced while the OOMPAH-616 completion auditor ran a long test command. The Claude/OpenCode and Codex ACP run_command tools are async wrappers but currently invoke api_agent._exec_run_command synchronously on the orchestrator event-loop thread. Offload every subprocess-backed run_command execution to a worker thread while preserving direct in-process oompah task command routing, authority checks, timeouts, output formatting, and auditor read-only rules. Relevant file: oompah/acp_tools.py and ACP catalog tests. Tests: deterministically capture the thread identity used by each distinct ACP run_command implementation and assert the subprocess helper never runs on the event-loop thread; cover Claude/OpenCode shared catalog and Codex catalog, normal output, direct task command interception, and timeout behavior. Run focused ACP tests and Oompah's full combined-tree gate. Acceptance criteria: a long agent or auditor shell command does not stop scheduler refresh, integration completion, audit dispatch, or API-state updates; all three catalog builders retain compatible results; tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 21:04
---
Claimed for direct operator implementation. This child fixes the event-loop stall observed during the OOMPAH-616 audit; implementation, regression tests, branch integration, and audit handoff will be completed here.
---
<!-- COMMENTS:END -->
