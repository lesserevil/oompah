---
id: OOMPAH-1328
type: task
status: Open
priority: null
title: Apply large stream limit to OpenCode ACP subprocesses
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T00:59:00.469186Z'
updated_at: '2026-08-24T01:01:15.325277Z'
work_branch: OOMPAH-1328
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 32623887-6658-4507-aebe-1f82fa244df7
  request_fingerprint: 3e72702ee72c5191f330bc2235080b55d6d11adf9beb0ee63295241e50b8ada2
oompah.lifecycle_revision: 1
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1328
  base_branch: main
  base_sha: 859930db3ade55125aafb55fa634c1e49f9e57a4
  head_sha: aaac848e78bef6ee935df3c6697bcaa53012bfbb
  submitted_at: '2026-08-24T01:01:01.865641+00:00'
  updated_at: '2026-08-24T01:01:01.865641+00:00'
oompah.work_branch: OOMPAH-1328
---
## Summary

Completion auditors using the OpenCode ACP backend still fail with ValueError: Separator is found, but chunk is longer than limit after OOMPAH-1327, because oompah/acp_backends/opencode.py invokes asyncio.create_subprocess_exec without limit=MAX_LINE_SIZE. This repeatedly exhausts terminal-audit retries, moves tasks to Needs Human, creates tracker-authority churn, and prevents restart reconstruction from admitting workers, leaving non-terminal tasks inactive. Implement the same bounded 10 MiB subprocess stream limit on the OpenCode backend. Add regression coverage in tests/test_acp_opencode_backend.py asserting the spawn limit and handling an output line larger than 64 KiB. Run focused OpenCode backend tests and the branch gate. Acceptance: OpenCode auditors no longer raise the asyncio separator/limit ValueError; exhausted affected audits can be safely rearmed; workflow reconstruction converges and inactive non-terminal work resumes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 01:00
---
Root cause confirmed in the live server: OpenCode completion auditors bypass AgentSession and create subprocess streams without MAX_LINE_SIZE. Implementing the missing limit with regression coverage.
---
<!-- COMMENTS:END -->
