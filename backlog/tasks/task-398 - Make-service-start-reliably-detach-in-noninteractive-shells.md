---
id: TASK-398
title: Make service start reliably detach in noninteractive shells
status: To Do
assignee: []
created_date: '2026-06-01 16:07'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
While restarting Oompah on 2026-06-01, the Makefile start target reported a PID but the child exited immediately after .env load when launched from a noninteractive automation shell. A setsid + redirected stdin launch survived and served 8090. Investigate whether make start should use a more robust daemonization pattern, and ensure make status reports the configured .env port consistently.
<!-- SECTION:DESCRIPTION:END -->
