---
id: TASK-459.5
title: Update dashboard board and detail views for GitHub issues
status: Done
assignee: []
created_date: '2026-06-08 17:57'
updated_date: '2026-06-09 23:14'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-459.1
  - TASK-459.2
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/templates/dashboard.html
  - tests/test_dashboard_draft_epics.py
parent_task_id: TASK-459
priority: high
ordinal: 127000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Show GitHub-backed issue display identifiers, GitHub issue links, tracker kind, project name, sub-issues, blockers, comments, review links, and a legacy marker for Backlog-backed tasks. Keep board grouping based on canonical oompah status.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GitHub issue cards link to the GitHub issue URL.
- [ ] #2 Legacy Backlog task cards remain usable and visually distinct.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 23:04
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 23:05
---
Understanding: Investigated for duplicates - confirmed NOT a duplicate. No other task covers dashboard board/detail view changes for GitHub issues. TASK-459.1 (Done) extended API schema, TASK-459.2 (Done) made mutation endpoints backend-neutral - both blockers are complete. This task needs to update oompah/templates/dashboard.html to: (1) show display_identifier (GitHub #123 form or TASK-xxx), (2) link GitHub issue URLs, (3) show tracker_kind/project name, (4) show sub-issues/blockers/comments/review links, (5) mark legacy Backlog tasks visually. Board grouping stays on canonical oompah status. Modified files list shows work may have started: dashboard.html and tests/test_dashboard_draft_epics.py. Starting codebase exploration.
---

author: oompah
created: 2026-06-09 23:08
---
Discovery: Codebase exploration complete. Both blockers done. Server already returns tracker_kind, url (GitHub URL), is_legacy, display_identifier in board and detail API responses. Dashboard JS already has issueDisplayIdentifier() function. Missing from the template: (1) Card-level GitHub URL link (clickable ↗ badge when issue.url is set), (2) Card-level legacy badge (when is_legacy is true), (3) Detail panel GitHub Issue URL field, (4) Detail panel Tracker field (tracker_kind + owner/repo). Will add CSS classes .legacy-badge and .tracker-link, update createCard() to include these badges, and update openDetailPanel() to render GitHub URL and tracker fields. Tests will verify these JS patterns are present in the template.
---

author: oompah
created: 2026-06-09 23:14
---
Implementation: Updated oompah/templates/dashboard.html with: (1) Three new CSS classes: .legacy-badge (amber, monospace badge for Backlog tasks), .tracker-link (small external link icon for GitHub URL on cards), .detail-github-link (blue link in detail panel). (2) createCard() gets trackerLinkHtml (↗ anchor to issue.url when set, stopPropagation) and legacyBadgeHtml ('legacy' span when issue.is_legacy), both interpolated into card HTML. (3) openDetailPanel() gets three conditional html+= blocks: GitHub Issue URL field (detail-github-link), Tracker field (tracker_kind + owner/repo), Legacy Note field (legacy-badge + text). Added 19 tests in tests/test_dashboard_github_issues.py.
---

author: oompah
created: 2026-06-09 23:14
---
Verification: 19 new tests in test_dashboard_github_issues.py — all pass. 525 dashboard+server tests pass (no regressions). 664 additional project/tracker/epic tests pass. AC #1 covered: createCard renders tracker-link anchor with issue.url, opens in new tab, stops card click propagation. AC #2 covered: createCard renders legacy-badge when is_legacy=true; badge is visually distinct (amber/yellow color scheme). Detail panel shows GitHub Issue URL as clickable link, Tracker kind with owner/repo, and Legacy Note badge.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated dashboard board and detail views for GitHub issues. Added CSS (.legacy-badge, .tracker-link, .detail-github-link), createCard() GitHub URL link (tracker-link ↗ anchor, stopPropagation) and legacy badge (is_legacy=true), openDetailPanel() GitHub Issue URL field, Tracker kind/owner/repo field, and Legacy Note field. 19 new tests in test_dashboard_github_issues.py — all pass. 525 dashboard+server tests pass, 664 additional tests pass. Branch pushed to epic-TASK-459.
<!-- SECTION:FINAL_SUMMARY:END -->
