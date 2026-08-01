---
id: OOMPAH-681
type: task
status: Open
priority: null
title: Reject interactive Git commands before they can deadlock worker slots
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T17:34:02.400338Z'
updated_at: '2026-08-01T18:58:02.361289Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 48c3a78a1c359a6746a56297c07d572a613f9b5a2e94083e360ffbb30267836c
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: bed8b9d0-39d4-423d-b199-f69fe827a1e3
  claim_owner: cdcf766d-728b-41c9-bcaa-eb3b220f310c
  claimed_at: '2026-08-01T18:57:57.291940+00:00'
  claim_expires_at: '2026-08-01T19:27:57.291940+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: f492f9d4-7517-4016-956b-78c781e82823
---
## Summary

Live regression on 2026-08-01 during graceful restart: EXOCOMP-140 invoked bare `git rebase -i b1a07ccf` through mcp__oompah__run_command. Git spawned `/usr/bin/vi .../rebase-merge/git-rebase-todo`; the tool call and sole remaining worker slot blocked for about ten minutes until the operator identified and terminated only that exact editor subprocess. The worker then recovered and continued. OOMPAH-647 made server-generated rebase continuation noninteractive, but arbitrary worker command execution still permits interactive rebase/editor/prompt paths despite repository AGENTS.md requiring noninteractive shell commands. Implementation scope: enforce the noninteractive Git environment at every worker shell/MCP command boundary and reject commands whose semantics require a TTY/editor, including bare `git rebase -i`, `git add -p`, `git commit` without a message in non-amend flows, and other known interactive Git modes; provide an actionable replacement such as scripted `GIT_SEQUENCE_EDITOR` or reset/commit when safe. Add bounded prompt/editor-child detection tied to the exact worker process tree so an unexpected editor is terminated and the command returns a recoverable error without killing unrelated processes or losing repository state. Relevant files: MCP run-command implementation/policy, ACP shell command wrappers, oompah/git_noninteractive.py, tool liveness/watchdog code, focus prompts, and process-tree tests. Required tests: a real worktree bare `git rebase -i` never launches the hostile/blocking EDITOR; known interactive modes are rejected before execution; noninteractive scripted rebase succeeds; an unexpected editor child is terminated within a bounded interval; repository/rebase state remains recoverable; unrelated workers are untouched. Acceptance: no worker slot can remain occupied by an editor or terminal prompt, the EXOCOMP-140 reproduction fails fast with guidance, and focused command-policy/process tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 18:58
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 18:58
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
