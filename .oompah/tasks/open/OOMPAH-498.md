---
id: OOMPAH-498
type: chore
status: Open
priority: 2
title: Group granular Release Delivery template assertions by behavior
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
- OOMPAH-497
labels: []
assignee: null
created_at: '2026-07-28T13:53:33.437818Z'
updated_at: '2026-07-28T14:35:37.175988Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

After canonical ownership is established, reduce granular static-source assertions remaining in `tests/test_dashboard_release_delivery_ui.py` and `tests/test_release_delivery_page.py`. Group assertions by observable contract: controls/structure, URL and refresh lifecycle, status rendering, selection/queue payload, drawer/evidence, accessibility, and XSS boundaries. Use helper assertions or table loops with descriptive failure messages instead of one test per HTML ID, CSS token, or JavaScript variable. Keep behaviorally distinct server-route tests and JavaScript function-body checks that validate data flow, generation counters, idempotency keys, safe text handling, and queue payload shape. Do not replace executable behavior tests with snapshots.

Tests

Run both files with collection and duration reporting before and after. Deliberately mutate or monkeypatch representative fixture strings in helper-level tests, where practical, to prove each grouped contract fails for the intended missing behavior. Run the release-delivery backend and E2E suites plus `make test`.

Acceptance criteria

Every listed behavior category remains protected, failures identify the missing contract, the two UI files have substantially fewer collected cases and repeated source reads, no queueing/security/accessibility behavior is lost, and all release-delivery tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

