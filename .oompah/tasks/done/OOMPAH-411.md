---
id: OOMPAH-411
type: task
status: Done
priority: null
title: Unblock clean GitHub PRs with no CI checks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T21:26:04.166626Z'
updated_at: '2026-07-22T21:30:35.010887Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix YOLO review handling so a GitHub PR whose status and check-run APIs are successfully read but report no checks is classified as an explicit no-checks verdict and can be merged when clean. Preserve unknown CI as non-mergeable when status/check data is unavailable. Update CI status contracts and GitHub provider mapping as needed, add unit coverage for no-checks versus unavailable CI and an orchestrator regression proving a clean no-checks GitHub PR is merged, and run make test. Acceptance: PR #540-style clean no-checks reviews no longer remain In Review indefinitely; unknown/unavailable CI remains fail-safe.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 21:29
---
Implemented and pushed edf4bc481. GitHub now treats successfully observed zero status/check runs as CI-passed, while unavailable CI remains unknown. Added SCM and YOLO regression coverage. make test passed.
---
author: oompah
created: 2026-07-22 21:30
---
Classified successfully observed zero GitHub checks as CI-passed, added regressions, restarted the service, and verified YOLO merged PR #540.
---
<!-- COMMENTS:END -->
