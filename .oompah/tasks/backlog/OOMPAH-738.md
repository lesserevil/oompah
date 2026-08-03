---
id: OOMPAH-738
type: task
status: Backlog
priority: null
title: Fence terminal override cleanup from concurrent worker-map mutation
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T20:08:56.082557Z'
updated_at: '2026-08-03T20:08:56.082557Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live race reproduced on 2026-08-03 while overriding EXOCOMP-159 after deploying OOMPAH-729. The PATCH/terminal override correctly committed EXOCOMP-159 from In Validation to Done and revoked its newly dispatching auditor authority, but concurrent provider exit removed an entry from a shared dictionary while the update path iterated it. The server logged, in order: Running implementation authority generation revoked ... reason=task status changed; Skipping revoked implementation worker before provider setup; Quarantined revoked implementation worker after provider exit; then Update issue API error: RuntimeError('dictionary changed size during iteration'). The CLI received HTTP 500 even though a fresh task view proved the terminal mutation had committed. A caller can therefore retry a successful non-idempotent owner action because the response falsely reports failure.\n\nImplementation scope:\n- Identify every update/terminal-override cleanup loop that traverses running workers, auditors, managed processes, authority maps, or audit chains while provider-exit callbacks can mutate them.\n- Snapshot or lock the iteration under the existing authority boundary; never await or call provider cleanup while holding a mutable-dictionary iterator.\n- Make post-commit cleanup idempotent and ordered so a concurrent worker exit cannot change the authoritative terminal outcome.\n- If cleanup fails after the tracker/audit commit, return the committed result with explicit cleanup diagnostics rather than an ambiguous 500; preserve fail-closed behavior before commit.\n- Ensure retries observe and return the same terminal decision without creating duplicate override records, comments, audit retirement, or worker termination.\n\nRelevant code: PATCH /api/v1/issues/{identifier} update path in oompah/server.py, owner terminal override/coordinator finalization, orchestrator authority revocation and running-worker quarantine/provider-exit callbacks, and audit scheduler retirement.\n\nRequired tests:\n- Deterministically pause an auditor between dispatch registration and provider setup, commit an owner override, and concurrently remove/quarantine that run; no dictionary-size exception and one successful response.\n- Cover provider exit during iteration, already-retired auditor, multiple sibling audits, implementation worker versus audit worker, and task status change callbacks.\n- Inject a post-commit cleanup exception and prove the API reports the committed terminal state with actionable diagnostics; inject a pre-commit exception and prove no state change.\n- Retry the exact request and prove idempotent override metadata/comments and no duplicate termination.\n- Run focused terminal override, audit scheduler, agent lifecycle, server update API, and concurrency suites plus make test.\n\nAcceptance criteria:\n- Concurrent authority revocation/provider exit cannot produce 'dictionary changed size during iteration'.\n- A client never receives an ambiguous failure after the requested terminal state has committed.\n- Terminal authority, fingerprint fencing, worker retirement, and audit history remain exact and race-safe.\n\nTriggered by: EXOCOMP-159; related to OOMPAH-729 and OOMPAH-734.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

