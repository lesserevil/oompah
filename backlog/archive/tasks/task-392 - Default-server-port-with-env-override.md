---
id: TASK-392
title: Default server port with env override
status: Done
assignee:
  - oompah
created_date: '2026-06-01 03:12'
updated_date: '2026-06-01 03:26'
labels: []
dependencies: []
priority: medium
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Make oompah start the HTTP dashboard on port 8080 by default while allowing OOMPAH_SERVER_PORT to override or disable it.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented default HTTP dashboard port 8080 with OOMPAH_SERVER_PORT override/disable behavior, updated make start to stop forcing --port, refreshed docs, and added config/Makefile regression coverage. Verified with make test: 3916 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
