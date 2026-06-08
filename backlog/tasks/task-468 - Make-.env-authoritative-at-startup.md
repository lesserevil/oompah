---
id: TASK-468
title: Make .env authoritative at startup
status: Done
assignee: []
created_date: '2026-06-08 20:29'
updated_date: '2026-06-08 20:29'
labels:
  - bug
dependencies: []
priority: high
ordinal: 168000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Startup currently loads .env in no-override mode, so an inherited OOMPAH_* process environment can silently override values in .env. This caused OOMPAH_MAX_CONCURRENT_AGENTS=16 in .env to be ignored by a daemon started from an environment containing OOMPAH_MAX_CONCURRENT_AGENTS=5. Change startup loading so .env wins over inherited shell values, document the precedence, and cover the regression with tests.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed startup .env loading to override inherited process environment values, updated .env.example precedence docs, added regression coverage for OOMPAH_MAX_CONCURRENT_AGENTS, and isolated the quarantined-project dispatch test from live persisted service state. Verification: make test passed with 4733 tests.
<!-- SECTION:FINAL_SUMMARY:END -->
