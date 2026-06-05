---
id: TASK-446
title: Non-verbose agent transcript should show only message and thinking text
status: Done
assignee:
  - oompah
created_date: '2026-06-04 14:30'
updated_date: '2026-06-05 16:56'
labels: []
dependencies: []
modified_files:
  - oompah/templates/dashboard.html
  - tests/test_activity_panel_verbose_toggle.py
ordinal: 82000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the agent log popup, the non-verbose ('verbose off') mode should show only operator-readable model output entries: log kind 'message' and log kind 'thinking'. It must not show other plain-text log kinds such as tool/session/system payloads just because they contain non-empty non-JSON text. Within the allowed 'message' and 'thinking' kinds, empty/whitespace-only entries and raw JSON-only payloads should remain hidden. Verbose mode behavior is unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 In verbose=off, non-empty plain-text 'message' entries are visible.
- [x] #2 In verbose=off, non-empty plain-text 'thinking' entries are visible.
- [x] #3 In verbose=off, entries whose kind is not 'message' or 'thinking' are hidden even when their payload is non-empty plain text.
- [x] #4 In verbose=off, empty/whitespace-only entries and JSON-only payloads remain hidden.
- [x] #5 In verbose=on, existing full activity behavior is unchanged.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Corrected scope: compact/non-verbose mode should use an explicit allowlist of activity kinds ('message' and 'thinking'), then apply the existing content checks to hide empty/whitespace-only content and raw JSON blobs. Other activity kinds remain visible only in verbose mode.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Restricted non-verbose agent log popup entries to kind 'message' and 'thinking' only, while preserving existing empty/whitespace and JSON-only filtering and leaving verbose mode unchanged. Updated activity panel tests and verified with focused pytest plus full make test (4544 passed).
<!-- SECTION:FINAL_SUMMARY:END -->
