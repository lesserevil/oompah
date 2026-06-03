---
id: TASK-398
title: Make service start reliably detach in noninteractive shells
status: Done
assignee: []
created_date: '2026-06-01 16:07'
updated_date: '2026-06-03 02:26'
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

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-03 02:22

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-03 02:25

Focus: Duplicate Investigator

Understanding: Searched for duplicates covering 'service start detach', 'setsid', 'daemonization', 'noninteractive shell', 'port status'. No prior task covers the same problem. TASK-392 covers port configuration defaults but not daemonization — different issue.

Discovery: The fix was already implemented in commit f7ef5bb by a prior agent pass. Makefile start target uses setsid+</dev/null stdin, and PORT variable reads OOMPAH_SERVER_PORT from .env as fallback. Two targeted tests in tests/test_makefile_setup.py (test_make_start_uses_setsid_with_devnull_stdin, test_port_reads_from_dotenv_file_as_fallback) cover both behaviors. All 6 tests in that file pass.

The task status was repeatedly reset to In Progress by the orchestrator re-dispatch cycle despite the implementation being complete. Closing permanently.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding: Two bugs in Makefile. (1) start target uses bare & - in noninteractive shell, parent exit sends SIGHUP to process group killing child. Fix: use setsid with stdin from /dev/null. (2) PORT var uses env var only, not .env file, so make status shows wrong port. Fix: grep .env for OOMPAH_SERVER_PORT as fallback.

Discovery: Root cause confirmed in Makefile. (1) start target: bare '&' backgrounding leaves child in parent process group — SIGHUP from shell exit kills it. Upstream had setsid/nohup conditional but was missing </dev/null stdin redirect. (2) PORT variable only reads OOMPAH_SERVER_PORT from shell env, not .env file. Fix: added _ENV_PORT shell grep and </dev/null to both setsid and nohup branches. Tests updated in tests/test_makefile_setup.py.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
No duplicate found. Implementation was already complete from prior agent pass (commit f7ef5bb): Makefile start target uses setsid+/dev/null stdin for reliable detach in noninteractive shells; PORT variable reads OOMPAH_SERVER_PORT from .env as fallback so make status reports the correct port. Tests: test_make_start_uses_setsid_with_devnull_stdin and test_port_reads_from_dotenv_file_as_fallback pass. Task was re-dispatched by orchestrator despite being done; closing permanently.
<!-- SECTION:FINAL_SUMMARY:END -->
