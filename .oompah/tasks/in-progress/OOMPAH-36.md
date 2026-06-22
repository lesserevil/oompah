---
id: OOMPAH-36
type: task
status: In Progress
priority: 1
title: Remove stale Backlog.md and beads instructions from docs and templates
parent: OOMPAH-32
children: []
blocked_by:
- OOMPAH-35
labels: []
assignee: null
created_at: '2026-06-22T01:17:28.394571Z'
updated_at: '2026-06-22T14:47:25.782295Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e5264c4b-aa04-4005-9a71-74f0014d0ca3
oompah.task_costs:
  total_input_tokens: 123
  total_output_tokens: 4541
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 123
      output_tokens: 4541
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 123
    output_tokens: 4541
    cost_usd: 0.0
    recorded_at: '2026-06-22T14:47:22.871315+00:00'
---
## Summary

Plan: plans/oompah-1.0-release.md#operator-and-project-documentation

WHAT TO DO
Remove or correct any remaining user-facing Backlog.md and beads instructions from current docs and bootstrap templates.

HOW TO VERIFY
Searches for Backlog.md, backlog, beads, and bd either find historical/internal migration notes only or current text explicitly saying they are unsupported.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 14:25
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 14:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 14:32
---
Understanding: OOMPAH-36 is NOT a duplicate — no other task covers removing stale beads/Backlog.md instructions from docs and templates. OOMPAH-35 (Done) covered writing the onboarding checklist; this task is about cleaning up stale instructions. Investigation found: (1) bootstrap templates (oompah/project_bootstrap/templates/__init__.py) are already clean; (2) agent_instructions.py templates are clean; (3) user-facing docs in docs/ are clean; (4) plans/oompah-1.0-release.md references them correctly as historical/deprecated; (5) .gitignore/.gitattributes have infrastructure entries for .beads/ backward compat, with comments that reference 'bd init'/'bd bootstrap' but in explanatory context. The .gitattributes comment is outdated: it says oompah/projects.py calls _install_beads_merge_driver() but that function no longer exists. Plan: update .gitignore and .gitattributes comments to be clearly historical migration notes so all searches satisfy the HOW TO VERIFY criteria.
---
author: oompah
created: 2026-06-22 14:37
---
Discovery: Confirmed this is NOT a duplicate. Investigation summary: (1) bootstrap templates (oompah/project_bootstrap/templates/__init__.py) were already clean — no beads/Backlog.md references; (2) agent_instructions.py templates were already clean; (3) all docs in docs/ were clean; (4) plans/oompah-1.0-release.md correctly labels them as historical/deprecated; (5) .gitignore had operational beads comments referencing 'bd init' and 'bd bootstrap' that appeared instructional; (6) .gitattributes had incorrect docs claiming _install_beads_merge_driver() was auto-called (that function no longer exists). Changes needed: update .gitignore and .gitattributes comments to be clearly historical migration notes.
---
author: oompah
created: 2026-06-22 14:37
---
Implementation: Updated .gitignore and .gitattributes. In .gitignore: replaced 'Dolt database files (added by bd init)' and 'beads-jsonl-ignore (managed by oompah)' sections (which included 'emergency recovery via bd bootstrap') with a single 'Historical: Dolt/beads files from the old task tracker (pre-.oompah/tasks)' block explicitly saying 'beads and bd are no longer used'; did the same for .beads-credential-key. In .gitattributes: replaced the setup instructions (which incorrectly claimed _install_beads_merge_driver() auto-installs the driver) with a 'Historical: merge driver for the old beads issue store' note explicitly stating beads is no longer used and the driver is NOT installed automatically. All patterns retained for backward compat. No code changes needed — docs and templates were already clean.
---
author: oompah
created: 2026-06-22 14:47
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 81
- Tokens: 123 in / 4.5K out [4.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 21m 34s
- Log: OOMPAH-36__20260622T142553Z.jsonl
---
<!-- COMMENTS:END -->
