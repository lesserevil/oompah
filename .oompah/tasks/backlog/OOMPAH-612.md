---
id: OOMPAH-612
type: bug
status: Backlog
priority: 1
title: Avoid ACP auditor result deadlock on the dispatch event loop
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T19:33:15.081209Z'
updated_at: '2026-07-30T19:33:15.081209Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-610

Implementation scope: Fix the ACP Completion Auditor submit_audit_result bridge in oompah/orchestrator.py and oompah/acp_tools.py. The ACP SDK tool is async and invokes the synchronous audit_result_handler on the dispatch event-loop thread; the current handler calls asyncio.run_coroutine_threadsafe(..., same_loop).result(timeout=60), blocking that loop for 60 seconds. The coordinator result is then applied only after the timeout returns an error, causing a valid PASS to be persisted while the auditor is told it was rejected and retries indefinitely. Preserve the API-agent thread-pool bridge, but give ACP an awaitable path (or explicitly offload its synchronous handler) so the coordinator completes once and the tool returns its actual accepted/idempotent outcome without blocking the loop. Include bounded error handling and preserve target/attempt validation.\n\nRequired tests: Add a regression that executes the ACP submit_audit_result async tool on the same running event loop and proves the handler/coordinator completes without timeout or retry, returns accepted=true, and does not double-apply an idempotent attempt. Retain API-agent result-handler coverage and add a failure-path assertion. Run focused auditor/ACP/terminal-transition tests and make test.\n\nAcceptance criteria: ACP auditor PASS/FAIL submissions return the coordinator outcome promptly; a successful durable result is never reported as 'audit scheduler rejected result' merely because the dispatch loop was blocked; the auditor exits normally after one successful submission; graceful draining cannot be held indefinitely by this loop; all relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

