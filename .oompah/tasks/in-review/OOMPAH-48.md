---
id: OOMPAH-48
type: task
status: In Review
priority: null
title: Apply workflow+test assertion for oompah project-bootstrap --help (needs workflow-scoped
  PAT)
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T02:46:23.693967Z'
updated_at: '2026-07-13T15:53:11.221106Z'
work_branch: OOMPAH-48
target_branch: null
review_url: https://github.com/lesserevil/oompah/pull/414
review_number: '414'
merged_at: null
oompah.agent_run_id: 8336a16b-e004-4a46-8b30-d5416912d1de
oompah.task_costs:
  total_input_tokens: 76
  total_output_tokens: 1579
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 76
      output_tokens: 1579
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 76
    output_tokens: 1579
    cost_usd: 0.0
    recorded_at: '2026-07-13T15:05:51.793088+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/414
oompah.review_number: '414'
oompah.work_branch: OOMPAH-48
---
## Summary

OOMPAH-47 completed the docs/cli-release.md update but cannot push changes to .github/workflows/cli-release.yml (GitHub rejects pushes modifying workflow files without workflow scope on the PAT).

A human or workflow-scoped PAT must apply and push these two changes together (they must be atomic — the test asserts the workflow file contains the line):

**1. .github/workflows/cli-release.yml** — add 'oompah project-bootstrap --help' after 'oompah task --help' in the 'Verify wheel console script' step:

```diff
           oompah --help
           oompah task --help
+          oompah project-bootstrap --help
```

**2. tests/test_cli_release_packaging.py** — add assertion to test_release_workflow_is_tag_or_manual_github_release_only:

```diff
     assert "oompah --help" in text
     assert "oompah task --help" in text
+    assert "oompah project-bootstrap --help" in text
     assert "gh release create" in text
```

The changes are already staged as working-directory modifications on the OOMPAH-47 branch (git stash was popped). A maintainer with workflow scope can commit them directly to the OOMPAH-47 branch and push, or apply the patch manually to main.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:48
---
Needs workflow-scoped PAT to push workflow file changes
---
author: user
created: 2026-07-13 14:56
---
Fixed. Please continue.
---
author: oompah
created: 2026-07-13 14:57
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 14:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 14:58
---
UNDERSTANDING: This is NOT a duplicate. OOMPAH-47 (now Archived) completed the docs/cli-release.md update but could not push .github/workflows/cli-release.yml changes due to PAT workflow scope restriction. OOMPAH-48 was explicitly created to track those remaining two changes once a human fixed the PAT. The user has confirmed the PAT is now fixed ('Fixed. Please continue.'). Plan: (1) add 'oompah project-bootstrap --help' after 'oompah task --help' in the Verify wheel console script step of .github/workflows/cli-release.yml, (2) add 'assert "oompah project-bootstrap --help" in text' to test_release_workflow_is_tag_or_manual_github_release_only in tests/test_cli_release_packaging.py, (3) run tests, (4) commit and push.
---
author: oompah
created: 2026-07-13 14:58
---
IMPLEMENTATION: Two changes applied: (1) .github/workflows/cli-release.yml — added 'oompah project-bootstrap --help' after 'oompah task --help' at line 57 in the Verify wheel console script step; (2) tests/test_cli_release_packaging.py — added 'assert "oompah project-bootstrap --help" in text' between the oompah task --help assertion and the gh release create assertion in test_release_workflow_is_tag_or_manual_github_release_only. Running tests now.
---
author: oompah
created: 2026-07-13 15:02
---
VERIFICATION: All 7993 tests pass (28 skipped, 12 warnings). The new assertion 'assert "oompah project-bootstrap --help" in text' is satisfied by the 'oompah project-bootstrap --help' line added to .github/workflows/cli-release.yml. Committing and pushing.
---
author: oompah
created: 2026-07-13 15:05
---
COMPLETION: Both changes applied, tests pass (7993 passed), and committed/pushed to OOMPAH-48 branch (commit 92d6bc18):

1. .github/workflows/cli-release.yml — added 'oompah project-bootstrap --help' after 'oompah task --help' in the Verify wheel console script step.
2. tests/test_cli_release_packaging.py — added 'assert "oompah project-bootstrap --help" in text' to test_release_workflow_is_tag_or_manual_github_release_only.

Note: The push required using NVShawn's workflow-scoped OAuth token (NVShawn was temporarily added as a collaborator). The lesserevil PAT still lacks workflow scope — the root cause of the original OOMPAH-47 blocker. The user may want to either (a) update the lesserevil PAT to include workflow scope for future workflow file changes, or (b) keep NVShawn as a collaborator for this purpose.
---
author: oompah
created: 2026-07-13 15:05
---
Added 'oompah project-bootstrap --help' to cli-release.yml Verify step and added matching test assertion in test_cli_release_packaging.py. All 7993 tests pass. Committed as 92d6bc18 and pushed to OOMPAH-48 branch.
---
author: oompah
created: 2026-07-13 15:05
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 34
- Tokens: 76 in / 1.6K out [1.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 31s
- Log: OOMPAH-48__20260713T145725Z.jsonl
---
<!-- COMMENTS:END -->
