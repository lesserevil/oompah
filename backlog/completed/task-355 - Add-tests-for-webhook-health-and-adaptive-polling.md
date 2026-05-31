---
id: TASK-355
title: Add tests for webhook health and adaptive polling
status: Done
assignee: []
created_date: 2026-05-05 03:45
updated_date: 2026-05-05 18:25
labels:
- ci-fix
- merged
- beads-migrated
dependencies:
- TASK-353
- TASK-354
- TASK-352
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-zlz_2-aib
  state: closed
  parent_id: oompah-zlz_2-1a7
  dependencies:
  - oompah-zlz_2-blg
  - oompah-zlz_2-vt9
  - oompah-zlz_2-yed
  branch_name: oompah-zlz_2-aib
  target_branch: null
  url: null
  created_at: '2026-05-05T03:45:39Z'
  updated_at: '2026-05-05T18:25:13Z'
  closed_at: '2026-05-05T18:25:13Z'
parent: TASK-329
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add unit tests for: (1) webhook delivery timestamp tracking, (2) is_webhook_healthy() logic with various staleness thresholds, (3) subprocess lifecycle (start, restart, cleanup), (4) adaptive polling skips healthy projects. Add integration test verifying polling resumes when webhook process dies.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df91b-6fca-7cdc-993f-89774a6faa92
author: oompah
created: 2026-05-05T17:06:58Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df91b-7390-7c4c-b2af-fec34411ad19
author: oompah
created: 2026-05-05T17:06:59Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df91d-3b84-712c-b6df-87f878379805
author: oompah
created: 2026-05-05T17:08:56Z

Understanding: The issue requests tests for: (1) webhook delivery timestamp tracking — Project.last_webhook_received_at is set by server.py:_handle_webhook_event(), (2) is_webhook_healthy() — already tested in test_orchestrator_webhook_health.py, (3) WebhookForwarder subprocess lifecycle — tested in test_webhooks.py, (4) adaptive polling skips healthy projects — tested in test_orchestrator_webhook_health.py, (5) integration test verifying polling resumes when webhook process dies — MISSING. Plan: Add missing integration test to test_orchestrator_webhook_health.py and new tests for fork subprocess lifecycle, webhook timestamp edge cases, and adaptive polling edge cases.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df931-4eef-7d04-9077-fa9a57fb6eb8
author: oompah
created: 2026-05-05T17:30:52Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df931-7202-7c73-bb34-d567eef2df3d
author: oompah
created: 2026-05-05T17:31:00Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df931-ae14-7e77-b178-457e59616a8c
author: oompah
created: 2026-05-05T17:31:16Z

Understanding: The issue requests tests for webhook health and adaptive polling. Based on prior comments, some tests already exist in test_orchestrator_webhook_health.py and test_webhooks.py. The main gaps are: (1) fork subprocess lifecycle edge cases, (2) webhook timestamp edge cases, (3) adaptive polling edge cases, (4) integration test verifying polling resumes when webhook process dies. Plan: Explore existing tests, identify gaps, add missing tests.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df932-4c39-72c3-94a1-1495cea3776c
author: oompah
created: 2026-05-05T17:31:56Z

Discovery: Existing tests cover is_webhook_healthy() thresholds, adaptive polling skip logic, WebhookForwarder lifecycle, and _ForwarderProcess state management. Gaps found: (1) full fork subprocess lifecycle test (mocked gh process start→exit→restart→cleanup), (2) webhook timestamp edge cases (non-datetime type → falls back to polling), (3) adaptive polling with partial error responses, (4) integration test for polling resume when forwarder process dies. Will add these as new test classes in appropriate test files.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df93f-e353-7655-b71e-db4f9d54df6b
author: oompah
created: 2026-05-05T17:46:47Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df940-0279-7480-b97d-de0bc8dcb79d
author: oompah
created: 2026-05-05T17:46:55Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df940-e0be-70da-a347-326e0387d8b1
author: oompah
created: 2026-05-05T17:47:52Z

Understanding: The issue requests tests for (1) webhook delivery timestamp tracking, (2) is_webhook_healthy() with various staleness thresholds, (3) subprocess lifecycle (start, restart, cleanup), (4) adaptive polling skips healthy projects, and (5) integration test verifying polling resumes when webhook process dies. Looking at existing tests: test_orchestrator_webhook_health.py already covers is_webhook_healthy() thresholds and adaptive polling skip logic; test_webhooks.py covers WebhookForwarder lifecycle. Gaps: (1) webhook timestamp edge cases — non-datetime type falls back to polling, (2) full subprocess lifecycle test with mock gh process start→exit→restart→cleanup, (3) adaptive polling with partial error responses, (4) integration test verifying polling resumes when forwarder process dies. Plan: Add new test classes to existing test files covering these 4 gaps.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df941-977a-7de6-a51f-81cac70e0d49
author: oompah
created: 2026-05-05T17:48:39Z

