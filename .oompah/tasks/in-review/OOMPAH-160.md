---
id: OOMPAH-160
type: bug
status: In Review
priority: null
title: Make native task writes atomic and block intake reimports for corrupt tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-29T14:46:06.483875Z'
updated_at: '2026-06-29T15:45:59.304035Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 402f1d0d-b767-4c2d-8e21-47d392862319
oompah.task_costs:
  total_input_tokens: 50
  total_output_tokens: 47913
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 50
      output_tokens: 47913
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 50
    output_tokens: 47913
    cost_usd: 0.0
    recorded_at: '2026-06-29T15:44:40.925616+00:00'
---
## Summary

Triggered by: TRICKLE-8

### Summary
Native oompah Markdown task writes should be atomic and GitHub intake should not recreate an already-imported issue just because the existing native task file is corrupt or unreadable.

### Problem
TRICKLE-8 was in progress on 2026-06-29 when the host had disk-full errors. The tracked file `.oompah/tasks/in-progress/TRICKLE-8.md` became a zero-byte file, causing the native tracker to skip it with `Missing YAML front matter`. Because the valid task was no longer visible to intake lookup, GitHub issue intake treated NVIDIA-Omniverse/trickle#268 as not imported and created a fresh Proposed `TRICKLE-8`, which then validated back to Backlog.

This caused an active task to disappear from the scheduler, terminate its running agent, and re-enter the intake flow as if it were new.

### Evidence
- `oompah.log` shows repeated warnings starting at 2026-06-29T14:23:40Z: `Skipping invalid native oompah task ... .oompah/tasks/in-progress/TRICKLE-8.md: Missing YAML front matter`.
- The current tracked `.oompah/tasks/in-progress/TRICKLE-8.md` in the trickle managed repo is zero bytes.
- Commit `822e8423` in the trickle managed repo both emptied the old in-progress TRICKLE-8 file and created a new `.oompah/tasks/proposed/TRICKLE-8.md`.
- Commit `0f1a5540` then moved the recreated task from Proposed to Backlog after validation passed.
- `oompah/oompah_md_tracker.py` currently writes task files with `path.write_text(...)`, which truncates the destination before the full replacement content is durable.

### Expected Behavior
A failed write must not corrupt or empty an existing task file. If a task file is corrupt or unreadable, GitHub intake should treat that as a repair/blocking condition for the existing task identity or external issue reference, not create a duplicate replacement task with the same identifier.

