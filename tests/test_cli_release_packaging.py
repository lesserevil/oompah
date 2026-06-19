from __future__ import annotations

import importlib.util
from pathlib import Path
import tomllib

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
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
    assert "does not install or configure" in text
