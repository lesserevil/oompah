# Terminal-State Mutations: Coordinator Allowlist

**Audience:** Developers implementing or extending oompah  
**Related:** `plans/terminal-transition-coordinator.md`, `docs/terminal-audit-enforcement-operations.md`

## Overview

Terminal-state mutations (Done, Merged, Archived) must go through the `TerminalTransitionCoordinator`. Direct calls to tracker terminal-mutation methods are blocked by static analysis and fail CI unless they are in the documented allowlist.

### Allowed Terminal-Mutation Methods

These tracker methods are permitted **only** when called from the coordinator or persistence layer:

| Method | Usage | Allowed Callers |
|--------|-------|-----------------|
| `tracker.close_issue(issue)` | Mark task Done | `TerminalTransitionCoordinator`, `TerminalAuditMetadata` |
| `tracker.archive_issue(issue)` | Mark task Archived | `TerminalTransitionCoordinator`, `TerminalAuditMetadata` |
| `tracker.set_status(issue, status="Done")` | Set terminal status | Coordinator/persistence boundary |
| `tracker.update_issue(issue, status="Done")` | Update terminal state | Coordinator/persistence boundary |

### Allowed Exception Paths

The following paths are exempt from the allowlist requirement:

1. **Unit tests**: Test files under `tests/` can call terminal mutations directly for testing purposes
   - Marked with `# pragma: no cover` or in test doubles
   - Example: Mock trackers in test files

2. **Static comparisons**: Reading or comparing terminal-state constants (not mutations)
   ```python
   # ✓ ALLOWED: Reading state constant
   if issue.state == "Done":
       ...
   
   # ✓ ALLOWED: Comparing with TargetState enum
   if target == TargetState.DONE:
       ...
   
   # ✗ BLOCKED: Calling mutation method
   if tracker.set_status(issue, "Done"):  # NOT ALLOWED outside allowlist
       ...
   ```

3. **Comment-justified deviations**: Code paths with explicit justification and PR review
   ```python
   # ALLOWLISTED: Used during bootstrap to apply persisted terminal state
   # See OOMPAH-466 for context
   tracker.set_status(issue, status="Done", metadata=audit_result)
   ```

### Current Exact Exceptions

The scanner allowlist is keyed by file, qualified function, and mutation
method—not by whole module. The current compatibility exceptions are:

| Call site | Method | Rationale |
|-----------|--------|-----------|
| `ErrorWatcher.auto_close_for_issue` | `close_issue` | Closes an oompah-generated transient diagnostic only after its originating retry succeeds |
| `OompahMarkdownTracker.archive_issue` | `update_issue` | Implements the low-level tracker persistence boundary for Archived |
| `Orchestrator._reset_orphaned_in_progress` | `update_issue` | Reasserts Done only for an issue already recorded in the completed set |
| `Orchestrator._defer_review_handoff` | `update_issue` | Preserves completed work while review creation waits for capacity |
| `Orchestrator._mark_stale_in_review_done` | `update_issue` | Uses Git containment evidence for shared epic-child work |
| `Orchestrator._on_worker_exit` | `close_issue` | Compatibility close after a merge-conflict repair gate succeeds |
| `TerminalTransitionCoordinator._apply_result_locked` | `update_issue` | Applies a validated and persisted audit result |
| `TerminalTransitionCoordinator._override_transition_locked` | `update_issue` | Applies a validated project-owner override |

Each production exception carries a `TERMINAL-AUDIT-ALLOW` source comment
where a statically identifiable call currently exists. Adding a second call
in one of these functions still fails, unless its exact key is reviewed and
added deliberately.

## Static Analysis

A CI check (`make test` gate) scans all Python code for disallowed terminal-mutation calls.

### Running the Scanner Locally

```bash
# Run all tests (includes static analysis)
make test

# Run only the static analysis check
python -m pytest tests/test_terminal_audit_scanner.py -v

# Scan a specific file
python scripts/find_terminal_mutations.py src/my_module.py
```

### Scanner Output

**Allowed usage**:

