---
id: OOMPAH-989
type: bug
status: In Progress
priority: 1
title: Keep graceful restart responsive while quiesce drains workflow work
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T06:19:44.763738Z'
updated_at: '2026-08-10T10:14:32.010159Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-989
  head_sha: 7b5f28ac3bdc10cd6ae244af943acf6768e07207
  submitted_at: '2026-08-10T10:14:27.838130+00:00'
  updated_at: '2026-08-10T10:14:27.838130+00:00'
---
## Summary

Triggered by: OOMPAH-986

Live regression on 2026-08-10 while deploying OOMPAH-986: make graceful acquired the restart claim against healthy revision 148db44a97e42140160a428bd11eed2c50f75381, then POST /api/v1/orchestrator/quiesce timed out. The server stopped answering /healthz and /api/v1/state for several minutes, logged no progress after 06:08:42 UTC, and slept on futex_do_wait. The cutover could not cancel its restart claim because that POST also timed out, requiring the identity-checked make force-restart recovery. The last authoritative snapshot had zero agents and auditors; only durable workflow jobs existed. Diagnose and eliminate any event-loop blocking/deadlock across the quiesce/restart-claim path, workflow publication, issue snapshot refresh, and webhook handling. Relevant code: server lifecycle endpoints, orchestrator quiesce/drain, scripts/canonical_cli_cutover.py, workflow_runtime publication/drain coordination, and lifecycle tests. Add a deterministic regression that holds slow/full-project workflow or snapshot work while a graceful restart claims and quiesces; prove /healthz and lifecycle control requests remain responsive, the quiesce request returns within its HTTP budget, cancellation/resume remains possible after a pre-cutover failure, no agent is interrupted before drain authority permits it, and restart reaches the exact new build without force. Also cover a dropped/timed-out response after server-side acceptance so the client and server converge without an orphaned restart fence. Acceptance: make graceful cannot wedge the HTTP control plane; bounded failures leave the old service responsive and unquiesced or complete an exactly identified cutover; focused lifecycle/runtime/server tests and the full Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 06:49
---
Implementation is complete and pushed for independent review at 53b413fbfd6975d007fbf5c04711db2a666b20d4 on branch OOMPAH-989, rebased onto origin/main 6c6f55220f61149fc15e73f18fbf7fdc2445f146. The fix keeps quiesce/restart provider-fence acquisition cooperative and bounded, moves issue snapshot authority reads plus resume recovery off the HTTP event loop, makes graceful-restart admission cooperative, and retries exact idempotent restart-claim cancellation after an accepted-but-dropped response. Deterministic regressions cover quiesce and restart contention with responsive health, a blocked snapshot authority probe with responsive health, and dropped quiesce/cancel responses converging without an orphan restart fence. Validation: combined OOMPAH-989 plus OOMPAH-987/OOMPAH-988 adjacent orchestrator/gate suites 1455 passed, 3 non-failing warnings; compileall passed; git diff --check passed; terminal-audit scan passed; secret checks and commit hooks passed. Task intentionally remains In Progress and unsubmitted pending independent review.
---
author: oompah
created: 2026-08-10 07:14
---
Independent-review blockers at 53b413f are fixed and pushed at replacement head 8ec9c3e760aa5f276426726f797825576e66e978. Lifecycle state mutation is now separated from heavyweight publication: API quiesce commits under cooperative admission with synchronous notification suppressed; API resume mutates on the dedicated lifecycle executor with notification suppressed; both queue full observer snapshots on a separate publication pool. Resume notification always occurs after provider admission is released. graceful_restart moves both observer snapshots and restart-journal merge/persistence off the event loop, including rollback persistence/notification. Failed restart drain cleanup now performs only its in-memory CAS synchronously and always delegates save/notification after releasing admission, including the uncontended path. New deterministic regressions use a real Orchestrator/full get_snapshot project-authority hold and explicit snapshot, restart-journal, and failed-cleanup persistence barriers; they prove health plus claim/cancel/resume remain responsive and admission is not stranded. Validation: 1613 passed, 3 non-failing warnings, 0 failures across OOMPAH-989 and adjacent OOMPAH-987/OOMPAH-988 gate/server/orchestrator/event/retry/termination suites; compileall, git diff --check, terminal-audit scan, Makefile secret scan, and commit hooks passed. Task remains In Progress and unsubmitted for another independent review.
---
author: oompah
created: 2026-08-10 07:15
---
Correction to the preceding review-fix comment: the exact pushed replacement head is 8ec9c3e76704908c7f350517c975765158818cad (local HEAD and origin/OOMPAH-989 match). The prior comment's expanded SHA was a transcription error; its implementation and validation details are otherwise accurate.
---
author: oompah
created: 2026-08-10 07:50
---
Final re-review blockers are fixed at exact pushed head 27b21eb9dac8340c3a97c1a791e83205ed4d58ac. Lifecycle publication is now owned per Orchestrator: one running full snapshot plus only the latest monotonic generation is coalesced; restart success and exception paths enqueue without awaiting; a publication epoch and provider-admission generation fence prevent blocked old snapshots from emitting after lifecycle change or teardown; shutdown cancels queued work and performs non-waiting executor shutdown; replacing the server orchestrator fences the old publisher. The process-global lifecycle publication executor was removed. Pause/unpause and failed-drain rollback persistence now use a generation-CAS write held through the state-file replace, and rollback generations are monotonic, so newer operator pause intent either writes after the older rollback or makes that rollback stale before disk mutation. Deterministic real-Orchestrator regressions prove: journal and drain completion while a full snapshot remains permanently blocked; exception rollback completion under the same block; latest-generation coalescing; teardown rejection and no stale observer emission after release; health/cancel responsiveness; and blocked rollback False followed by concurrent pause finishes with durable/memory True and ordered writes False then True. Validation: 1667 passed, 3 non-failing warnings, 0 failures across OOMPAH-989 plus adjacent OOMPAH-987/OOMPAH-988 lifecycle/gate/server/event/retry/termination and set_orchestrator suites. Focused blocker rerun 4 passed. compileall, git diff --check, graceful_restart observer-await static scan, terminal-audit scan, Makefile secret scan, and commit hooks passed. Task remains In Progress and unsubmitted pending final independent review.
---
author: oompah
created: 2026-08-10 08:12
---
Final three independent-review blockers are fixed and pushed at exact head 8ef2a699da97a7e594bef6162bb2dafa7e32580b. Lifecycle snapshots now use a per-Orchestrator coalescing daemon thread, so a permanently blocked advisory snapshot cannot keep interpreter shutdown alive. Generation/epoch authority is committed at the observer sink entry; shutdown revokes work blocked before that boundary without waiting, and no provider/lifecycle lock is held across IPC, EventBus, or legacy observer callbacks. The pause API now performs pause authority and generation-CAS persistence on the lifecycle executor with synchronous snapshot notification disabled, preserves running-agent retirement by scheduling it on the captured live API loop, then queues fenced publication. New deterministic regressions prove bounded shutdown and available admission with a sink-boundary barrier plus no late stale observer emission, health responsiveness while older persistence owns provider admission for 300ms, and normal subprocess exit with a permanently blocked snapshot worker. Focused combined lifecycle/restart/server/pause/event/retry/auditor/IPC compatibility suite: 509 passed, 3 non-failing warnings; the two concurrency regressions passed 10 repeated runs; py_compile and git diff --check passed; commit secret hooks passed. Per final-review coordination, the full Makefile gate was not run at this head and should wait until independent approval. Task remains In Progress and unsubmitted for independent final re-review.
---
author: oompah
created: 2026-08-10 08:37
---
The final post-permit/pre-sink replacement race is fixed at exact pushed head 6f32efb14ac3ead1b8392985180c96a7bc5cb7ab, rebased cleanly onto origin/main 41ac37dbd3148b167ae2f2917f19734ad037eb10 (merged OOMPAH-990). Lifecycle publication now propagates an exact revocable source permit into each sink. IPC state publication uses an atomic SQLite source-ID compare-and-replace, with set_orchestrator atomically activating the replacement source; an old process that cached a True Python predicate still cannot mutate after the replacement claim. EventBus propagates the permit to handlers for narrow mutation-time CAS and rechecks source before dispatch. Server full/state observer wrappers are bound to the exact Orchestrator and perform source+permit validation under the same owner lock as cache mutation/replacement; old callbacks cannot overwrite the replacement cache. No provider/lifecycle lock is held across IPC, EventBus handlers, or legacy callbacks. Deterministic barriers now pause (1) after IPC's Python guard but before SQL, (2) inside EventBus handler entry before permit mutation, and (3) inside the source-aware legacy wrapper before server cache CAS; shutdown+set_orchestrator completes, all old mutations are rejected, current pre/post-cutover deliveries succeed, and callback lock availability is proved. Post-rebase focused combined lifecycle/server/EventBus/IPC/pause/retry/auditor plus OOMPAH-990 quality-gate/OOMPAH-988 validation-lease suite: 1356 passed, 3 existing warnings. The three sink barriers passed 10 repeated runs. py_compile, diff-check, and commit secret hooks passed. Full Makefile gate intentionally remains deferred until independent approval. Task remains In Progress and unsubmitted for final re-review.
---
author: oompah
created: 2026-08-10 09:03
---
Implementation checkpoint pushed at b865539bf on OOMPAH-989. Replacement now serializes whole cutovers, drains sink-local admitted EventBus and legacy callbacks outside provider/lifecycle/ownership locks, preserves supported plain callbacks, and rolls back on bounded timeout without switching the installed owner. IPC state publication is fenced by exact source+epoch+generation; lifecycle requests advance that authority and shutdown revokes it. Added migration and deterministic gen0-to-gen1 cached-true, plain-callback drain, timeout rollback, and concurrent replacement ABA tests. Verification: 1,359 focused regressions passed (3 existing warnings); 110 post-commit core tests passed; exact six-case race pack passed 10/10 repetitions (60/60). origin/main remains 41ac37dbd; branch is pushed/up to date. Full make test intentionally deferred to the configured review-ready branch gate; task left In Progress for review.
---
author: oompah
created: 2026-08-10 09:12
---
Reviewer fail-open blocker fixed and pushed at exact head d2cbe93047a08085f784699f7ffb88cae703af0a. Lifecycle IPC writes now require a non-empty activated source ID plus explicit epoch and generation whenever source_is_current is supplied; missing authority is rejected at OrchestratorIPC.put_kv, and Orchestrator skips the lifecycle IPC sink when set_orchestrator source activation failed. Non-lifecycle source-less publish_state compatibility remains unchanged and is explicitly tested. Real shared-SQLite activation-failure regression proves an unclaimed lifecycle publisher cannot overwrite replacement-owned state. Rollback re-audit found no other partial-advance, ABA, or lock-order blocker. Evidence: exact fail-open/generation/replacement selector 4 passed; restart+EventBus+IPC core 112 passed; broad focused regression selection 1,361 passed with 3 existing warnings; git diff/check and commit hooks passed. Branch OOMPAH-989 is clean and up to date with origin. Full gate not launched pending re-review.
---
author: oompah
created: 2026-08-10 09:45
---
Full-gate repair pushed at exact head dde652463d3ef5a732c229640c84ae42ecd59bca. Prior exact full make test on d2cbe93047a08085f784699f7ffb88cae703af0a failed 3 tests after 19,368 passed, 7 skipped, 2 xfailed, 48 warnings in 1,255.30s: lightweight workflow-store shutdown compatibility, daemon-publication subprocess startup/exit timing, and replacement vs blocked IPC predicate. Root cause repair: cooperative source_is_current now runs before OrchestratorIPC._lock (test asserts mutex is free), while exact source+epoch+generation INSERT...SELECT remains the authoritative commit fence; source revocation has bounded Python-lock and SQLite busy timeouts using the remaining lifecycle deadline; undrained callback shutdown fails closed before persistent stores close. Tests now use event-ordered barriers: subprocess startup readiness is separated from the 2s post-ready exit proof, and replacement synchronously revokes authority before the cached-true writer resumes and is rejected by SQL. Evidence: original failed trio plus new Python-lock/SQLite-lock/store-close cases pass 6/6 post-commit; five race cases passed 10x (50/50); affected core including full epic workflow adapter passes 167; broad focused selection passes 1,415 with 3 existing warnings; py_compile, static lock scan, diff check, commit secret hooks all pass. Branch is clean/up to date. Full gate intentionally not rerun pending re-review.
---
author: oompah
created: 2026-08-10 09:51
---
Reviewer reconnect-deadline blocker fixed at exact pushed head 7b5f28ac3bdc10cd6ae244af943acf6768e07207. Previous dde652463 bounded deactivate could call normal _ensure_conn/_open after close, inheriting sqlite3.connect(timeout=5) and schema writes before the remaining lifecycle deadline was installed; real close()+BEGIN IMMEDIATE repro took ~5.006s for a 0.05s request. Revocation now uses a deactivation-only reconnect to the existing authority DB: no schema writes, connect uses the remaining budget, SQLite busy timeout is installed before exact publication_sources schema validation and DELETE, missing/incompatible schema fails closed, and the normal 5000ms busy timeout is restored before returning the handle to ordinary callers. Exact regression proves disconnected+BEGIN IMMEDIATE returns False under 1s for timeout=0.05, preserves old epoch/generation authority, and restores busy_timeout=5000. Evidence: reconnect/Python-lock/SQLite-lock/replacement pack passed 10x (40/40); post-commit exact pack 4/4; affected core 168 passed with 2 existing warnings; broad focused selection 1,417 passed with 3 existing warnings; diff check, py_compile, and commit secret hooks passed. Branch clean/up to date. Full gate not launched pending re-review.
---
author: oompah
created: 2026-08-10 10:14
---
Final exact branch gate passed at 7b5f28ac3bdc10cd6ae244af943acf6768e07207: make test completed with 19,375 passed, 7 skipped, 2 xfailed, 49 warnings in 1,255.13s. Independent exact-head review approved the lifecycle publication, bounded IPC revocation/reconnect, authority rollback, and compatibility repairs; focused evidence is recorded in prior comments.
---
<!-- COMMENTS:END -->
