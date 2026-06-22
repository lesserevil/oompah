from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
import tomllib

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = REPO_ROOT / "dist"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "cli-release.yml"
SCRIPT_PATH = REPO_ROOT / "scripts" / "render_cli_release_notes.py"


def _load_release_notes_module():
    spec = importlib.util.spec_from_file_location(
        "render_cli_release_notes", SCRIPT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_notes_include_exact_tag_and_artifact_install_commands():
    module = _load_release_notes_module()

    notes = module.render_release_notes(
        tag="v0.1.0",
        wheel_name="oompah-0.1.0-py3-none-any.whl",
        sdist_name="oompah-0.1.0.tar.gz",
    )

    assert (
        'uv tool install "git+https://github.com/lesserevil/oompah@v0.1.0"'
        in notes
    )
    assert (
        'pipx install "git+https://github.com/lesserevil/oompah@v0.1.0"'
        in notes
    )
    assert (
        'uv tool install "https://github.com/lesserevil/oompah/releases/download/'
        'v0.1.0/oompah-0.1.0-py3-none-any.whl"'
        in notes
    )
    assert (
        'pipx install "https://github.com/lesserevil/oompah/releases/download/'
        'v0.1.0/oompah-0.1.0-py3-none-any.whl"'
        in notes
    )
    assert "task CLI release" in notes
    assert "does not install or configure the oompah service runtime" in notes


def test_default_package_install_is_task_cli_only():
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert data["project"]["dependencies"] == ["httpx>=0.27"]

    extras = data["project"]["optional-dependencies"]
    assert "server" in extras
    assert "fastapi>=0.115" in extras["server"]
    assert "uvicorn[standard]>=0.34" in extras["server"]
    assert "watchfiles>=1.0" in extras["server"]

    assert "fastapi>=0.115" in extras["dev"]
    assert "watchfiles>=1.0" in extras["dev"]
    assert "oompah[server]" in extras["all"]


def test_release_notes_renderer_validates_tag_and_artifacts(tmp_path):
    module = _load_release_notes_module()
    pyproject = tmp_path / "pyproject.toml"
    dist = tmp_path / "dist"
    dist.mkdir()
    pyproject.write_text(
        "[project]\nname = \"oompah\"\nversion = \"1.2.3\"\n",
        encoding="utf-8",
    )
    (dist / "oompah-1.2.3-py3-none-any.whl").write_text("", encoding="utf-8")
    (dist / "oompah-1.2.3.tar.gz").write_text("", encoding="utf-8")

    notes = module.render_release_notes_for_dist(
        tag="v1.2.3",
        pyproject_path=pyproject,
        dist_dir=dist,
    )

    assert "oompah-1.2.3-py3-none-any.whl" in notes
    assert "oompah-1.2.3.tar.gz" in notes


def test_release_notes_renderer_rejects_version_mismatched_tag(tmp_path):
    module = _load_release_notes_module()
    pyproject = tmp_path / "pyproject.toml"
    dist = tmp_path / "dist"
    dist.mkdir()
    pyproject.write_text(
        "[project]\nname = \"oompah\"\nversion = \"1.2.3\"\n",
        encoding="utf-8",
    )

    try:
        module.render_release_notes_for_dist(
            tag="v1.2.4",
            pyproject_path=pyproject,
            dist_dir=dist,
        )
    except ValueError as exc:
        assert "expected 'v1.2.3'" in str(exc)
    else:
        raise AssertionError("version-mismatched release tag was accepted")


def test_release_workflow_is_tag_or_manual_github_release_only():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on") or workflow.get(True)

    assert triggers["push"]["tags"] == ["v*"]
    assert "branches" not in triggers["push"]
    assert "workflow_dispatch" in triggers
    assert workflow["permissions"] == {"contents": "write"}

    assert "python -m build --sdist --wheel" in text
    assert "python -m pip install dist/*.whl" in text
    assert "oompah --help" in text
    assert "oompah task --help" in text
    assert "gh release create" in text
    assert "gh release upload" in text
    assert "scripts/render_cli_release_notes.py" in text

    lower = text.lower()
    assert "twine" not in lower
    assert "pypi" not in lower
    assert "id-token" not in lower


def test_release_docs_cover_tag_creation_and_verification_commands():
    text = (REPO_ROOT / "docs" / "cli-release.md").read_text(encoding="utf-8")

    assert 'git tag -a v0.1.0 -m "oompah v0.1.0"' in text
    assert "Actions > CLI Release" in text
    assert (
        'uv tool install "git+https://github.com/lesserevil/oompah@v0.1.0"'
        in text
    )
    assert (
        'pipx install "git+https://github.com/lesserevil/oompah@v0.1.0"'
        in text
    )
    assert (
        'uv tool install "https://github.com/lesserevil/oompah/releases/download/'
        'v0.1.0/oompah-0.1.0-py3-none-any.whl"'
        in text
    )
    assert (
        'pipx install "https://github.com/lesserevil/oompah/releases/download/'
        'v0.1.0/oompah-0.1.0-py3-none-any.whl"'
        in text
    )
    assert "standalone `oompah task` client" in text
    assert "oompah project-bootstrap --help" in text
    assert "does not install or configure" in text


def test_pyproject_version_is_1_0_0():
    """Package metadata must be at 1.0.0 on the release branch."""
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == "1.0.0", (
        f"pyproject.toml project.version must be 1.0.0 on the release branch, "
        f"got {data['project']['version']!r}"
    )


def test_release_note_generator_accepts_v1_0_0_tag(tmp_path):
    """The release-note generator must agree that v1.0.0 matches package version 1.0.0."""
    module = _load_release_notes_module()
    pyproject = tmp_path / "pyproject.toml"
    dist = tmp_path / "dist"
    dist.mkdir()
    pyproject.write_text(
        '[project]\nname = "oompah"\nversion = "1.0.0"\n',
        encoding="utf-8",
    )
    (dist / "oompah-1.0.0-py3-none-any.whl").write_text("", encoding="utf-8")
    (dist / "oompah-1.0.0.tar.gz").write_text("", encoding="utf-8")

    notes = module.render_release_notes_for_dist(
        tag="v1.0.0",
        pyproject_path=pyproject,
        dist_dir=dist,
    )

    assert "oompah-1.0.0-py3-none-any.whl" in notes
    assert "oompah-1.0.0.tar.gz" in notes
    assert "v1.0.0" in notes


def test_server_extras_complete_and_not_in_base_dependencies():
    """ALL server-runtime packages must be behind the server extra, not in base deps.

    This is a comprehensive check that the dependency boundary is correct:
    every package from the ``server`` extra is verified to be absent from the
    base ``[project.dependencies]`` list.  Adding a server package to base
    deps would force it on every CLI-only user, breaking the lightweight
    install contract.
    """
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    base_deps = data["project"]["dependencies"]
    server_extras = data["project"]["optional-dependencies"]["server"]

    # The base dependency list must contain only httpx (the HTTP client used
    # by the task CLI to talk to the oompah server).
    assert base_deps == ["httpx>=0.27"], (
        f"Base dependencies must contain only 'httpx>=0.27' to keep the "
        f"lightweight CLI install free of server runtime packages.  "
        f"Got: {base_deps!r}"
    )

    # All known server-runtime package name prefixes (PEP 508 names,
    # lowercased) must appear in the server extra.
    required_server_packages = [
        "fastapi",
        "uvicorn",
        "jinja2",
        "pyyaml",
        "watchfiles",
        "python-liquid",
        "pyjwt",
        "python-multipart",
    ]
    for pkg in required_server_packages:
        found = any(
            dep.lower().startswith(pkg.lower()) for dep in server_extras
        )
        assert found, (
            f"Expected {pkg!r} in [project.optional-dependencies.server], "
            f"but it was not found.  Server-runtime packages must stay behind "
            f"the server extra.  Current server extras: {server_extras!r}"
        )

    # None of the server extra packages must leak into base deps.
    for dep in server_extras:
        # Strip version specifiers to get the package name portion.
        pkg_name = dep.split("[")[0].split(">=")[0].split("==")[0].split(">")[0].strip()
        assert pkg_name not in base_deps, (
            f"Server-extra package {pkg_name!r} was found in base "
            f"[project.dependencies].  It must stay behind the server extra "
            f"to keep CLI-only installs lightweight."
        )


def test_wheel_contains_required_cli_modules():
    """The built wheel must include all modules needed by the lightweight CLI.

    Verifies that ``oompah task`` and ``oompah project-bootstrap`` module
    paths are present inside the wheel archive.  Skipped automatically when
    no wheel exists in ``dist/`` so the normal development cycle (no wheel
    pre-built) is not disrupted.

    A wheel is a zip archive.  The expected paths mirror the package layout
    under ``[tool.hatch.build.targets.wheel] packages = ["oompah"]``.
    """
    wheels = sorted(DIST_DIR.glob("oompah-*.whl"))
    if not wheels:
        import pytest
        pytest.skip(
            "No wheel found in dist/ -- build one with 'python -m build' "
            "or 'pip wheel . -w dist --no-deps' to enable wheel-contents tests"
        )

    wheel_path = wheels[-1]

    # Required modules for the two supported CLI commands.
    required_modules = [
        "oompah/__init__.py",
        "oompah/__main__.py",
        "oompah/task_cli.py",
        "oompah/project_bootstrap_cli.py",
        "oompah/project_bootstrap/__init__.py",
        "oompah/agent_instructions.py",
        "oompah/project_bootstrap/templates/__init__.py",
    ]

    with zipfile.ZipFile(wheel_path) as whl:
        names = whl.namelist()

    missing = [m for m in required_modules if m not in names]
    assert not missing, (
        f"Wheel {wheel_path.name} is missing required CLI modules:\n"
        + "\n".join(f"  - {m}" for m in missing)
        + f"\n\nWheel contents (oompah/ files):\n"
        + "\n".join(f"  {n}" for n in sorted(names) if n.startswith("oompah/"))
    )


def test_wheel_does_not_contain_server_only_module_as_dep():
    """The wheel metadata must not list any server-runtime package as a required dep.

    Parses the METADATA file inside the built wheel (a zip archive) and
    checks that none of the ``Requires-Dist`` entries are server-runtime
    packages.  Skipped when no wheel is present in ``dist/``.
    """
    wheels = sorted(DIST_DIR.glob("oompah-*.whl"))
    if not wheels:
        import pytest
        pytest.skip(
            "No wheel found in dist/ -- build one with 'python -m build' "
            "or 'pip wheel . -w dist --no-deps' to enable wheel-metadata tests"
        )

    wheel_path = wheels[-1]

    server_package_prefixes = [
        "fastapi",
        "uvicorn",
        "jinja2",
        "pyyaml",
        "watchfiles",
        "python-liquid",
        "pyjwt",
        "python-multipart",
    ]

    with zipfile.ZipFile(wheel_path) as whl:
        # METADATA lives in <name>-<version>.dist-info/METADATA
        metadata_path = next(
            n for n in whl.namelist()
            if n.endswith(".dist-info/METADATA")
        )
        metadata_text = whl.read(metadata_path).decode("utf-8")

    requires_dist = [
        line.split("Requires-Dist:")[1].strip()
        for line in metadata_text.splitlines()
        if line.startswith("Requires-Dist:")
    ]

    # Only unconditional (no extra marker) requirements are checked.
    # Conditional extras are allowed to list server packages.
    unconditional = [r for r in requires_dist if 'extra ==' not in r]

    for req in unconditional:
        req_name = req.split("[")[0].split(">=")[0].split("==")[0].split(">")[0].strip().lower()
        for pkg in server_package_prefixes:
            assert req_name != pkg.lower(), (
                f"Wheel {wheel_path.name} METADATA lists {req!r} as an "
                f"unconditional Requires-Dist entry.  Server-runtime packages "
                f"must be behind the 'server' extra marker, not required for "
                f"all installs.  This would force the server runtime on "
                f"lightweight CLI users."
            )