```bash
$ python scripts/find_terminal_mutations.py oompah/terminal_transition_coordinator.py
# No output; exits with code 0 (allowed)
```

**Disallowed usage**:

```bash
$ python scripts/find_terminal_mutations.py oompah/bad_module.py
ERROR: oompah/bad_module.py:42 - Disallowed terminal mutation: tracker.close_issue()
  This method must be called from TerminalTransitionCoordinator or auditor.
  See docs/terminal-state-coordinator-allowlist.md

Found 1 violation(s); failing CI.
```

## Adding New Terminal Mutations

If you need to call a terminal-mutation method in a new code path:

### Option 1: Coordinator Integration (Recommended)

Call the coordinator instead of calling the tracker directly:

**Before** (not allowed):

```python
def my_feature():
    if should_close:
        tracker.close_issue(issue)  # ✗ BLOCKED
```

**After** (allowed):

```python
from oompah.terminal_transition_coordinator import TerminalTransitionCoordinator

async def my_feature(orchestrator):
    if should_close:
        result = await orchestrator.terminal_transition_coordinator.request_transition(
            current_issue=issue,
            requested_target=TargetState.DONE,
            trigger_identity=ContributorIdentity("my-feature"),
            project_context=...,
            evidence_fingerprint=...,
        )
        # Result includes audit_id, status, etc.
```

### Option 2: Add to Allowlist

If the call **must** be direct (e.g., new persistence layer), add to the allowlist:

1. **Update the scanner configuration** (`oompah/terminal_mutation_scanner.py`):

```python
ALLOWLISTED_CALLS = {
    (
        "oompah/my_new_module.py",
        "MyClass.replay_audit_result",
        "update_issue",
    ): "Applies a previously validated and persisted audit result.",
}
```

2. **Justify in a comment**:

```python
# oompah/my_new_module.py

# ALLOWLISTED: Terminal mutation during persistence recovery
# See OOMPAH-500 for rationale: This module replays persisted audit results
# after a crash, applying the audited terminal status without re-auditing.
tracker.set_status(issue, status="Done", metadata=audit_result)
```

3. **Add a test** to verify the allowlist entry:

```python
# tests/test_terminal_audit_scanner.py

def test_allowlisted_module_is_scanned_and_approved(tmp_path):
    """Verify oompah.my_new_module is in the allowlist."""
    code = inspect.getsource(my_new_module)
    results = scan_for_terminal_mutations(code)
    # Results should be empty or marked as justified
    assert len(results) == 0
```

4. **Open a PR and request review** from the owner (see `CODEOWNERS`)

## Examples

### Example 1: Blocking a Direct Mutation

**Code**:

```python
# oompah/bad_example.py

def publish_release():
    issue = tracker.fetch_issue("RELEASE-123")
    tracker.close_issue(issue)  # ✗ BLOCKED
```

**CI Output**:

```
FAILED tests/test_terminal_audit_scanner.py::test_no_unauthorized_terminal_mutations
ERROR: oompah/bad_example.py:5 - close_issue() called outside allowlist
  File: oompah/bad_example.py
  Line: 5
  Method: close_issue()
  Allowed callers: TerminalTransitionCoordinator, auditor
  
  Fix: Use TerminalTransitionCoordinator.request_transition() instead.
```

**Fix**:

```python
# oompah/good_example.py

async def publish_release(orchestrator):
    issue = tracker.fetch_issue("RELEASE-123")
    
    # Use coordinator instead of direct mutation
    result = await orchestrator.terminal_transition_coordinator.request_transition(
        current_issue=issue,
        requested_target=TargetState.DONE,
        trigger_identity=ContributorIdentity("publish-release"),
        project_context=orchestrator.project_context(),
        evidence_fingerprint=EvidenceFingerprint.from_evidence(
            requirements_text="Release published",
            project_id=orchestrator.project_id,
            task_id=issue.id,
        ),
    )
```

### Example 2: Justified Allowlist Entry

**Code**:

