---
id: TASK-334
title: '[backend:tracker] Failed to fetch candidates: bd command failed (exit 1):
  Error: no beads database found

  Hint: run ''bd where'' to inspect the resolved workspace, or ''bd init'' to create
  a new databas...'
status: Done
assignee: []
created_date: 2026-05-05 00:34
updated_date: 2026-05-05 01:19
labels:
- bug
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: bug
beads:
  id: oompah-zlz_2-uxx
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-uxx
  target_branch: null
  url: null
  created_at: '2026-05-05T00:34:30Z'
  updated_at: '2026-05-05T01:19:14Z'
  closed_at: '2026-05-05T01:19:14Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Failed to fetch candidates: bd command failed (exit 1): Error: no beads database found
Hint: run 'bd where' to inspect the resolved workspace, or 'bd init' to create a new database
      or set BEADS_DIR to point to your .beads directory
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df5a7-be03-7eb1-802c-5ed2cecfd14a
author: oompah
created: 2026-05-05T01:01:44Z

Mitigation landed: tracker.py now raises TrackerNotConfiguredError (subclass of TrackerError) when bd reports 'no beads database found', and short-circuits subsequent calls for 60s via an instance-level cache. The error is logged once per TTL window at WARNING (not ERROR), so error_watcher no longer auto-files duplicate beads for it. 5 duplicate beads (2lh, 33g, 51f, jqw, y3n) superseded by this one. Underlying issue remains: ~/.oompah/repos/trickle/.beads/ exists but has no DB. To fully resolve, either run 'bd init' in the trickle workspace or remove the trickle project from .oompah/projects.json. Keeping this bead open as the tracking record for the environmental fix; the noise itself is gone.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
