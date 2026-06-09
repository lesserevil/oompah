---
id: TASK-470
title: Explain actionable alerts in the UI
status: Done
assignee:
  - oompah
created_date: '2026-06-08 23:52'
updated_date: '2026-06-08 23:59'
labels: []
dependencies: []
priority: high
ordinal: 176000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The dashboard currently surfaces alerts without enough explanation or remediation context. Update alert rendering so every visible alert includes its title, detail/explanation, source when useful, and clear remediation context/action when the service has already filed or can deal with it (for example stale epic rebase alerts). Add test coverage for the rendered explanation/action text.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated dashboard alert rendering so non-credential alerts show title, detail/explanation, action/remediation, and source context. Added stale epic alert remediation payloads, including failed/in-flight rebase states, plus dashboard and orchestrator tests.
<!-- SECTION:FINAL_SUMMARY:END -->
