#!/usr/bin/env python3
"""Render GitHub Release notes for oompah CLI artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tomllib


REPOSITORY = "lesserevil/oompah"


def load_project_version(pyproject_path: Path) -> str:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    try:
        version = data["project"]["version"]
    except KeyError as exc:
        raise ValueError(f"{pyproject_path} does not define project.version") from exc
    if not isinstance(version, str) or not version:
        raise ValueError(f"{pyproject_path} has an invalid project.version")
    return version


def is_draft_release_tag(tag: str, version: str) -> bool:
    """Return True if *tag* is the explicit force-movable draft form for *version*.

    The only accepted draft form is ``v{version}-draft`` — e.g. ``v1.0.0-draft``
    for a project whose ``project.version`` is ``1.0.0``.  Broader wildcards such
    as ``v*-draft`` are intentionally rejected so this predicate cannot silently
    weaken final-release validation.
    """
    return tag == f"v{version}-draft"


def validate_tag_matches_version(tag: str, version: str) -> None:
    """Raise ValueError unless *tag* is the final or draft release tag for *version*.

    Accepted forms:
    - ``v{version}``        — immutable final release tag
    - ``v{version}-draft``  — force-movable draft tag used during RC iteration
    """
    expected = f"v{version}"
    if tag == expected or is_draft_release_tag(tag, version):
        return
    raise ValueError(
        f"release tag {tag!r} does not match pyproject version {version!r}; "
        f"expected {expected!r} or {expected!r}-draft"
    )


def _find_one(dist_dir: Path, pattern: str, artifact_kind: str) -> Path:
    matches = sorted(dist_dir.glob(pattern))
    if len(matches) != 1:
        names = ", ".join(path.name for path in matches) or "none"
        raise ValueError(
            f"expected exactly one {artifact_kind} matching {pattern!r} in "
            f"{dist_dir}; found {names}"
        )
    return matches[0]


def find_release_artifacts(dist_dir: Path, version: str) -> tuple[Path, Path]:
    wheel = _find_one(dist_dir, f"oompah-{version}-*.whl", "wheel")
    sdist = _find_one(dist_dir, f"oompah-{version}.tar.gz", "sdist")
    return wheel, sdist


def render_release_notes(
    *,
    tag: str,
    wheel_name: str,
    sdist_name: str,
    repository: str = REPOSITORY,
) -> str:
    wheel_url = f"https://github.com/{repository}/releases/download/{tag}/{wheel_name}"
    tag_url = f"git+https://github.com/{repository}@{tag}"
    return f"""# oompah {tag}

GitHub-only task CLI release for `{tag}`.

The default install provides `oompah task` for talking to an existing oompah
service. It does not install or configure the oompah service runtime.

## Install from the Git tag

```bash
uv tool install "{tag_url}"
pipx install "{tag_url}"
```

## Install from the wheel artifact

```bash
uv tool install "{wheel_url}"
pipx install "{wheel_url}"
```

## Verify the installed console script

```bash
oompah --help
oompah task --help
oompah project-bootstrap --help
```

## Upgrading from an earlier install

If you installed oompah before the `project-bootstrap` subcommand was added,
your binary may lack the `project_bootstrap` module. Running
`oompah project-bootstrap status .` on a stale install fails with
`unrecognized arguments: status .`.

Run one of the following to update:

```bash
# Preferred: upgrade in place
uv tool upgrade oompah

# Alternative: force a full reinstall from this tag
uv tool install --reinstall "{tag_url}"

# pipx equivalent
pipx upgrade oompah
```

Verify the upgrade with `oompah project-bootstrap --help`. If the output lists
`status`, `preview`, and `apply`, the upgrade was successful.

## Artifacts

- `{wheel_name}` - lightweight installable wheel for the `oompah task` CLI
- `{sdist_name}` - source distribution built from the tagged source state

This project publishes CLI artifacts through GitHub Releases only.
"""


def render_release_notes_for_dist(
    *,
    tag: str,
    pyproject_path: Path,
    dist_dir: Path,
    repository: str = REPOSITORY,
) -> str:
    version = load_project_version(pyproject_path)
    validate_tag_matches_version(tag, version)
    wheel, sdist = find_release_artifacts(dist_dir, version)
    return render_release_notes(
        tag=tag,
        wheel_name=wheel.name,
        sdist_name=sdist.name,
        repository=repository,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render GitHub Release notes for oompah CLI artifacts."
    )
    parser.add_argument("--tag", required=True, help="Release tag, e.g. v0.1.0")
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to pyproject.toml",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=Path("dist"),
        help="Directory containing built release artifacts",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("CLI_RELEASE_NOTES.md"),
        help="Release notes output path",
    )
    parser.add_argument(
        "--repository",
        default=REPOSITORY,
        help="GitHub repository in owner/name form",
    )
    args = parser.parse_args(argv)

    try:
        notes = render_release_notes_for_dist(
            tag=args.tag,
            pyproject_path=args.pyproject,
            dist_dir=args.dist_dir,
            repository=args.repository,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    args.output.write_text(notes, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
