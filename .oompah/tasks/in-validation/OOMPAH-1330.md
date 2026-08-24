---
id: OOMPAH-1330
type: task
status: In Validation
priority: null
title: Auditor OpenCode ACP transport crashes on >64KiB JSON-RPC lines (Separator
  is found, but chunk is longer than limit)
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T16:03:40.977842Z'
updated_at: '2026-08-24T16:59:11.675858Z'
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
  creation_marker: 9b97bcbb-e6fa-488f-8275-579ea59de529
  request_fingerprint: e3b707c418dee4750bfee0f7a47b8bdd131c9282b7c0568052cfe8fd994ea64c
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-880d1098e31e
    project_id: proj-14849f1b
    task_id: OOMPAH-1330
    digest: 648cfbb5a46f2eac6fcd37b46d7fa0879085d7a392aaf39499e395f9e13383fb
  - version: 1
    audit_id: audit-436fa43dadd4
    project_id: proj-14849f1b
    task_id: OOMPAH-1330
    digest: 648cfbb5a46f2eac6fcd37b46d7fa0879085d7a392aaf39499e395f9e13383fb
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-880d1098e31e
    project_id: proj-14849f1b
    task_id: OOMPAH-1330
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 648cfbb5a46f2eac6fcd37b46d7fa0879085d7a392aaf39499e395f9e13383fb
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T16:59:02.332831+00:00'
    eligible_at: '2026-08-24T16:59:02.332831+00:00'
    selected_ref: origin/OOMPAH-1330
    selected_sha: 585382bbb8f5e02b8938dacc4653786b18af0107
  - version: 1
    audit_id: audit-436fa43dadd4
    project_id: proj-14849f1b
    task_id: OOMPAH-1330
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 648cfbb5a46f2eac6fcd37b46d7fa0879085d7a392aaf39499e395f9e13383fb
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T16:59:02.332831+00:00'
    prerequisite_audit_id: audit-880d1098e31e
    selected_ref: origin/OOMPAH-1330
    selected_sha: 585382bbb8f5e02b8938dacc4653786b18af0107
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
Completion auditors dispatched to the OpenCode/Switchyard provider (prov-6cf41c89/switchyard/auto) repeatedly crash before producing a verdict with:

    ValueError: Separator is found, but chunk is longer than limit

Observed live on the current main build (revision 1e08d58a3) at 2026-08-24T15:36/15:44 while auditing OOMPAH-1249 and OOMPAH-1268. Each attempt exhausts the 3-attempt terminal-audit budget, routes tasks to Needs Human, and keeps workflow_liveness in restart_overdue (scan_complete=false, restart reconstruction pending), which surfaces the dashboard alert 'N workflow task(s) require a named human action'.

### Why the existing fixes don't cover this
- OOMPAH-1327 added limit=MAX_LINE_SIZE to oompah/agent.py create_subprocess_exec.
- OOMPAH-1328 added limit=MAX_LINE_SIZE to oompah/acp_backends/opencode.py create_subprocess_exec (verified present on main at opencode.py:443).
Despite both, the crash persists for the OpenCode *auditor provider* path. The oversized line is being read by a StreamReader that still has asyncio's default 64 KiB limit — evidence points to the ACP/JSON-RPC client transport used to drive the 'opencode' provider session (or the opencode binary's own ACP serve loop), not the two already-patched create_subprocess_exec call sites.

### Steps to Reproduce
1. Run oompah on proj-14849f1b (tracker provenanceguardedtracker) with auditor role bound to the OpenCode/Switchyard provider.
2. Dispatch a completion audit whose evidence/tool output emits a single JSON-RPC line larger than 65536 bytes.
3. Observe the auditor attempt end with 'ValueError: Separator is found, but chunk is longer than limit' and the terminal-audit retry budget exhaust.

### Investigation scope
- Locate every StreamReader/open_connection/readline used to speak ACP JSON-RPC to provider subprocesses (not just the two create_subprocess_exec sites already fixed). Grep for asyncio stream construction in the ACP client/session transport and any code that wraps the 'opencode' CLI or its ACP 'serve' protocol.
- Ensure the reader buffer limit is raised to MAX_LINE_SIZE (10 MiB) on that transport, or chunk/frame reads so a single large line cannot overflow the default 64 KiB.
- If the overflow is inside the external 'opencode' binary's ACP serve loop (not oompah code), bound auditor output/evidence size before it is emitted, or switch the auditor role to an independent provider that does not exhibit the crash.

### Tests
- Regression: drive the ACP auditor transport with a >64 KiB JSON-RPC line and assert no ValueError and a parsed result.
- Assert the auditor subprocess/stream is created with limit=MAX_LINE_SIZE on the identified path.

### Acceptance Criteria
- OpenCode auditor attempts no longer raise 'Separator is found, but chunk is longer than limit' on large audit payloads.
- Terminal audits for OOMPAH-1249 and OOMPAH-1268 can complete once rearmed.
- workflow_liveness restart reconstruction converges (scan_complete=true) and the 'require a named human action' dashboard alert clears when no genuine human action is pending.
- No regression in other ACP backends (Claude, Codex) or the two already-fixed create_subprocess_exec sites.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 16:59
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
