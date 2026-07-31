# Candidate code sandbox isolation (OOMPAH-655)

## Problem

Branch code cannot be trusted to implement its own containment boundary. Candidate branches created before the OOMPAH-652 deployment may contain Makefiles or scripts that:
- Hard-code absolute paths like `.oompah.pid` and ignore `OOMPAH_PYTEST_GATE` environment variables
- Attempt to discover or signal the operator service on localhost:8090
- Read or write to operator state files
- Escape the test sandbox via symlinks or process signaling

When the orchestrator checks out an old branch, the operator service is exposed to code that predates the isolation contract.

## Solution

The quality gate enforces service isolation **outside and before** candidate code executes. Candidate Makefiles and scripts may evolve freely; the containment boundary is under operator control.

### Layers of isolation

#### 1. Git ancestry verification (preflight)

Before snapshot creation or OS sandbox setup, the gate checks that the branch contains the OOMPAH-652 safety head in its git ancestry:

```python
subprocess.run(
    ["git", "merge-base", "--is-ancestor", safety_head, "HEAD"],
    cwd=repo_path,
    capture_output=True,
    timeout=5,
)
```

Branches created before OOMPAH-652 are rejected with `needs_rebase` status **without executing any candidate code**. This prevents a non-cooperating Makefile from ever running.

**Why git ancestry is the enforcement boundary:**
- Cannot be spoofed by commit messages, marker strings, or Makefile text
- Is verified before any state is created (no snapshot, no sandbox)
- Fails closed immediately with actionable error

#### 2. Disposable snapshot

Candidate code is isolated from operator state using `git archive`:

```python
subprocess.run(
    ["git", "archive", "--format=tar", f"--output={archive_path}", "HEAD"],
    cwd=repo_path,
    capture_output=True,
    text=True,
    timeout=30,
)
```

`git archive` includes **only** tracked files at HEAD, excluding:
- `.oompah.pid` (operator lifecycle marker)
- `.env` (operator configuration)
- `.oompah/` directory (operator state)
- All untracked files and symlinks

Snapshot extraction uses tarfile's `filter="fully_trusted"` to reject:
- Absolute paths
- `..` path traversal
- Symlinks pointing outside the snapshot
- Device, FIFO, or socket files

**Result:** Candidate code receives a read-only, immutable snapshot with zero access to operator files.

#### 3. OS-level namespace sandbox (bubblewrap)

Candidate code runs in an empty-root sandbox using bubblewrap (`bwrap`):

```bash
bwrap \
  --die-with-parent --new-session \
  --unshare-user --unshare-pid --unshare-net \
  --cap-add CAP_NET_ADMIN \
  --tmpfs / \                    # Empty root
  --bind /repo /repo \           # Candidate snapshot (read-write)
  --bind /run/oompah /oompah-gate \  # Operator run state (read-write in sandbox only)
  --tmpfs /tmp --tmpfs /var/tmp \    # Private temp
  --ro-bind /usr /usr \          # Shared read-only /usr
  # ... more mounts ...
  /bin/sh -c "ip link set lo up && exec $command"
```

