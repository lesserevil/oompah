---
id: TASK-447
title: Show plain text thinking messages in agent log popup when verbose is off
status: Backlog
assignee: []
created_date: '2026-06-05 15:40'
labels: []
dependencies: []
priority: medium
ordinal: 83000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In the agent log popup, when verbose=off, include all non-empty plain text thinking messages in the visible log stream. Today these thinking messages are hidden along with verbose output. Acceptance criteria: non-empty plain text thinking messages are shown with verbose=off; empty thinking messages remain hidden; non-plain-text thinking payloads keep the existing filtering behavior; existing verbose=on behavior is unchanged; add focused test coverage for the filtering behavior.
<!-- SECTION:DESCRIPTION:END -->