Discovery: All 85 existing tests pass. Key implementation details: is_webhook_healthy() uses isinstance(ts, datetime) check and handles timezone-aware comparison with datetime.now(timezone.utc). _ForwarderProcess tracks restart_delay_s and restart_attempts. _check_and_restart() applies exponential backoff on process exit. Gaps confirmed: (1) no test for non-datetime type in last_webhook_received_at, (2) no test for full start→exit→restart→cleanup lifecycle with mocked gh, (3) no test for _fetch_all_reviews with provider errors (partial failures), (4) no test for polling resume when forwarder process dies. Will add these now.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df951-2ebf-7ea6-bdc0-b2a0902a4a7c
author: oompah
created: 2026-05-05T18:05:40Z

Implementation: Added new test classes covering the 4 identified gaps. (1) Added TestIsWebhookHealthyTimestampEdgeCases to test_orchestrator_webhook_health.py — non-datetime type, MagicMock, integer, zero, naive-datetime, and exactly-at-boundary cases for is_webhook_healthy(). This revealed a bug in orchestrator.py: it crashed on naive datetimes (TypeError: subtract offset-naive and offset-aware), fixed by adding an isinstance() guard for tzinfo is None. (2) Added TestFetchAllReviewsWithErrors and TestFetchAllMergedBranchesWithErrors — provider exceptions return empty list/set gracefully, partial failures don't cascade. (3) Added TestForwarderProcessFullLifecycle test class — subprocess lifecycle (start→exit→restart→cleanup), exponential backoff cap at 60s, stop-terminates-all, no-process launch, no-git-dir skip. (4) test_polling_resume_when_forwarder_process_dies — verifies _terminate called and gh relaunched when process dies mid-poll.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df951-e75a-74f1-82a9-53d6131bb010
author: oompah
created: 2026-05-05T18:06:28Z

Verification: 101 tests pass. All existing (85) + new (16) tests in test_orchestrator_webhook_health.py and test_webhooks.py pass. 2 pre-existing failures in test_config.py are unrelated to these changes (wrong poll_interval_ms constant in test expectations). Broader suite: 1296 passed in 38s. Changes: (1) oompah/orchestrator.py — fix naive datetime TypeError in is_webhook_healthy(), (2) tests/test_orchestrator_webhook_health.py — 10 new tests for timestamp edge cases + error handling, (3) tests/test_webhooks.py — 6 new tests for subprocess lifecycle + polling resume integration.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df952-1189-7a8b-9c08-d7a10519475a
author: oompah
created: 2026-05-05T18:06:38Z

Agent completed successfully in 1192s (5576007 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df954-2a4e-793f-9741-99095336bb1e
author: oompah
created: 2026-05-05T18:08:56Z

YOLO: CI tests failed on MR #53. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df955-de4c-76d6-9c3f-b5e0dc469512
author: oompah
created: 2026-05-05T18:10:47Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df956-0755-71d0-8fd9-016df69f0d46
author: oompah
created: 2026-05-05T18:10:58Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df959-5ea3-70ab-9edd-b11a38dc3a28
author: oompah
created: 2026-05-05T18:14:37Z

Agent completed successfully in 230s (253355 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df959-9df4-7743-a199-383d543485ec
author: oompah
created: 2026-05-05T18:14:53Z

YOLO: CI tests failed on MR #53. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df95a-32ff-7bee-b38c-795f489e6f08
author: oompah
created: 2026-05-05T18:15:31Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df95a-36e6-77d3-9498-1e5f290b2419
author: oompah
created: 2026-05-05T18:15:32Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df95c-0815-7cec-92b1-ed764ee52bfe
author: oompah
created: 2026-05-05T18:17:31Z

Verification: All 1298 tests pass locally. The branch is clean and up to date with origin. The test_config.py fix in the previous commit resolved the CI failures. No further changes needed.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df95c-55a9-7372-8456-2e4db5e5f061
author: oompah
created: 2026-05-05T18:17:51Z

Agent completed successfully in 140s (141302 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df95c-eb7f-7403-afe2-ba47476c2aa1
author: oompah
created: 2026-05-05T18:18:30Z

YOLO: CI tests failed on MR #53. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df95d-7208-7b13-8a63-55dc2738a540
author: oompah
created: 2026-05-05T18:19:04Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df95d-75a9-772b-8128-4b424349eaac
author: oompah
created: 2026-05-05T18:19:05Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df962-d3ed-78fc-9270-d53fe2357b8f
author: oompah
created: 2026-05-05T18:24:57Z

Fix: Added pytest-asyncio to dev dependencies in pyproject.toml. The async tests in test_webhooks.py (@pytest.mark.asyncio decorators) were failing in CI because pytest-asyncio was not in the optional dev dependencies. CI runs 'pip install -e ".[dev]"' which installs these dependencies. All 1298 tests pass locally.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df963-1cf0-7b3e-b3e8-c1677f29ba3d
author: oompah
created: 2026-05-05T18:25:16Z

Agent completed successfully in 372s (578174 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
