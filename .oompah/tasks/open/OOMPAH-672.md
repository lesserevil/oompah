---
id: OOMPAH-672
type: task
status: Open
priority: null
title: Preserve logging format placeholders during secret redaction
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T00:18:06.952783Z'
updated_at: '2026-08-01T00:18:32.244661Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5f652cb7d6eca5414cb48d9d1f328cf08af6ba4d6f93a4585b29437504747aa3
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 0c1329bb-297a-4805-b748-5342edb022f6
  claim_owner: dd8a0ca0-c06e-4e9d-86a8-b69ebddec8d6
  claimed_at: '2026-08-01T00:18:26.187504+00:00'
  claim_expires_at: '2026-08-01T00:48:26.187504+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: b2f50d07-b637-4af3-aa0f-e3391b92c6b8
---
## Summary

Regression observed on the first production restart after OOMPAH-651 merged at main revision 72f8e7061ab5a6ae37b08b23c9e75190cf746a87. Startup logger.info calls such as 'HTTP Basic authentication enabled (htpasswd: %s)' emit 'TypeError: not all arguments converted during string formatting'. The SecretRedactionFilter rewrites record.msg so the sensitive-label rule replaces the %s placeholder with [REDACTED], while record.args remains populated; logging then formats a message with no placeholder against one argument. Implementation scope: update the centralized logging redaction boundary in oompah/secrets.py so percent-style and supported logging format placeholders retain valid message/argument arity while both format strings and values remain secret-safe; keep fail-closed behavior and process-wide plus handler/filter idempotency. Add regression tests using configured secret values and sensitive labels for tuple args, mapping args, repeated filter/factory passes, exceptions, and the real bootstrap/server htpasswd log messages. Assert no plaintext reaches formatted output and no logging error is written to stderr. Run focused redaction/logging tests and the full Makefile gate. Acceptance: startup logs render safely with [REDACTED], SecretRedactionFilter never causes logging formatting exceptions, all existing sentinel non-persistence guarantees remain intact, and restart remains healthy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 00:18
---
Filed from the production restart at 2026-08-01T00:15Z. The service recovered and is healthy; this is a nonfatal but real redaction-boundary regression. Opened for normal Oompah dispatch while direct operator work remains focused on OOMPAH-671 and the stranded Exocomp audits.
---
author: oompah
created: 2026-08-01 00:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 00:18
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
