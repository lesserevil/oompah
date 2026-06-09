---
id: TASK-496
title: Clear stale epic alerts when epics leave active candidates
status: Done
assignee:
  - oompah
created_date: '2026-06-09 19:54'
updated_date: '2026-06-09 20:05'
labels: []
dependencies: []
priority: high
ordinal: 212000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stale epic alerts remain visible after an epic PR has merged and the epic drops out of active candidates. _prune_stale_epic_rebase_states() prunes rebase state for inactive epics but does not clear epic_stale:<id> alerts, so the dashboard can keep showing false rebase-required alerts for merged epics. Clear the matching epic_stale alert whenever an epic is pruned from active rebase tracking, and cover this with a regression test.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 19:54
---
Understanding: stale epic alerts are stored in orchestrator._alerts and keyed as epic_stale:<id>. _check_epic_staleness() skips terminal epics, while _prune_stale_epic_rebase_states() only removes _epic_rebase_states entries. That leaves alert entries for epics that have merged or otherwise left the active candidate set. I will clear the matching alert as part of pruning inactive epic rebase state and add a regression test.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Cleared matching epic_stale alerts when stale epic rebase state is pruned for terminal or inactive epics. Added regression coverage proving pruned epic alerts are removed while active epic alerts and unrelated alerts remain.
<!-- SECTION:FINAL_SUMMARY:END -->
