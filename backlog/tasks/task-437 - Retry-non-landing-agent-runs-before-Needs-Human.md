---
id: TASK-437
title: Retry non-landing agent runs before Needs Human
status: Done
assignee:
  - oompah
created_date: '2026-06-03 19:53'
updated_date: '2026-06-03 20:00'
labels: []
dependencies: []
priority: high
ordinal: 73000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Landing gate currently marks a task Needs Human immediately when an agent exits normally without closing and no commits landed on origin. Non-landing runs should stay in the retry/escalation pipeline and try stronger configured profiles before asking a human.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Updated the landing-gate path so normal exits with no landed commits stay in the retry/escalation pipeline. Added regression coverage that non-landing runs schedule an escalated retry instead of immediately moving to Needs Human.
<!-- SECTION:FINAL_SUMMARY:END -->
