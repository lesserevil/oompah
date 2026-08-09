---
id: OOMPAH-918
type: bug
status: Done
priority: 1
title: Make management-tracker alert diagnostics path-length independent
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T15:12:47.858971Z'
updated_at: '2026-08-09T21:43:08.982746Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-94494af4ac62
    project_id: proj-14849f1b
    task_id: OOMPAH-918
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b360d5ff15ac50547335c2d73382080775c943ce3e5af6386f0ae668be79e593
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:27:52.272971+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-918
    target_state: Done
    evidence_fingerprint: b360d5ff15ac50547335c2d73382080775c943ce3e5af6386f0ae668be79e593
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:28:01.114223+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Owner-reviewed terminal implementation is retained. The Done child is
      durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
      exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
    marked_at: '2026-08-09T21:43:07.456489+00:00'
    updated_at: '2026-08-09T21:43:07.456489+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Owner-reviewed terminal implementation is retained. The Done child is
        durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
        exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
      recorded_at: '2026-08-09T21:43:07.456489+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

The management_tracker_resolution alert currently stores a raw repository/path exception in detail and relies on the generic alert sanitizer length threshold to move it into diagnostic. Its regression test passes or fails solely according to the generated temporary path length, and short paths can leak local filesystem diagnostics into the compact dashboard. Update oompah/server.py to emit an explicit bounded operator-facing detail plus the raw failure under diagnostic, update tests/test_management_tracker_resolution.py to assert the structured producer and snapshot contracts, and run focused tests plus the exact full make test gate. Acceptance: compact detail never exposes the raw repository path, diagnostic_available is true with the actionable exact diagnostic, behavior is independent of temp-root length, and the full gate is green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 15:14
---
Direct owner implementation is complete on the systemic composition head: management-tracker failures now emit a fixed compact detail and explicit raw diagnostic, making dashboard path disclosure independent of temp-root length. Focused serial reproduction passes. This task remains Backlog/unclaimed only because the currently deployed expired-transition recovery bug blocks promotion; it will be promoted and direct-claimed immediately after the repaired head is deployed.
---
author: oompah
created: 2026-08-08 16:28
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
