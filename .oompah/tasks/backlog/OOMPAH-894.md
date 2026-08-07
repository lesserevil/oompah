---
id: OOMPAH-894
type: task
status: Backlog
priority: null
title: Coalesce repeated owner rearm without erasing retained auto-archive provenance
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T13:45:31.251950Z'
updated_at: '2026-08-07T13:45:31.251950Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live diagnostic while repairing OOMPAH-877: an exhausted unbound auto-archive audit can be owner-rearmed successfully once while correctly retaining requested_by=auto_archive for future origin/main provenance binding, but repeating the same otherwise idempotent rearm returns audit_not_retryable because coalescing requires the fresh audit requested_by actor to equal the rearm-history owner actor. Implementation scope: separate retained transition provenance from rearm authorization/idempotency identity in terminal_transition_coordinator and terminal audit metadata; coalesce an exact repeated owner rearm for the same project/task/target/evidence generation without rewriting original auto_archive provenance or accepting a different actor/generation. Preserve evidence fingerprint and project-lock CAS fences. Required tests: unbound auto-archive first rearm then exact repeated rearm coalesces; retained requested_by remains auto_archive; late origin/main binding still works; bound owner provenance control; different owner/reason/evidence generation does not coalesce; concurrent repeat has one durable history entry; restart persistence. Acceptance: exact repeated owner rearm is idempotent and successful while historical transition provenance remains truthful and immutable.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

