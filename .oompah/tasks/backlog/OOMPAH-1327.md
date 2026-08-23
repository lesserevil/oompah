---
id: OOMPAH-1327
type: task
status: Backlog
priority: null
title: '[backend:agent] Auditor subprocess readline crashes on lines >64KiB (Separator
  is found, but chunk is longer than limit)'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-23T21:54:32.810884Z'
updated_at: '2026-08-23T21:54:32.810884Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 8f85a250-1070-4c56-9175-6156032292b9
  request_fingerprint: 0478bc00db58f4b66809697c958bb69f71680af4fb9c32d7d90335fd2c1c0752
---
## Summary

### Problem
Completion auditors repeatedly crash before producing a verdict with:

    ValueError: Separator is found, but chunk is longer than limit

This exhausts the 3-attempt terminal-audit retry budget and forces tasks into the dashboard 'Needs Human' column ('Done audit requires operator input'). Observed on OOMPAH-1201, OOMPAH-1206, OOMPAH-1266, OOMPAH-1268 (all parked in .oompah/tasks/needs-human on the state branch).

### Root Cause
oompah/agent.py AgentSession.start() calls asyncio.create_subprocess_exec(...) WITHOUT passing limit=, so the StreamReader keeps the asyncio default 64 KiB buffer. _read_response() and _drain_stderr() call StreamReader.readline(); when an ACP/JSON-RPC line exceeds 64 KiB (large auditor tool output / evidence payloads) readline raises 'Separator is found, but chunk is longer than limit'. The module already defines MAX_LINE_SIZE = 10*1024*1024 but it was never wired into subprocess creation.

### Steps to Reproduce
1. Start an AgentSession whose subprocess emits a single stdout line longer than 65536 bytes without a newline.
2. Call _read_response (or let _drain_stderr run).
3. Observe ValueError: Separator is found, but chunk is longer than limit.

### Fix (implemented on branch, needs review/landing)
Pass limit=MAX_LINE_SIZE to asyncio.create_subprocess_exec in AgentSession.start so stdout/stderr StreamReaders buffer up to 10 MiB.

### Acceptance Criteria
- create_subprocess_exec is invoked with limit=MAX_LINE_SIZE (unit test asserts kwargs['limit'] == MAX_LINE_SIZE).
- Regression test drives readline against a >64 KiB line without raising the limit ValueError.
- Auditor dispatch no longer exhausts its retry budget from oversized-line crashes; tests/test_agent.py stays green (27 passing).
- Stuck tasks OOMPAH-1201/1206/1266/1268 can complete their terminal audit once rearmed.

### Test Commands
- uv run python -m pytest tests/test_agent.py -q
- make test

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

