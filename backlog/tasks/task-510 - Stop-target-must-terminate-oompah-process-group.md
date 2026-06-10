---
id: TASK-510
title: Stop target must terminate oompah process group
status: Done
assignee:
  - oompah
created_date: '2026-06-10 10:46'
updated_date: '2026-06-10 10:48'
labels:
  - bug
dependencies: []
priority: high
ordinal: 236000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
make start launches oompah with setsid, so webhook forwarder subprocesses share the oompah process group. make stop currently kills only the parent PID, allowing gh webhook forward subprocesses to survive as orphans across restarts. Update stop to signal the process group with a PID fallback and add Makefile regression coverage.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated make stop to signal the setsid-created oompah process group before falling back to the parent PID, so gh webhook forward subprocesses do not survive restarts as orphans. Added Makefile regression coverage and verified with uv run pytest tests/test_makefile_restart_wait.py tests/test_makefile_setup.py -q plus a real make restart showing old forwarder PIDs no longer survive.
<!-- SECTION:FINAL_SUMMARY:END -->
