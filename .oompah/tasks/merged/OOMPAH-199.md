---
id: OOMPAH-199
type: task
status: Merged
priority: 1
title: Add commit-selection release delivery queue API
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-195
- OOMPAH-198
labels: []
assignee: null
created_at: '2026-07-13T19:32:53.860350Z'
updated_at: '2026-07-13T23:37:36.501875Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 3a79a0f7-cb99-4715-a0d5-d2c9a4fc3883
oompah.task_costs:
  total_input_tokens: 160
  total_output_tokens: 4321
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 160
      output_tokens: 4321
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 160
    output_tokens: 4321
    cost_usd: 0.0
    recorded_at: '2026-07-13T22:35:07.290200+00:00'
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md section 4.2 POST contract.

Implement POST /api/v1/projects/{project_id}/release-delivery/commits. It accepts a source-head snapshot, ordered full source SHAs, target release branches, and an Idempotency-Key. Revalidate source reachability/non-merge eligibility and branch availability server-side, append exact immutable delivery bundles under the ledger lock, then wake the existing queue only after persistence.

Acceptance criteria
- Creates one ordered delivery bundle per eligible target branch and never creates an ordinary task.
- Rejects a changed source HEAD, invalid/unreachable/merge SHA, unavailable branch, missing idempotency key, and malformed payload before writing.
- Returns explicit created, already_active, already_delivered, and invalid per-pair outcomes without duplicate deliveries.
- Replaying the same idempotency key returns the original outcome and makes no additional ledger write.

Tests
- Server tests cover one/many commits, one/many targets, atomic validation failure, duplicate active/merged pairs, archived reapproval, queue wake-up after persistence, and idempotency replay.
- Test the queued source order reaches the executor unchanged.

Dependencies
- OOMPAH-195 and OOMPAH-198.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 22:16
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 22:17
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 22:18
---
Duplicate investigation complete: OOMPAH-199 is unique. No other task implements the POST /api/v1/projects/{project_id}/release-delivery/commits endpoint. Sibling tasks cover: ledger schema (193), migration (194), queue/executor refactoring (195), task/epic compat (196), CommitInventoryService (197), GET inventory API (198), UI overlay (200), docs/deprecation (201), and e2e (202). OOMPAH-199 is the only task implementing the write endpoint with idempotency, per-pair outcome reporting, and delivery bundle creation. Proceeding with implementation.
---
author: oompah
created: 2026-07-13 22:22
---
Discovery: Identified all relevant code. Infrastructure from OOMPAH-193/195/196/197/198 is in place: ReleaseDeliveryStore (ledger store), ReleaseDelivery dataclass, _delivery_lock (per-project lock), make_delivery_store, _make_delivery_id, approve_release_addendums_via_ledger pattern. GET endpoint is complete in server.py. The POST endpoint needs to be added at /api/v1/projects/{project_id}/release-delivery/commits with: Idempotency-Key header validation, JSON body parsing, git validation (source HEAD recheck via _resolve_remote_ref, commit reachability/non-merge checks), per-pair outcome determination (created/already_active/already_delivered), atomic append under _delivery_lock, queue wake via event_bus.emit(RELEASE_ADDENDUM_READY), and idempotency replay store. Tests go in tests/test_server_release_delivery_commits.py alongside the existing GET tests.
---
author: oompah
created: 2026-07-13 22:33
---
Implementation complete. Added POST /api/v1/projects/{project_id}/release-delivery/commits to server.py with: (1) Idempotency-Key header validation + in-memory replay store, (2) JSON body validation (source_head, commits, target_branches with full SHA checks), (3) server-side git revalidation via _delivery_validate_git (source HEAD check, reachability, non-merge, branch availability), (4) asyncio.to_thread for all git work, (5) per-pair outcome computation (created/already_active/already_delivered) under _delivery_lock, (6) atomic ledger write via store._write_ledger with all new deliveries in one call, (7) RELEASE_ADDENDUM_READY event emission after persistence, (8) commit_inventory cache invalidation. Also added bulk_append and read_all_by_target_branch to ReleaseDeliveryStore. All deliveries use source_kind=commits and source_identifier=None (never creates ordinary tasks). Added 46 new POST endpoint tests covering all acceptance criteria.
---
author: oompah
created: 2026-07-13 22:34
---
Verification: All tests pass. 8533 total (make test), 95/95 in test_server_release_delivery_commits.py, 118/118 in test_release_delivery_store.py. Branch epic-OOMPAH-192 pushed and up to date with origin.
---
author: oompah
created: 2026-07-13 22:34
---
Completion: Implemented POST /api/v1/projects/{project_id}/release-delivery/commits (section 4.2 POST contract). Delivery: (1) Idempotency-Key header required, in-memory replay store prevents duplicate writes on replay; (2) Full payload validation — source_head, commits (full SHAs), target_branches; (3) Server-side git revalidation in asyncio.to_thread — source HEAD snapshot comparison (409 on mismatch), per-commit reachability + non-merge checks, branch availability; (4) Atomic ledger append under _delivery_lock with all new delivery bundles in one write; (5) RELEASE_ADDENDUM_READY events emitted after persistence; (6) Per-pair outcomes: created, already_active, already_delivered, invalid; (7) All deliveries use source_kind=commits (never creates ordinary tasks); (8) 46 new server tests added to test_server_release_delivery_commits.py plus bulk_append/read_all_by_target_branch added to ReleaseDeliveryStore.
---
author: oompah
created: 2026-07-13 22:34
---
Implemented POST /api/v1/projects/{project_id}/release-delivery/commits with idempotency, server-side git validation, atomic ledger writes, per-pair outcomes, and queue wake-up. 46 new tests added; all 8533 tests pass.
---
author: oompah
created: 2026-07-13 22:35
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 103
- Tokens: 160 in / 4.3K out [4.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 10s
- Log: OOMPAH-199__20260713T221704Z.jsonl
---
<!-- COMMENTS:END -->
