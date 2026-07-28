---
id: OOMPAH-491
type: feature
status: In Progress
priority: 1
title: Block network Git remotes during pytest sessions
parent: OOMPAH-490
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- needs:feature
assignee: null
created_at: '2026-07-28T13:53:26.578514Z'
updated_at: '2026-07-28T14:37:40.192519Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 504c86b2-5f4c-4633-80da-9bd16c6f9c43
oompah.work_branch: epic-OOMPAH-490
---
## Summary

Implementation scope

Add a pytest-session safety barrier in `tests/conftest.py` that prevents any unmocked Git command from contacting a remote whose effective URL uses HTTP, HTTPS, SSH, SCP-style `user@host:path`, or the git protocol. Use process-local Git configuration/environment inherited by test subprocesses; do not edit the developer's global or repository Git config. Redirect forbidden URL prefixes to a deterministic nonexistent local path or an equivalent fail-fast local transport. Preserve any pre-existing `GIT_CONFIG_COUNT` entries instead of overwriting them. Absolute paths and temporary `file://` bare remotes must remain usable because state-branch and migration tests depend on them. Document an explicit, narrowly scoped opt-out only if a test has a proven local transport that the guard misclassifies; no test may opt out for public network access.

Tests

Add `tests/test_git_remote_safety.py`. Prove HTTPS, HTTP, SSH URL, SCP-style, and git-protocol remotes fail without DNS/network access; prove an absolute-path bare remote and a temporary `file://` remote can fetch and push; prove existing numbered Git config environment entries survive. Run the new tests and representative local-remote tests from `test_project_bootstrap_state_branch.py` and `test_state_branch_e2e.py`.

Acceptance criteria

Running pytest cannot contact or push to a public/private network Git remote, local bare-remote coverage still passes, the guard changes no persistent Git configuration, and failures identify the blocked URL and explain that tests must inject a local remote or mock the Git boundary.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 14:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 14:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 14:35
---
Understanding: I will screen OOMPAH-491 for duplicates before any implementation by searching task records and project documentation for pytest Git remote/network safety work, then reading each plausible candidate's full description and comments. I will archive only on a confirmed scope match; otherwise I will record evidence and hand off for implementation.
---
author: oompah
created: 2026-07-28 14:37
---
Discovery: No duplicate found. Exact searches across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md found no prior GIT_CONFIG_COUNT, url.*.insteadOf, pytest-session Git network barrier, SCP-style blocking, or unmocked-Git safety work. Closest full tasks reviewed: OOMPAH-500 is the downstream final clean-checkout/no-network audit and explicitly depends on this guard; OOMPAH-492 isolates specific worker-exit/epic-rebase leaks rather than enforcing a suite-wide transport barrier; OOMPAH-281 provisions the CI runner; OOMPAH-203 concerns auto-update restarts after tracker writes. Parent OOMPAH-490 assigns the first suite-wide outbound-Git barrier uniquely to OOMPAH-491.
---
author: oompah
created: 2026-07-28 14:37
---
Focus handoff: duplicate_detector

1. Outcome: No confirmed duplicate; OOMPAH-491 should proceed to implementation.
2. Evidence: Searched task records and docs for Git remote/network safety, pytest-session guards, GIT_CONFIG_COUNT, url.*.insteadOf, SCP-style URLs, and unmocked Git. Read OOMPAH-490, OOMPAH-500, OOMPAH-492, OOMPAH-281, and OOMPAH-203 in full. OOMPAH-490 uniquely assigns the suite-wide barrier to this child; OOMPAH-500 validates it later, and OOMPAH-492 fixes specific leak sites.
3. Remaining work/risks: Implement the process-local inherited Git configuration in tests/conftest.py and tests/test_git_remote_safety.py. Preserve numbered Git config entries, allow absolute paths and temporary file:// remotes, block HTTP/HTTPS/SSH/SCP/git transports fail-fast with actionable errors, and avoid persistent config changes. Verify representative state-branch local-remote tests.
4. Recommended next focus: feature (implementation), followed by test verification.
---
<!-- COMMENTS:END -->
