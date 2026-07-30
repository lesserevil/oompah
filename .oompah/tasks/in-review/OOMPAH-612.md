---
id: OOMPAH-612
type: bug
status: In Review
priority: 1
title: Avoid ACP auditor result deadlock on the dispatch event loop
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T19:33:15.081209Z'
updated_at: '2026-07-30T19:44:26.184248Z'
work_branch: OOMPAH-612
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/595
review_number: '595'
merged_at: null
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-612
  head_sha: 8ce6fa0ad3a343b053298a64f721a6a3b73ceb22
  submitted_at: '2026-07-30T19:43:50.264292+00:00'
  updated_at: '2026-07-30T19:43:50.264292+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/595
oompah.review_number: '595'
oompah.work_branch: OOMPAH-612
oompah.target_branch: main
---
## Summary

Triggered by: OOMPAH-610

Implementation scope: Fix the ACP Completion Auditor submit_audit_result bridge in oompah/orchestrator.py and oompah/acp_tools.py. The ACP SDK tool is async and invokes the synchronous audit_result_handler on the dispatch event-loop thread; the current handler calls asyncio.run_coroutine_threadsafe(..., same_loop).result(timeout=60), blocking that loop for 60 seconds. The coordinator result is then applied only after the timeout returns an error, causing a valid PASS to be persisted while the auditor is told it was rejected and retries indefinitely. Preserve the API-agent thread-pool bridge, but give ACP an awaitable path (or explicitly offload its synchronous handler) so the coordinator completes once and the tool returns its actual accepted/idempotent outcome without blocking the loop. Include bounded error handling and preserve target/attempt validation.\n\nRequired tests: Add a regression that executes the ACP submit_audit_result async tool on the same running event loop and proves the handler/coordinator completes without timeout or retry, returns accepted=true, and does not double-apply an idempotent attempt. Retain API-agent result-handler coverage and add a failure-path assertion. Run focused auditor/ACP/terminal-transition tests and make test.\n\nAcceptance criteria: ACP auditor PASS/FAIL submissions return the coordinator outcome promptly; a successful durable result is never reported as 'audit scheduler rejected result' merely because the dispatch loop was blocked; the auditor exits normally after one successful submission; graceful draining cannot be held indefinitely by this loop; all relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 19:35
---
Claimed by the interactive operator session. Keeping the task non-dispatchable while repairing the ACP submit bridge because the running service cannot safely self-audit this event-loop defect without reproducing the 60-second loop block. Root cause was live-reproduced by OOMPAH-610 audit attempt attempt-9ad0fa99a03f.
---
author: oompah
created: 2026-07-30 19:43
---
Implemented the ACP bridge repair: Claude and OpenCode async submit_audit_result tools now offload the synchronous run_coroutine_threadsafe coordinator bridge, keeping the dispatch loop free to apply and return the actual result. Added same-loop success/idempotency regressions for both async ACP catalogs and a coordinator-rejection regression. Focused suite: 237 passed. Full make test: 13,729 passed, 7 skipped; terminal mutation scan and secret scan passed.
---
author: oompah
created: 2026-07-30 19:43
---
Offload Claude/OpenCode ACP audit-result submission bridges so the event loop can apply the coordinator result; add same-loop success, idempotency, and rejection regressions. Full make test passed 13,729 with 7 skipped.
---
<!-- COMMENTS:END -->
