---
id: TASK-398
title: Make service start reliably detach in noninteractive shells
status: Done
assignee: []
created_date: '2026-06-01 16:07'
updated_date: '2026-06-02 03:36'
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
No duplicate found. This was re-dispatched after the orchestrator reset the task file. Implementation already complete (commit f7ef5bb): (1) setsid+nohup with </dev/null stdin redirect for robust daemonization; (2) _ENV_PORT shell-grep for PORT fallback from .env. 6/6 makefile tests pass, 3568 total tests pass.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
No duplicate found. Implementation was already completed in a prior agent run (commit f7ef5bb). Two Makefile bugs fixed: (1) make start now uses setsid with </dev/null stdin redirect (nohup fallback also gets </dev/null), preventing immediate child exit when launched from noninteractive automation shells; (2) PORT variable reads OOMPAH_SERVER_PORT from .env via _ENV_PORT shell-grep, so make status and make graceful consistently report the actual configured port. Added regression tests test_make_start_uses_setsid_with_devnull_stdin and test_port_reads_from_dotenv_file_as_fallback. 6/6 Makefile tests pass; 3568 total tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
