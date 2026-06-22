---
id: OOMPAH-52
type: task
status: In Progress
priority: null
title: Update oompah uv-tool install to include project-bootstrap support
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T14:20:20.212899Z'
updated_at: '2026-06-22T14:29:59.513318Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e966e93c-13b9-410c-bf38-578f33b8cda0
---
## Summary

Validation in OOMPAH-31 found that the oompah binary installed via 'uv tool install git+https://github.com/lesserevil/oompah' (/home/shedwards/.local/bin/oompah) is an older version that lacks project_bootstrap/ and project_bootstrap_cli.py. Running 'oompah project-bootstrap status .' fails with 'unrecognized arguments: status .' because the installed __main__.py does not have the project-bootstrap dispatch block.\n\nThe development version (python3 -m oompah) works correctly.\n\nAny operator who installed oompah before the project-bootstrap feature was added needs to reinstall:\n  uv tool upgrade oompah\n  # or\n  uv tool install --reinstall git+https://github.com/lesserevil/oompah\n\nThis should be called out in the release notes and operator runbook so operators know to reinstall after 1.0 ships.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

