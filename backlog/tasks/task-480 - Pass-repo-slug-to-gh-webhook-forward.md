---
id: TASK-480
title: Pass repo slug to gh webhook forward
status: Done
assignee:
  - oompah
created_date: '2026-06-09 18:47'
updated_date: '2026-06-09 18:56'
labels: []
dependencies: []
priority: high
ordinal: 208000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: current gh-webhook extension exits immediately with 'Error: --repo or --org flag required' because WebhookForwarder launches 'gh webhook forward' with only --events and --url. This disables webhook-triggered refresh and leaves oompah relying on periodic polling. Extract the project repo slug and pass --repo owner/repo when launching each GitHub webhook forwarder. Add regression tests that assert --repo is present and that projects without a usable slug are skipped cleanly.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed WebhookForwarder to pass --repo owner/repo to gh webhook forward using each project's repo_url, and to skip projects whose repo slug cannot be determined. Added regression coverage for the subprocess args and missing-slug path. Verified with focused webhook tests and full make test: 6249 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
