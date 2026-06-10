---
id: TASK-498
title: Kill timed-out run_command process trees
status: Done
assignee:
  - oompah
created_date: '2026-06-10 01:14'
updated_date: '2026-06-10 01:41'
labels: []
dependencies: []
priority: high
ordinal: 216000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: ACP/tool run_command returns a timeout after 60s but can leave the subprocess or its children running with PPID 1. Observed 2026-06-10 with an agent pytest command continuing to burn CPU after the tool returned 'command timed out after 60s', which made the agent log popup and state API intermittently time out. run_command must launch commands in a killable process group/session and terminate the whole tree on timeout.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed ACP run_command execution to launch commands in a killable process session/process group and terminate the whole tree on timeout. Added a POSIX regression test proving a background child sleep is gone after timeout. Focused api-agent and retry tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->
