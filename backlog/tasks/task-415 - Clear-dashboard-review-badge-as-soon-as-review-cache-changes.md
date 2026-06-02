---
id: TASK-415
title: Clear dashboard review badge as soon as review cache changes
status: Done
assignee:
  - oompah
created_date: '2026-06-02 03:05'
updated_date: '2026-06-02 03:06'
labels:
  - bug
dependencies: []
priority: high
ordinal: 47000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: the dashboard can show a stale reviews badge such as '1 awaiting review' while the Reviews page shows no open reviews. The Review page fetches /api/v1/reviews directly, but the dashboard badge is driven by the websocket state payload from reviews_summary. A tick may update _reviews_cache early and then spend a long time in dispatch, auto-archive, or other work before _notify_observers runs at the end. During that window the Reviews page is current but the dashboard badge still shows the previous summary.\n\nExpected behavior: whenever _handle_review_check changes the computed reviews_summary, oompah should emit a state-only websocket update immediately so the dashboard badge clears or updates without waiting for the rest of the tick. This should not trigger an issues fetch.\n\nImplementation guidance:\n1. Track the last emitted review summary on the orchestrator.\n2. After _handle_review_check updates _reviews_cache and _unmerged_review_branches, compute _reviews_summary().\n3. If the summary changed, call _notify_state_only() and remember the new summary.\n4. Keep the existing end-of-tick _notify_observers behavior unchanged.\n5. Add tests that _handle_review_check notifies when the summary changes, does not notify when unchanged, and still populates the review cache.\n6. Run the focused test and make test before closing.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed stale dashboard review badge updates. The orchestrator now tracks the last emitted reviews_summary and sends a state-only websocket update immediately after _handle_review_check when the summary changes, so the dashboard badge clears or updates without waiting for the rest of a long tick. Added regression tests and ran make test: 3744 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
