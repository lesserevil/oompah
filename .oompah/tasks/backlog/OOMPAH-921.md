---
id: OOMPAH-921
type: task
status: Backlog
priority: null
title: Stop direct-owner terminal overrides from self-invalidating evidence
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T16:33:49.292212Z'
updated_at: '2026-08-08T16:33:49.292212Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live recurrence on deployed d796a4b after OOMPAH-889: OOMPAH-588 is direct-owner claimed and In Progress; its historical landed head a3a577a489650c602ec3c62bd242eb53de631af4 is contained in origin/main and parent OOMPAH-584 is Merged, yet two fresh authenticated project-owner Done overrides both return evidence_fingerprint_mismatch. The API appears to compute terminal evidence before an ownership/dispatch-fence or native rollup mutation changes the same task, so the request invalidates itself rather than rejecting genuinely stale caller evidence. Trace server terminal transition staging, owner-claim retirement/revocation, TerminalTransitionCoordinator fingerprint CAS, and native parent rollup. Preserve genuine stale/tampered evidence rejection and ordinary shared-epic Merged landing checks. Add production-shaped regression coverage for an In Progress direct-owner-claimed historically landed nested epic: a fresh Done override succeeds atomically and remains Done across refresh/reconciliation; a concurrent external metadata mutation still fails closed. Run focused tests, terminal mutation scan, secret scan, and exact full Makefile gate. Acceptance: OOMPAH-588 can be restored to stable Done through the authenticated API without hand-editing tracker/state files or recreating pruned branches.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

