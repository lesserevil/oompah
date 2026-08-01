---
id: OOMPAH-672
type: task
status: Backlog
priority: null
title: Preserve logging format placeholders during secret redaction
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T00:18:06.952783Z'
updated_at: '2026-08-01T00:18:06.952783Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Regression observed on the first production restart after OOMPAH-651 merged at main revision 72f8e7061ab5a6ae37b08b23c9e75190cf746a87. Startup logger.info calls such as 'HTTP Basic authentication enabled (htpasswd: %s)' emit 'TypeError: not all arguments converted during string formatting'. The SecretRedactionFilter rewrites record.msg so the sensitive-label rule replaces the %s placeholder with [REDACTED], while record.args remains populated; logging then formats a message with no placeholder against one argument. Implementation scope: update the centralized logging redaction boundary in oompah/secrets.py so percent-style and supported logging format placeholders retain valid message/argument arity while both format strings and values remain secret-safe; keep fail-closed behavior and process-wide plus handler/filter idempotency. Add regression tests using configured secret values and sensitive labels for tuple args, mapping args, repeated filter/factory passes, exceptions, and the real bootstrap/server htpasswd log messages. Assert no plaintext reaches formatted output and no logging error is written to stderr. Run focused redaction/logging tests and the full Makefile gate. Acceptance: startup logs render safely with [REDACTED], SecretRedactionFilter never causes logging formatting exceptions, all existing sentinel non-persistence guarantees remain intact, and restart remains healthy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

