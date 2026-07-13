---
id: OOMPAH-172
type: epic
status: In Progress
priority: 0
title: Implement queued release-branch addendums
parent: null
children:
- OOMPAH-173
- OOMPAH-174
- OOMPAH-175
- OOMPAH-176
- OOMPAH-177
- OOMPAH-178
- OOMPAH-179
- OOMPAH-180
- OOMPAH-181
- OOMPAH-182
- OOMPAH-183
- OOMPAH-184
- OOMPAH-185
blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-13T02:35:12.892610Z'
updated_at: '2026-07-13T07:06:07.813288Z'
work_branch: epic-OOMPAH-172
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/407
review_number: '407'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/407
oompah.review_number: '407'
oompah.work_branch: epic-OOMPAH-172
oompah.target_branch: main
oompah.agent_run_id: f808e288-e449-468b-9d16-3430c96bad7e
---
## Summary

Implement plans/release-branch-addendums.md. Replace new release-pick child tasks with durable, queueable release addendums attached to the original merged task or epic. Supported release lines are configured per project; approval of any task or epic merged to main immediately queues one addendum per selected supported release branch. Preserve an auditable task/branch view, migrate existing release-pick records safely, and retire the old child-backport workflow.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:38
---
Filed implementation children OOMPAH-173 through OOMPAH-184 from plans/release-branch-addendums.md, with scoped tests and acceptance criteria. OOMPAH-185 was immediately archived as a duplicate of OOMPAH-184.
---
author: oompah
created: 2026-07-13 07:00
---
YOLO: CI tests failed on MR #407. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-13 07:01
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-13 07:01
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-13 07:01
---
YOLO: CI tests failed on MR #407. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-13 07:02
---
Understanding: CI is failing on PR #407 (branch epic-OOMPAH-172) with 6 test failures in tests/test_granian_parity.py::TestMultipartAttachmentEndpoints. All failures show Granian returning 503 while uvicorn returns expected codes (400, 404, 500). Root cause: multipart attachment endpoints likely not registered in the Granian route set. Will investigate the granian parity test setup and the attachment route registration.
---
<!-- COMMENTS:END -->
