---
id: TASK-472.5
title: 'Validate multipart upload, static mount, and Jinja routes under Granian'
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:backend'
  - 'needs:test'
dependencies: []
parent_task_id: TASK-472
priority: medium
ordinal: 194000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Exercise the non-JSON routes under granian: the 3 UploadFile/multipart attachment endpoints, the /static StaticFiles mount, and the Jinja/HTML routes (cache-busting headers). Confirm parity with uvicorn.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Multipart uploads succeed under granian
- [ ] #2 /static assets and HTML routes serve with correct headers
<!-- AC:END -->
