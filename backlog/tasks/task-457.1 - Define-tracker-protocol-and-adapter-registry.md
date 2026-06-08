---
id: TASK-457.1
title: Define tracker protocol and adapter registry
status: In Progress
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-08 18:40'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies: []
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/tracker.py
  - oompah/orchestrator.py
  - oompah/config.py
parent_task_id: TASK-457
priority: high
ordinal: 109000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduce a typed tracker protocol or abstract base for all operations used by server, orchestrator, watchers, prompts, and attachments. Add an adapter registry so tracker.kind resolves to a concrete factory instead of hard-coded BacklogMdTracker construction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Protocol includes issue fetch/create/update/comment/label/dependency/metadata/cache operations used by oompah.
- [ ] #2 Unknown tracker.kind values still fail validation with clear errors.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 18:25
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 18:27
---
Understanding: No duplicate found. TASK-402.x removed Beads and locked to BacklogMdTracker. TASK-457.1 is the next step: introduce a TrackerProtocol (typed abstract base / Protocol class) covering all operations used across server, orchestrator, watchers, prompts, and attachments, plus an adapter registry so tracker.kind in config resolves to a concrete factory. This enables GitHub Issues (TASK-458+) without hard-coding BacklogMdTracker everywhere. Plan: (1) survey all tracker operations in oompah/tracker.py, oompah/orchestrator.py, oompah/server.py, etc.; (2) define TrackerProtocol and ADAPTER_REGISTRY; (3) make BacklogMdTracker the sole registered factory under 'backlog'; (4) validate unknown kinds with clear errors; (5) tests.
---

author: oompah
created: 2026-06-08 18:31
---
Discovery: Surveyed all tracker usages across orchestrator.py, server.py, error_watcher.py. BacklogMdTracker is imported directly in orchestrator.py (type hints + construction), error_watcher.py (type hints + isinstance guard). The protocol needs ~25 methods. ADAPTER_REGISTRY will map 'backlog_md' to a factory function. config.py validate_dispatch_config hardcodes the 'backlog_md' check - will switch to registry lookup. error_watcher.py uses isinstance(tracker, BacklogMdTracker) as a guard for git-persistence - will keep this as a runtime check (protocol-unaware) while changing type annotation to TrackerProtocol. No circular import risks found.
---

author: oompah
created: 2026-06-08 18:40
---
Implementation: (1) Added TrackerProtocol (@runtime_checkable Protocol) to oompah/tracker.py with all 27 operations used by server, orchestrator, watchers, prompts and attachments. (2) Added TrackerFactory type alias and ADAPTER_REGISTRY dict mapping 'backlog_md' to _backlog_md_factory; third-party adapters can extend the dict at import time. (3) Updated oompah/config.py validate_dispatch_config to use ADAPTER_REGISTRY for validation - unknown kinds now produce error mentioning registered adapters. (4) Updated oompah/orchestrator.py: imported TrackerProtocol and ADAPTER_REGISTRY, changed _new_tracker to use registry factory, updated all type annotations from BacklogMdTracker to TrackerProtocol. (5) Updated oompah/error_watcher.py: changed type annotations to TrackerProtocol, kept isinstance(tracker, BacklogMdTracker) runtime guard in _persist_error_task_to_git. (6) Created tests/test_tracker_protocol.py with 19 tests covering protocol conformance, registry content, factory behavior, and config validation.
---
<!-- COMMENTS:END -->