### Acceptance Criteria
- Native Markdown task writes use atomic replacement: write to a temporary file in the same directory, fsync where practical, then rename/replace the original only after the full payload is written.
- A regression test simulates a write failure and verifies the previous task file remains intact.
- GitHub intake duplicate detection/import lookup detects corrupt/unreadable native task files that match an existing task id or external GitHub issue metadata when possible, and does not create a duplicate task.
- When a corrupt native task file is found, oompah surfaces an actionable alert or moves the task to a repair flow instead of silently skipping it.
- Existing invalid zero-byte task files do not poison candidate selection or cause repeated intake reimports.
- Regression coverage includes the TRICKLE-8 failure mode: an in-progress task file becomes zero bytes, GitHub issue intake polls the same external issue, and no new Proposed task is created.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-29 15:26
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-29 15:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-29 15:27
---
Understanding: OOMPAH-160 is NOT a duplicate. Searched all merged/archived tasks for atomic writes, write_text, corrupt files, reimport, disk-full. OOMPAH-158 (Merged) fixed H2 heading parsing in intake import; OOMPAH-159 (Merged) added intake body normalization. Neither addresses write atomicity or corrupt-file reimport prevention. This is a new bug with two distinct fix areas: (1) oompah_md_tracker.py uses path.write_text() which truncates-before-write — must switch to write-to-tempfile + rename; (2) GitHub issue intake lookup skips corrupt/unreadable native task files and treats the external GitHub issue as unimported — must detect corrupt files and skip reimport. Plan: (1) explore oompah_md_tracker.py for write_text calls; (2) explore github_intake_bridge.py for existing import lookup; (3) implement atomic write helper; (4) add corrupt-file detection to intake lookup; (5) add alerting for corrupt files; (6) write regression tests including TRICKLE-8 failure mode.
---
author: oompah
created: 2026-06-29 15:35
---
Discovery: Root causes and affected code confirmed. (1) oompah/oompah_md_tracker.py:_write_markdown() uses path.write_text() which truncates-before-write — zero-byte file if disk fills. Fix: _atomic_write() helper using tempfile.mkstemp + Path.replace(). NOTE: Python 3.12 glob('*.md') includes dotfiles, so temp files must use '.tmp' not '.md' suffix. (2) _read_records() silently skips corrupt files — scheduler/intake lose the task. Fix: track corrupt stubs in _corrupt_stubs, improve log message with repair instructions. (3) _next_identifier() only scans valid records — corrupt file ID (TRICKLE-8) reused for new task. Fix: also scan all file stems. (4) _find_native_issue_for_external() in github_intake_bridge.py only checks valid tasks — corrupt file means external issue appears un-imported. Fix: add import-index file (.oompah/tasks/external-imports.yml) mapping external_id -> task_id, updated atomically on each import. When valid task lookup fails but index has a match AND the task file is corrupt, block reimport and log repair alert. (5) ensure_native_issue_for_github_issue() does not record in import index. Fix: call record_external_import() after creating a new task. Implementation plan: 13 changes to oompah_md_tracker.py + 2 changes to github_intake_bridge.py + regression tests.
---
author: oompah
created: 2026-06-29 15:43
---
Implementation: Changes delivered across 2 files + 2 test files. (1) oompah/oompah_md_tracker.py: Added _atomic_write() helper (tempfile.mkstemp → write → fsync → Path.replace), updated _write_markdown() to use it, updated _read_records() to track corrupt stubs with actionable repair log messages, updated invalidate_read_cache() to also clear corrupt stubs, added list_corrupt_stubs() public method, updated _next_identifier() to scan ALL file stems (not just valid records) preventing corrupt-file ID reuse (TRICKLE-8 root cause), added import-index support: _IMPORT_INDEX_FILE constant, _import_index_path property, _read_import_index(), record_external_import(), find_imported_task_id_for_external(). (2) oompah/github_intake_bridge.py: Updated _find_native_issue_for_external() to check import index + corrupt stubs after valid-task scan fails, returning (None, {_blocked_reimport: True}) when corrupt file detected. Updated ensure_native_issue_for_github_issue() to check _blocked_reimport sentinel (no new task created) and to call record_external_import() after successful creation. (3) 15 new tests in test_oompah_md_tracker.py: TestAtomicWrite (4), TestCorruptFileHandling (5), TestImportIndex (6). (4) 6 new tests in test_github_intake_bridge.py: TestCorruptFileDeduplication including TRICKLE-8 regression.
---
author: oompah
created: 2026-06-29 15:43
---
Verification: Full test suite passed. 7213 passed, 0 failed, 28 skipped. New tests: 21 total — 15 in test_oompah_md_tracker.py (TestAtomicWrite, TestCorruptFileHandling, TestImportIndex) and 6 in test_github_intake_bridge.py (TestCorruptFileDeduplication). Key results: (1) Atomic write — test_write_failure_leaves_original_file_intact verifies Path.replace failure does not corrupt original; test_write_does_not_use_md_suffix_for_temp_files verifies temp files use .tmp suffix. (2) Corrupt file handling — test_next_identifier_skips_corrupt_file_stem verifies TRICKLE-8 ID-reuse prevention; test_corrupt_file_appears_in_list_corrupt_stubs verifies corrupt detection. (3) Import index — test_record_external_import_creates_index_file, test_import_index_survives_task_file_corruption, test_index_file_is_written_atomically. (4) TRICKLE-8 regression — test_corrupt_task_file_blocks_reimport verifies in-progress file corruption + poll = no new Proposed task; test_poll_does_not_create_duplicate_when_task_is_corrupt verifies poll_github_issue_intake_project returns 0 imports; test_clean_reimport_allowed_when_task_file_deleted verifies clean-delete allows fresh import.
---
author: oompah
created: 2026-06-29 15:44
---
Completion: OOMPAH-160 delivered. All 5 acceptance criteria met: (1) Atomic writes — _write_markdown() uses tempfile + fsync + Path.replace; disk-full can no longer empty a task file. (2) Write failure regression test — test_write_failure_leaves_original_file_intact patches Path.replace to raise and verifies original unchanged. (3) Intake duplicate detection — _find_native_issue_for_external() checks import index + corrupt stubs; returns _blocked_reimport sentinel when corrupt file found; ensure_native_issue_for_github_issue() respects sentinel. (4) Corrupt file alerting — _read_records() logs repair instructions with git-show recovery command; list_corrupt_stubs() exposes them for callers. (5) TRICKLE-8 regression tests — test_corrupt_task_file_blocks_reimport + test_poll_does_not_create_duplicate_when_task_is_corrupt cover the exact failure mode. Zero-byte file ID no longer reused (_next_identifier scans all stems). Branch OOMPAH-160 pushed to origin. All 7213 tests pass.
---
author: oompah
created: 2026-06-29 15:44
---
Implemented atomic task writes (_atomic_write via tempfile+rename), corrupt file tracking (list_corrupt_stubs), ID-reuse prevention (_next_identifier scans all stems), external import index (record_external_import/find_imported_task_id_for_external), intake reimport blocking (_blocked_reimport sentinel). 21 regression tests. 7213/7213 tests pass.
---
author: oompah
created: 2026-06-29 15:44
---
Agent completed successfully in 1068s (47963 tokens)
---
author: oompah
created: 2026-06-29 15:44
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 97, Tool calls: 60
- Tokens: 50 in / 47.9K out [48.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 17m 48s
- Log: OOMPAH-160__20260629T152659Z.jsonl
---
author: oompah
created: 2026-06-29 15:44
---
Close refused by orchestrator: branch `OOMPAH-160` has 1 commit not on `main` and no open PR targets `main` from this branch.

Diagnostic:
  Unmerged commits: 1
    8b3b197c OOMPAH-160: Make native task writes atomic and block intake reimports for corrupt tasks
  Open PRs from this branch: 0
  Merged PRs from this branch: 0

Required: open a PR before closing.
  gh pr create --base main --head OOMPAH-160 --title "OOMPAH-160: Make native task writes atomic and block intake reimports for corrupt tasks" --body "..."

Task reopened. Re-dispatch on the next tick will see this comment in its prompt context.
---
author: oompah
created: 2026-06-29 15:45
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-06-29 15:45
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
