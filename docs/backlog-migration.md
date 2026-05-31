# Migrating Beads to Backlog.md

Use `oompah-migrate-beads-to-backlog` to copy a project's existing `bd`
(beads) issues into Backlog.md task files.

```bash
oompah-migrate-beads-to-backlog --source /path/to/project --backlog-dir backlog
```

The tool reads from the beads tracker, writes Backlog.md task files, and stores
the original bead identifier in each task's YAML front matter under `beads.id`.
Backlog.md keeps its own native task IDs, so parent-child and blocker
dependencies are remapped to the new Backlog.md IDs after all tasks are
allocated.

Useful options:

```bash
oompah-migrate-beads-to-backlog --dry-run --json
oompah-migrate-beads-to-backlog --force
oompah-migrate-beads-to-backlog --no-init
```

- `--dry-run` reports the planned ID mapping without writing files.
- `--force` updates tasks that were already migrated, matched by `beads.id`.
- `--no-init` requires an existing Backlog.md directory instead of running
  `backlog init`.

By default, re-running the migration is safe: tasks that already have matching
`beads.id` metadata are skipped rather than duplicated.
