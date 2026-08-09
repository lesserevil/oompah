#!/usr/bin/env python3
"""Resolve and validate the lifecycle listener-startup deadline."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from oompah.config import load_dotenv


ENVIRONMENT_KEY = "OOMPAH_LISTENER_STARTUP_TIMEOUT_SECONDS"
DEFAULT_SECONDS = 10
MINIMUM_SECONDS = 5
MAXIMUM_SECONDS = 120


def resolve_listener_startup_timeout(env_file: str | Path = ".env") -> int:
    """Return the validated environment/.env timeout, failing closed."""

    load_dotenv(str(env_file), override=False)
    raw_value = os.environ.get(ENVIRONMENT_KEY, str(DEFAULT_SECONDS)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{ENVIRONMENT_KEY} must be an integer") from exc
    if not MINIMUM_SECONDS <= value <= MAXIMUM_SECONDS:
        raise ValueError(
            f"{ENVIRONMENT_KEY} must be between {MINIMUM_SECONDS} and "
            f"{MAXIMUM_SECONDS} seconds"
        )
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env")
    arguments = parser.parse_args(argv)
    try:
        timeout = resolve_listener_startup_timeout(arguments.env_file)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
