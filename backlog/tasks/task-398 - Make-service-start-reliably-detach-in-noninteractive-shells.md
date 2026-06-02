---
id: TASK-398
title: Make service start reliably detach in noninteractive shells
status: Done
assignee: []
created_date: '2026-06-01 16:07'
updated_date: '2026-06-02 03:15'
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

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed two Makefile bugs. (1) make start now redirects stdin from /dev/null in both the setsid and nohup branches, ensuring the child process does not inherit a closed/absent tty from a noninteractive automation shell - this was what caused immediate exit after .env load. (2) Added _ENV_PORT shell-grep so PORT falls back to OOMPAH_SERVER_PORT from .env when not exported in the shell environment, making make status and make graceful consistently report the actual configured port. Added two new regression tests: test_make_start_uses_setsid_with_devnull_stdin and test_port_reads_from_dotenv_file_as_fallback. All 6 makefile tests pass. This attempt #1 confirmed the implementation from the original run was correct; tests still pass.
<!-- SECTION:FINAL_SUMMARY:END -->
