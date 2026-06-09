---
id: TASK-481
title: Use project token for gh webhook forward
status: Done
assignee:
  - oompah
created_date: '2026-06-09 18:57'
updated_date: '2026-06-09 19:06'
labels: []
dependencies: []
priority: high
ordinal: 209000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: gh webhook forward subprocesses currently inherit the ambient gh CLI auth account. On hosts with multiple GitHub accounts, that can create 404/permission failures for repos owned by a different account even when the managed project has a valid access_token configured. Carry the project's access_token into WebhookForwarder process state and launch gh webhook forward with GH_TOKEN set for that process, while preserving the inherited environment for projects without a token. Add regression tests that assert GH_TOKEN is passed and never logged.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed WebhookForwarder to carry each project's configured access_token into the gh webhook forward subprocess via GH_TOKEN, while keeping tokens out of status snapshots and logs. The forwarder also refreshes process metadata when project settings change. Verified with focused webhook tests and full make test: 6251 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
