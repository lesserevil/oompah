---
id: OOMPAH-35
type: task
status: Done
priority: 1
title: Write the managed-project onboarding checklist
parent: OOMPAH-32
children: []
blocked_by:
- OOMPAH-31
labels: []
assignee: null
created_at: '2026-06-22T01:17:26.082104Z'
updated_at: '2026-06-22T14:25:40.230377Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d5c69a14-a12b-4408-b9b3-aa4efa82e353
---
## Summary

Plan: plans/oompah-1.0-release.md#operator-and-project-documentation

WHAT TO DO
Write the managed-project onboarding checklist for 1.0, including native tracker expectations, optional GitHub Issues intake, project bootstrap, AGENTS.md updates, and initial paused-project review.

HOW TO VERIFY
A new managed project can be added and reviewed while paused using the checklist.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 14:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-22 14:20
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 14:22
---
Understanding: OOMPAH-35 is NOT a duplicate. No existing onboarding checklist document exists under docs/ or plans/. The related tasks (OOMPAH-9 Merged, OOMPAH-31 Open validation, OOMPAH-36 stale-instruction cleanup) cover different scopes. OOMPAH-35 specifically requires a new user-facing doc at docs/managed-project-onboarding.md covering: (1) native tracker expectations, (2) optional GitHub Issues intake, (3) project bootstrap, (4) AGENTS.md updates, and (5) initial paused-project review. Plan: write the checklist drawing from native-markdown-tracker.md, github-issue-intake.md, project-bootstrap.md, and cli-install.md; commit and push on the OOMPAH-35 branch.
---
author: oompah
created: 2026-06-22 14:23
---
Discovery: No existing onboarding checklist found. Confirmed this is unique work. Will create docs/managed-project-onboarding.md as the new user-facing onboarding guide. Key sources: native-markdown-tracker.md (tracker layout and git-sync behavior), github-issue-intake.md (intake workflow), project-bootstrap.md (CLI and API apply flows), agent_instructions.py (oompah_md vs github_issues AGENTS.md content), operator-runbook.md (paused-project review process). The document will cover: (1) prerequisites and registration, (2) native tracker expectations, (3) optional GitHub Issues intake, (4) project bootstrap and AGENTS.md update, (5) initial paused-project review and unpause.
---
author: oompah
created: 2026-06-22 14:24
---
Implementation: Created docs/managed-project-onboarding.md (355 lines). The checklist covers all five required areas: (1) Prerequisites — service health, GitHub access, webhook extension; (2) Project registration paused via dashboard or API; (3) Native tracker expectations — .oompah/tasks layout, write behavior, initialization verification; (4) Optional GitHub Issues intake — enable, configure authorized actors, verify; (5) Project bootstrap and AGENTS.md — preview/apply CLI and API paths, what gets updated, dirty worktree safety; (6) Initial paused-project review — task queue, bootstrap status, service health checks, then unpause steps. Includes a Mermaid flow summary and a troubleshooting table.
---
author: oompah
created: 2026-06-22 14:25
---
Verification: docs/managed-project-onboarding.md committed (a5a19386) and pushed to origin/epic-OOMPAH-32. Document is 355 lines covering all six checklist sections. No code changes were made — this is a documentation-only deliverable, so no unit tests were needed. Cross-checked content against native-markdown-tracker.md, github-issue-intake.md, project-bootstrap.md, operator-runbook.md, and cli-install.md for accuracy. The checklist allows a new managed project to be added and reviewed while paused, satisfying the HOW TO VERIFY condition.
---
author: oompah
created: 2026-06-22 14:25
---
Completion: Created docs/managed-project-onboarding.md — the managed-project onboarding checklist for 1.0. The document walks operators through: (1) prerequisites, (2) registering a project in paused state, (3) native tracker expectations and verification, (4) optional GitHub Issues intake setup, (5) project bootstrap and AGENTS.md refresh, and (6) a systematic paused-project review before unpausing. Includes a Mermaid flow diagram and a troubleshooting table. Satisfies Epic D3 from plans/oompah-1.0-release.md. No duplicate found during investigation.
---
author: oompah
created: 2026-06-22 14:25
---
Created docs/managed-project-onboarding.md: the full managed-project onboarding checklist for 1.0, covering prerequisites, project registration (paused), native tracker expectations, optional GitHub Issues intake, project bootstrap and AGENTS.md update, and initial paused-project review before unpause. Satisfies Epic D3.
---
author: oompah
created: 2026-06-22 14:25
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 50
- Tokens: 83 in / 2.3K out [2.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 43s
- Log: OOMPAH-35__20260622T142100Z.jsonl
---
<!-- COMMENTS:END -->
