---
id: TASK-398
title: Make service start reliably detach in noninteractive shells
status: In Progress
assignee: []
created_date: '2026-06-01 16:07'
updated_date: '2026-06-02 02:00'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding: Two bugs in Makefile. (1) start target uses bare & - in noninteractive shell, parent exit sends SIGHUP to process group killing child. Fix: use setsid with stdin from /dev/null. (2) PORT var uses env var only, not .env file, so make status shows wrong port. Fix: grep .env for OOMPAH_SERVER_PORT as fallback.

Discovery: Root cause confirmed in Makefile. (1) start target: bare '&' backgrounding leaves child in parent process group — SIGHUP from shell exit kills it. Upstream had setsid/nohup conditional but was missing </dev/null stdin redirect. (2) PORT variable only reads OOMPAH_SERVER_PORT from shell env, not .env file. Fix: added _ENV_PORT shell grep and </dev/null to both setsid and nohup branches. Tests updated in tests/test_makefile_setup.py.
<!-- SECTION:NOTES:END -->