```python
# oompah/terminal_audit_metadata.py

def apply_audit_result(issue, result):
    """Apply an audit result to the tracker (persistence layer).
    
    ALLOWLISTED: Terminal mutation during audit result application.
    Rationale (OOMPAH-466): This is called by the coordinator after an auditor
    verdict is successfully validated. The verdict itself was computed by an
    independent auditor and persisted ddurably. Applying the result here is
    safe and atomic—it is the persistence layer's responsibility to turn an
    audited verdict into reality.
    
    See plans/terminal-transition-coordinator.md § Result Application.
    """
    tracker.set_status(issue, status=result.target_status)
```

**CI Output**:

```
PASSED tests/test_terminal_audit_scanner.py::test_no_unauthorized_terminal_mutations

Scanned 1 terminal mutation in allowlisted path:
  oompah/terminal_audit_metadata.py:42 - set_status() — justified (OOMPAH-466)
```

### Example 3: Test File (Exempt)

**Code**:

```python
# tests/test_auditor.py

def test_auditor_applies_verdict():
    """Test that auditor applies a passing verdict."""
    mock_tracker = MockTracker()
    issue = Issue(id="TEST-1", state="In Validation")
    
    auditor.apply_audit_result(
        tracker=mock_tracker,
        issue=issue,
        verdict=AuditResult(...),
    )
    
    assert mock_tracker.set_status.called_with(issue, "Done")
```

**CI Output**:

```
PASSED tests/test_terminal_audit_scanner.py::test_no_unauthorized_terminal_mutations

Excluded from allowlist check: tests/test_auditor.py (test file)
```

## CI Integration

The terminal-mutation allowlist is checked as part of the branch gate:

```makefile
# Makefile

test: test-setup terminal-audit-scan

terminal-audit-scan:
	$(PYTHON) scripts/find_terminal_mutations.py oompah
```

**Failure prevents merge**:

```bash
$ make test
...
FAILED tests/test_terminal_audit_scanner.py::test_no_unauthorized_terminal_mutations
ERROR: Found 1 unauthorized terminal mutation(s)
make: *** [test] Error 1
```

## Review Checklist

When you need to add a terminal mutation, use this checklist:

- [ ] **Consider using the coordinator** instead of direct mutation
  - [ ] Can you call `TerminalTransitionCoordinator.request_transition()`?
  - [ ] Does the code have access to orchestrator?
  - [ ] Can you compute the evidence fingerprint?

- [ ] **If direct mutation is necessary**:
  - [ ] Is there a strong technical reason (document it)
  - [ ] Can you add to the allowlist?
  - [ ] Can you add a test?

- [ ] **For allowlist additions**:
  - [ ] Reference the issue (e.g., OOMPAH-466)
  - [ ] Add comment explaining why direct mutation is needed
  - [ ] Update `ALLOWLISTED_CALLS` in scanner config
  - [ ] Add a test to verify the entry
  - [ ] Request review from CODEOWNERS

- [ ] **Test locally**:
  ```bash
  make test -- tests/test_terminal_audit_scanner.py -v
  ```

## Glossary

| Term | Definition |
|------|-----------|
| **Terminal mutation** | Direct call to `close_issue()`, `archive_issue()`, or `set_status(..., status="Done")` |
| **Allowlist** | Set of modules/functions permitted to call terminal mutations |
| **Coordinator** | `TerminalTransitionCoordinator` — the only approved entry point for terminal-state transitions |
| **Justified deviation** | Terminal mutation outside allowlist with documented reason and PR review |
| **Scanner** | Static analysis tool that finds disallowed terminal mutations in CI |

## See Also

- `plans/terminal-transition-coordinator.md` — Coordinator design and API
- `plans/terminal-audit-enforcement.md` — Enforcement and bypass detection
- `oompah/terminal_mutation_scanner.py` — Scanner and exact-call allowlist
- `tests/test_terminal_audit_scanner.py` — Scanner regression and repository guard
- `scripts/find_terminal_mutations.py` — Standalone scanner CLI used by Make
- `CODEOWNERS` — Code review owners for allowlist changes
