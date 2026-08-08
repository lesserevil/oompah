# Workflow engine qualification soak

The workflow-engine soak exercises the production durable scheduler, SQLite
job ledger, public WorkDecision projection, and global-alert filter with a
deterministic provider workload. It does not contact trackers, forges, models,
or other network services.

Run the bounded CI profile with:

```bash
make workflow-soak-ci
```

That profile runs 120 tasks across four projects. The ordinary test suite also
runs an equivalent 104-task profile, so pull-request CI cannot bypass the soak.

Run the longer operator profile with:

```bash
make workflow-soak
```

The operator profile runs 1,000 tasks across eight projects. Both profiles
contain independent work, shared and nested epics, cross-project/cross-epic
dependencies, review, audit, integration, and branch-pruning jobs. They inject
retryable transport failures, abandon one live lease across an exclusive
restart, and include exactly one deliberately unrecoverable job.

The command exits nonzero unless all of these conditions hold:

- every recoverable task reaches terminal state without manual intervention;
- exactly the deliberate permanent failure becomes operator-actionable;
- no pending task is left without a decision or durable recovery path;
- fair claims do not repeat one project while another project is claimable;
- public decision fields match the scheduler decision, and normal retries do
  not become global warnings;
- restart reconstruction recovers exactly one abandoned lease;
- task latency is no more than `task_count * (max_attempts + 2)` deterministic
  seconds;
- SQLite stays below 512 KiB plus 64 KiB per task; and
- traced Python allocations stay below 32 MiB plus 512 KiB per task.

The JSON report records the actual queue age, retry count, project claim skew,
restart count, task latency, SQLite bytes, peak traced allocations, alert count,
action mix, and hierarchy/dependency coverage.

## Configuration

Set soak tuning in `.env`; the Make targets load that file. Unset values use
the profile defaults above. Keep at least 100 total tasks, two projects, and at
least ten tasks per project so every project retains the complete topology.

```dotenv
OOMPAH_WORKFLOW_SOAK_TASK_COUNT=1000
OOMPAH_WORKFLOW_SOAK_PROJECT_COUNT=8
OOMPAH_WORKFLOW_SOAK_DECISION_LIMIT=100
OOMPAH_WORKFLOW_SOAK_BATCH_SIZE=64
OOMPAH_WORKFLOW_SOAK_MAX_CYCLES=500
OOMPAH_WORKFLOW_SOAK_SQLITE_BYTES_PER_TASK=65536
OOMPAH_WORKFLOW_SOAK_MEMORY_BYTES_PER_TASK=524288
```

To retain the SQLite ledger for inspection, set
`OOMPAH_WORKFLOW_SOAK_DATABASE` to a new path. The runner refuses to overwrite
an existing database.
