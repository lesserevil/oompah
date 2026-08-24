---
id: OOMPAH-1327
type: task
status: In Validation
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
updated_at: '2026-08-24T00:23:38.246664Z'
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
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-76cfa3e76835
    project_id: proj-14849f1b
    task_id: OOMPAH-1327
    digest: ec54d37a26f0a8ac377ed6cba16e297bf2b6247c1dba88c9b0d096f10a89d6ee
  - version: 1
    audit_id: audit-baa4202ff705
    project_id: proj-14849f1b
    task_id: OOMPAH-1327
    digest: ec54d37a26f0a8ac377ed6cba16e297bf2b6247c1dba88c9b0d096f10a89d6ee
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-76cfa3e76835
    project_id: proj-14849f1b
    task_id: OOMPAH-1327
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec54d37a26f0a8ac377ed6cba16e297bf2b6247c1dba88c9b0d096f10a89d6ee
    attempts:
    - version: 1
      attempt_id: attempt-56feef71903f
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ec54d37a26f0a8ac377ed6cba16e297bf2b6247c1dba88c9b0d096f10a89d6ee
      created_at: '2026-08-24T00:23:26.877689+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T00:23:26.877689+00:00'
      branch_key: OOMPAH-1327
      selected_ref: origin/OOMPAH-1327
      selected_sha: a1bdfad376af434e72551b698b2171863b4857dd
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T00:16:35.208700+00:00'
    eligible_at: '2026-08-24T00:16:35.208700+00:00'
    selected_ref: origin/OOMPAH-1327
    selected_sha: a1bdfad376af434e72551b698b2171863b4857dd
    updated_at: '2026-08-24T00:23:26.877689+00:00'
  - version: 1
    audit_id: audit-baa4202ff705
    project_id: proj-14849f1b
    task_id: OOMPAH-1327
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec54d37a26f0a8ac377ed6cba16e297bf2b6247c1dba88c9b0d096f10a89d6ee
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T00:16:35.208700+00:00'
    prerequisite_audit_id: audit-76cfa3e76835
    selected_ref: origin/OOMPAH-1327
    selected_sha: a1bdfad376af434e72551b698b2171863b4857dd
  attempt_history:
  - version: 1
    attempt_id: attempt-56feef71903f
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec54d37a26f0a8ac377ed6cba16e297bf2b6247c1dba88c9b0d096f10a89d6ee
    created_at: '2026-08-24T00:23:26.877689+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T00:23:26.877689+00:00'
    branch_key: OOMPAH-1327
    selected_ref: origin/OOMPAH-1327
    selected_sha: a1bdfad376af434e72551b698b2171863b4857dd
oompah.lifecycle_revision: 1
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 00:16
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-24 00:23
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 00:23
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
