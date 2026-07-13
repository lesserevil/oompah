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
        tag="v1.0.0",
        wheel_name="oompah-1.0.0-py3-none-any.whl",
        sdist_name="oompah-1.0.0.tar.gz",
    )

    assert (
        'uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in notes
    )
    assert (
        'pipx install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in notes
    )
    assert (
        'uv tool install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in notes
    )
    assert (
        'pipx install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
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


def test_release_workflow_dispatch_description_shows_v1_examples():
    """Workflow dispatch description should hint at v1.0.0-draft and v1.0.0 forms."""
    text = WORKFLOW_PATH.read_text(encoding='utf-8')
    workflow = yaml.safe_load(text)
    dispatch = (workflow.get('on') or workflow.get(True))['workflow_dispatch']
    description = dispatch['inputs']['tag']['description']
    assert 'v1.0.0-draft' in description
    assert 'v1.0.0' in description


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
    assert "oompah project-bootstrap --help" in text
    assert "gh release create" in text
    assert "gh release upload" in text
    assert "scripts/render_cli_release_notes.py" in text

    lower = text.lower()
    assert "twine" not in lower
    assert "pypi" not in lower
    assert "id-token" not in lower


def test_release_docs_cover_tag_creation_and_verification_commands():
    text = (REPO_ROOT / "docs" / "cli-release.md").read_text(encoding="utf-8")

    assert 'git tag -a v1.0.0 -m "oompah v1.0.0"' in text
    assert "Actions > CLI Release" in text
    assert (
        'uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in text
    )
    assert (
        'pipx install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in text
    )
    assert (
        'uv tool install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in text
    )
    assert (
        'pipx install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in text
    )
    assert "standalone `oompah task` client" in text
    assert "does not install or configure" in text


def test_release_notes_include_upgrade_and_reinstall_guidance():
    """Release notes must include an upgrade section for stale installs.

    Operators who installed oompah before the project-bootstrap feature was
    added have a binary that lacks project_bootstrap/. The release notes must
    tell them to run ``uv tool upgrade oompah`` or reinstall.
    """
    module = _load_release_notes_module()

    notes = module.render_release_notes(
        tag="v1.0.0",
        wheel_name="oompah-1.0.0-py3-none-any.whl",
        sdist_name="oompah-1.0.0.tar.gz",
    )

    # Must mention the upgrade command
    assert "uv tool upgrade oompah" in notes
    # Must mention --reinstall as an alternative
    assert "--reinstall" in notes
    # Must reference the upgrade section heading
    assert "Upgrading" in notes
    # Must include project-bootstrap in the verify block
    assert "oompah project-bootstrap --help" in notes


def test_release_notes_upgrade_section_references_tag_install():
    """The reinstall command in release notes must reference the release tag.

    Operators should reinstall from the tagged release, not from untagged main.
    """
    module = _load_release_notes_module()

    notes = module.render_release_notes(
        tag="v1.0.0",
        wheel_name="oompah-1.0.0-py3-none-any.whl",
        sdist_name="oompah-1.0.0.tar.gz",
    )

    # The reinstall command must pin to the specific release tag
    assert (
        'uv tool install --reinstall "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in notes
    )


def test_install_docs_cover_upgrade_from_pre_project_bootstrap_install():
    """docs/cli-install.md must document the project-bootstrap reinstall requirement.

    Any operator who installed before project-bootstrap was added will have a
    stale binary that fails with 'unrecognized arguments: status .' when running
    'oompah project-bootstrap status .'.
    """
    text = (REPO_ROOT / "docs" / "cli-install.md").read_text(encoding="utf-8")

    # Must describe the upgrade path
    assert "uv tool upgrade oompah" in text
    # Must mention --reinstall as an alternative
    assert "--reinstall" in text
    # Must mention project-bootstrap in the upgrade context
    assert "project-bootstrap" in text.lower()
    # Must mention project_bootstrap module (the Python module name used in error context)
    assert "project_bootstrap" in text


def test_release_docs_describe_draft_and_final_tag_convention():
    text = (REPO_ROOT / "docs" / "cli-release.md").read_text(encoding="utf-8")

    # 1.0 release train section
    assert "release/1.0" in text
    assert "v1.0.0-draft" in text
    assert "force-movable" in text.lower() or "force-move" in text.lower()
    assert "immutable" in text

    # Draft tag push command
    assert "git tag -f v1.0.0-draft" in text
    assert "git push -f origin v1.0.0-draft" in text


def test_install_docs_cover_tag_and_wheel_installs_for_v1():
    text = (REPO_ROOT / "docs" / "cli-install.md").read_text(encoding="utf-8")

    # v1.0.0 tag install
    assert (
        'uv tool install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in text
    )
    assert (
        'pipx install "git+https://github.com/lesserevil/oompah@v1.0.0"'
        in text
    )

    # v1.0.0 wheel install
    assert (
        'uv tool install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in text
    )
    assert (
        'pipx install "https://github.com/lesserevil/oompah/releases/download/'
        'v1.0.0/oompah-1.0.0-py3-none-any.whl"'
        in text
    )

    # Draft tag install example
    assert "v1.0.0-draft" in text

    # No PyPI install instructions (the docs may mention "no PyPI" but must not instruct
    # users to install from PyPI)
    assert "pip install oompah" not in text
    assert "pypi.org" not in text.lower()
    # The doc should explicitly say GitHub-only, no PyPI
    assert "github only" in text.lower() or "github-only" in text.lower()
