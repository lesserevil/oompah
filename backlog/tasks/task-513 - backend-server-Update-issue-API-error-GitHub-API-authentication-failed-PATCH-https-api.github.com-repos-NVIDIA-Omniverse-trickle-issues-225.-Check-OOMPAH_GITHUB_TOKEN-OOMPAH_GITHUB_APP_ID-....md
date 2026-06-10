---
id: TASK-513
title: >-
  [backend:server] Update issue API error: GitHub API authentication failed
  (PATCH https://api.github.com/repos/NVIDIA-Omniverse/trickle/issues/225).
  Check OOMPAH_GITHUB_TOKEN, OOMPAH_GITHUB_APP_ID, ...
status: Done
assignee:
  - oompah
created_date: '2026-06-10 15:47'
updated_date: '2026-06-10 15:53'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 240000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update issue API error: GitHub API authentication failed (PATCH https://api.github.com/repos/NVIDIA-Omniverse/trickle/issues/225). Check OOMPAH_GITHUB_TOKEN, OOMPAH_GITHUB_APP_ID, or run 'gh auth login'.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: backlog
- tracker_kind: backlog
- fingerprint: fba456b883c4aa56
- dedup_fingerprint: fba456b883c4aa56
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed GitHub issue status updates so terminal/open state and oompah status labels are patched together. A rejected GitHub PATCH now fails without first mutating labels, preventing Done labels from being left on still-open issues.
<!-- SECTION:FINAL_SUMMARY:END -->
