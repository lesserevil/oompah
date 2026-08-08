#!/usr/bin/env python3
"""Run the deterministic durable-workflow qualification soak."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from oompah.config import load_dotenv
from oompah.workflow_soak import WorkflowSoakProfile, run_workflow_soak


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("ci", "operator"),
        default="operator",
        help="bounded CI workload or longer operator workload",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="configuration file containing OOMPAH_WORKFLOW_SOAK_* values",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv(os.path.abspath(args.env_file), override=True)
    profile = WorkflowSoakProfile.from_env(args.profile)
    configured_database = os.environ.get("OOMPAH_WORKFLOW_SOAK_DATABASE", "").strip()
    if configured_database:
        report = run_workflow_soak(profile, database_path=Path(configured_database))
    else:
        with tempfile.TemporaryDirectory(prefix="oompah-workflow-soak-") as root:
            report = run_workflow_soak(
                profile,
                database_path=Path(root) / "workflow-jobs.sqlite3",
            )
    json.dump(report.to_dict(), sys.stdout, sort_keys=True, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
