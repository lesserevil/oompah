---
id: TASK-385
title: 'Submit queue Step 3: soften _project_has_open_review to a configurable concurrency
  limit'
status: In Progress
assignee: []
created_date: 2026-05-05 20:04
updated_date: 2026-05-05 20:14
labels:
- feature
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: feature
beads:
  id: oompah-zlz_2-pt4
  state: in_progress
  parent_id: oompah-zlz_2-btf
  dependencies: []
  branch_name: oompah-zlz_2-pt4
  target_branch: null
  url: null
  created_at: '2026-05-05T20:04:28Z'
  updated_at: '2026-05-05T20:14:15Z'
  closed_at: null
parent: TASK-382
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace orchestrator.py:_project_has_open_review's binary "1 in flight or 0" gate with a configurable per-project `max_in_flight_prs` field. Default value 1 preserves today's behavior exactly. Operators opt up project-by-project once they've confirmed merge queue is reliable for that repo.

Today (orchestrator.py:1009):
```
if not is_p0 and self._project_has_open_review(issue.project_id):
    return _reject("open_review")
```

Becomes:
```
n_open = self._count_open_reviews(issue.project_id)
limit = self._project_max_in_flight(issue.project_id)
if not is_p0 and n_open >= limit:
    return _reject(f"open_reviews_at_cap={n_open}/{limit}")
```

Parent: oompah-zlz_2-btf.
Plan: docs/submit-queue.md (Step 3).
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df9c7-255e-7079-aea3-510e6e5ca28d
author: oompah
created: 2026-05-05T20:14:31Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9c7-488c-7d3e-a8fc-7b77f8f25594
author: oompah
created: 2026-05-05T20:14:40Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df9cd-49f3-7455-9820-ca2d75147a00
author: oompah
created: 2026-05-05T20:21:14Z

Understanding: This issue replaces the binary _project_has_open_review gate with a configurable per-project max_in_flight_prs field (default=1, preserving current behavior).

Changes needed:
1. oompah/models.py: Add max_in_flight_prs: int = 1 to Project dataclass; update to_dict/from_dict
2. oompah/projects.py: Add max_in_flight_prs to UPDATABLE_FIELDS
3. oompah/orchestrator.py: Add _count_open_reviews() and _project_max_in_flight() helpers; update _should_dispatch() to use them; keep _project_has_open_review as thin compat wrapper
4. oompah/server.py: Accept max_in_flight_prs in PATCH endpoint with validation (positive integer); expose per-project cap in /api/v1/state
5. oompah/templates/projects.html: Show max_in_flight_prs field with inline edit
6. docs/submit-queue.md: Update Step 3 doc to reflect actual field name used
7. tests/: Full test coverage including default=1, cap=3, P0 bypass, per-project independence
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
