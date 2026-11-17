"""Guards for the Windows packaging pipeline (PyInstaller + NSIS + release workflow).

These exist because the installer build broke on three things that static
checks can catch: a hidden import that no longer exists, a missing NSIS icon,
and a PyInstaller pin that does not exist for the target Python versions.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "deploy" / "windows" / "unimonitor.spec"
NSI = ROOT / "deploy" / "windows" / "install.nsi"
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
INSTALLER_WORKFLOW = ROOT / ".github" / "workflows" / "windows-installer.yml"


def _spec_hiddenimports() -> list[str]:
    tree = ast.parse(SPEC.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "hiddenimports" for t in node.targets):
            return list(ast.literal_eval(node.value))
    raise AssertionError("hiddenimports not found in spec")


def test_spec_hiddenimports_point_at_real_unimonitor_modules():
    missing = []
    for name in _spec_hiddenimports():
        if not name.startswith("unimonitor"):
            continue
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except ModuleNotFoundError:
            missing.append(name)
    assert missing == [], f"hidden imports that do not exist: {missing}"


def test_spec_does_not_reference_removed_secrets_factory():
    assert "unimonitor.secrets.factory" not in _spec_hiddenimports()


def test_spec_collects_docx_templates_and_branding():
    source = SPEC.read_text()
    assert 'collect_data_files("docx")' in source, "python-docx needs its default.docx template at runtime"
    assert '"branding"' in source


def test_docker_images_copy_the_package_before_installing():
    """pip must see `unimonitor/` or it builds an empty wheel and the image lies."""
    for dockerfile in (Path("deploy/docker/Dockerfile"), Path("deploy/docker/Dockerfile.worker")):
        lines = [line.strip() for line in dockerfile.read_text().splitlines()]
        copy_index = lines.index("COPY unimonitor/ ./unimonitor/")
        install_index = next(i for i, line in enumerate(lines) if line.startswith("RUN pip install"))
        assert copy_index < install_index, f"{dockerfile} installs before copying the package"
        assert "-e " not in lines[install_index], f"{dockerfile} should install, not link, the package"


def test_docker_image_stages_the_frontend_where_the_app_serves_it():
    dockerfile = Path("deploy/docker/Dockerfile").read_text()
    assert "--from=frontend-builder /app/frontend/dist ./unimonitor/static/" in dockerfile
    assert "COPY branding/ ./branding/" in dockerfile


def test_nsis_icon_exists():
    """NSIS aborts the build when its MUI icon is missing."""
    assert "branding\\icon.ico" in NSI.read_text()
    icon = ROOT / "branding" / "icon.ico"
    assert icon.exists(), "branding/icon.ico missing — run python scripts/make_icon.py"
    assert icon.read_bytes()[:4] == b"\x00\x00\x01\x00", "not a valid .ico file"


def test_nsis_does_not_require_third_party_plugins():
    """EnVar is not shipped with stock NSIS, so a plugin call breaks the build."""
    assert "EnVar::" not in NSI.read_text()


def test_release_workflow_builds_installer_on_demand():
    workflow = yaml.safe_load(RELEASE.read_text())
    # PyYAML parses the bare ``on:`` key as boolean True
    triggers = workflow.get("on", workflow.get(True))
    assert "workflow_dispatch" in triggers, "installer should be buildable without pushing a tag"
    assert "push" in triggers

    job = workflow["jobs"]["windows-installer"]
    text = yaml.safe_dump(job)
    assert "pyinstaller>=6.16.0,<7" in text, "pin must be a version that exists for current Python"
    assert "pyinstaller==6.10.0" not in text
    assert "if-no-files-found: error" in text, "a missing installer must fail the job"


@pytest.mark.parametrize("workflow", [INSTALLER_WORKFLOW, RELEASE])
def test_nsis_is_put_on_path_before_it_is_used(workflow: Path):
    """``choco install nsis`` does not refresh the running process PATH.

    Calling bare ``makensis`` straight after the install fails with "The term
    'makensis' is not recognized" (exit 1), which is how the installer build broke.
    """
    text = workflow.read_text()
    assert "$env:GITHUB_PATH" in text, "later steps need the NSIS folder exported to PATH"
    assert "makensis.exe" in text, "workflow must resolve makensis.exe explicitly"
    install_block = text.split("choco install nsis", 1)[1]
    assert "$env:GITHUB_PATH" in install_block.split("- name:", 1)[0], "GITHUB_PATH must be set in the Install NSIS step, right after choco"


@pytest.mark.parametrize("filename", ["unimonitor.spec", "install.nsi"])
def test_windows_build_files_present(filename: str):
    assert (ROOT / "deploy" / "windows" / filename).exists()


def test_standalone_installer_workflow_is_dispatchable():
    workflow = yaml.safe_load(INSTALLER_WORKFLOW.read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert "workflow_dispatch" in triggers, "manual installer build must not need a commit or tag"
    assert "push" not in triggers, "keep installer builds manual so they don't burn Actions minutes"

    text = INSTALLER_WORKFLOW.read_text()
    assert "pyinstaller>=6.16.0,<7" in text
    assert "if-no-files-found: error" in text
    assert "branding/icon.ico" in text, "workflow must fail fast when the NSIS icon is missing"
    assert "--help" in text, "workflow must smoke-test the frozen executable"
    assert "makensis" in text and "UniMonitor-Setup-" in text