**Isolation properties:**
- **Mount namespace:** Only bound directories are visible; `/etc`, `/home`, `/root`, `/sys`, operator working directory are absent
- **PID namespace:** Process cannot signal or observe operator processes; `kill -TERM $(cat .oompah.pid)` fails (file doesn't exist, PID is unreachable)
- **Network namespace:** Isolated loopback; candidate cannot connect to host services like `http://127.0.0.1:8090`
- **User namespace:** Runs as a mapped UID; cannot become root or change permissions on operator files

### Threat model: can candidate code...?

| Attack                                      | Result | Defense |
|---------------------------------------------|--------|---------|
| Read `.oompah.pid`                          | ✗ File doesn't exist in snapshot | `git archive` excludes untracked files |
| Connect to `http://127.0.0.1:8090`          | ✗ No network route; own loopback only | Network namespace isolation |
| Signal operator process `kill -TERM $pid`   | ✗ PID unreachable in isolated namespace | PID namespace isolation |
| Modify operator files in live worktree      | ✗ Snapshot is immutable; live tree unavailable | Disposable snapshot + mount isolation |
| Discover operator socket via path traversal | ✗ `.../../../etc` leads to sandbox `/etc`, not host | Mount namespace isolation |
| Use symlink to escape sandbox                | ✗ Rejected at snapshot extraction time | Tarfile validation |

### Environment sanitization

The gate subprocess inherits **only** required display/locale settings and operator-generated lifecycle variables:

```python
environment = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
for key in ("LANG", "LC_ALL", "LC_CTYPE", "TERM"):
    value = os.environ.get(key)
    if value:
        environment[key] = value
environment.update({
    "OOMPAH_PYTEST_GATE": "1",
    "OOMPAH_PYTEST_RUN_ROOT": "/oompah-gate",
    "OOMPAH_PYTEST_TEMP_ROOT": "/oompah-gate/tmp",
    "OOMPAH_TEST_PID_FILE": "/oompah-gate/lifecycle/.oompah.pid",
    "OOMPAH_TEST_SERVER_PORT": str(allocated_port),  # Random, never 8090
    "HOME": "/oompah-gate/home",
    "TMPDIR": "/oompah-gate/tmp",
    # ... etc ...
})
```

**Excluded from candidate environment:**
- `OOMPAH_SERVER_URL`, `OOMPAH_SERVER_PORT` (no connection to operator)
- `OOMPAH_SERVER_USERNAME`, `OOMPAH_SERVER_PASSWORD` (no auth)
- `OOMPAH_TASK_HANDOFF_TOKEN` (no task access)
- Any user-set `QUALITY_GATE_*` variables (candidate cannot observe operator config)
- `$HOME`, `$TMPDIR` set to sandbox-visible paths only

### Process group and cleanup

The gate runs as a new session (`start_new_session=True`) to create an isolated process group:

```python
process = subprocess.Popen(
    sandboxed_command,
    env=...,
    start_new_session=True,  # New process group
)
```

On timeout or shutdown:
1. Entire process group is terminated: `os.killpg(process.pid, signal.SIGKILL)`
2. Sandbox is destroyed by bubblewrap's `--die-with-parent` option
3. Run root directory is deleted: `shutil.rmtree(run_root)`

This ensures no orphaned test processes or leaked files remain after gate completion.

## Integration with orchestrator

The `BranchQualityGate` instance is created once at orchestrator startup and shared across all concurrent integration checks:

```python
self._branch_quality_gate = BranchQualityGate(
    os.path.join(_state_dir, "quality_gates.json"),
    timeout_seconds=config.quality_gate_timeout_seconds,
    safety_head=config.quality_gate_safety_head,  # Configured by operator
)
```

### Safety head configuration

The operator can configure the safety head via environment variable:

```dotenv
# .env
OOMPAH_QUALITY_GATE_SAFETY_HEAD=ec0ec7d89fb8804571fcf7e780558e6d979b73ea
```

If not set, the compiled default (the actual OOMPAH-652 commit) is used.

### Generation tracking (OOMPAH-657)

The `BranchQualityGate` tracks active generations (candidate branches) for exactly-once delivery:

```python
_cancelled_generations: set[str] = set()  # Tombstones
_active_generations: dict[int, str | None] = {}  # Process -> generation ID
```

When a task is moved back to `Open` (e.g., for manual intervention), its generation is cancelled before the gate can even spawn the candidate process. This ensures a replacement gate is not blocked by a cancelled predecessor.

## Failure modes

### `needs_rebase`

Returned when:
- Branch lacks OOMPAH-652 ancestry (preflight failure)
- Bubblewrap is unavailable or cannot create the required namespaces
- Snapshot extraction fails (e.g., corrupt git repository)

**Action:** Task is moved to `Needs Rebase` with diagnostic comment. No candidate code executes.

### `failed`

Candidate process exited with non-zero status.

**Action:** Task is moved to `Needs CI Fix`. Gate output is logged for operator review.

### `timed_out`

Candidate process did not complete within `OOMPAH_QUALITY_GATE_TIMEOUT_SECONDS`.

**Action:** Process group is killed, task moved to `Needs CI Fix`.

### `error`

Unforeseen OS error (e.g., disk full, permission denied).

**Action:** Task moved to `Needs CI Fix` with diagnostic comment.

## Testing

### Regression fixtures

Unit tests verify that old/malicious Makefiles cannot breach the isolation boundary:

- `test_preflight_rejects_old_branch_without_oompah652_ancestor`: Orphan branches fail preflight without execution
- `test_spoofed_markers_without_oompah652_ancestor_is_rejected`: Spoofed marker strings in Makefile don't fool git ancestry check
- `test_default_boundary_blocks_literal_host_pid_and_localhost_attack`: Hostile code attempting file access and service connection fails
- `test_gate_subprocess_isolates_operator_and_tool_state`: Operator environment variables are stripped from sandbox

### Coverage

All 31 quality gate tests pass, including:
- Isolation mechanism tests (namespace enforcement, cleanup, reaping)
- Edge cases (symlink escapes, corrupt archives, unavailable bubblewrap)
- Caching and retry semantics
- Concurrent gate execution and single-flight locking

## Maintenance

### Bubblewrap availability

If bubblewrap is not installed, the gate fails closed with `needs_rebase` and diagnostic message. Operators must ensure bubblewrap is available in their deployment:

```bash
sudo apt-get install bubblewrap  # Debian/Ubuntu
sudo yum install bubblewrap      # RHEL/CentOS
brew install bubblewrap          # macOS
```

### Namespace availability

The gate probes for unprivileged namespace support on startup:

```bash
bwrap --die-with-parent --new-session \
  --unshare-user --unshare-pid --unshare-net \
  /bin/sh -c "ip link set lo up"
```

If this fails, the gate returns `needs_rebase` with diagnostic message. This typically indicates missing kernel support or restrictive security policies (AppArmor, SELinux) that block unprivileged namespace creation.

### Debugging failed gates

To debug a timed-out or failed gate on a specific branch:

1. Check the task's comment for gate output (last 16 KB)
2. Retry the gate explicitly from the integration state (same head, fresh execution)
3. If persistent, check system logs for:
   - OOM killer activity
   - AppArmor/SELinux denials
   - Disk space issues
