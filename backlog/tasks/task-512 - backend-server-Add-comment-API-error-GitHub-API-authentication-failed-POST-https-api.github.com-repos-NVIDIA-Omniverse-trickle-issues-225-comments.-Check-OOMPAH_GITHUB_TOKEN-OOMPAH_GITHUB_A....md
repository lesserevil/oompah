---
id: TASK-512
title: >-
  [backend:server] Add comment API error: GitHub API authentication failed (POST
  https://api.github.com/repos/NVIDIA-Omniverse/trickle/issues/225/comments).
  Check OOMPAH_GITHUB_TOKEN, OOMPAH_GITHUB_A...
status: Done
assignee:
  - oompah
created_date: '2026-06-10 15:47'
updated_date: '2026-06-10 15:55'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 239000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add comment API error: GitHub API authentication failed (POST https://api.github.com/repos/NVIDIA-Omniverse/trickle/issues/225/comments). Check OOMPAH_GITHUB_TOKEN, OOMPAH_GITHUB_APP_ID, or run 'gh auth login'.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: backlog
- tracker_kind: backlog
- fingerprint: 05a41bf0beb5d455
- dedup_fingerprint: 05a41bf0beb5d455
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Closed as transient during the initial cutover smoke. Retrying the comment path succeeded against NVIDIA-Omniverse/trickle#225, and subsequent GitHub issue mutations through the project token also succeeded after TASK-513.
<!-- SECTION:FINAL_SUMMARY:END -->
