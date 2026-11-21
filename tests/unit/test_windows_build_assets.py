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


def _literal_names(node: ast.AST) -> list[str]:
    """Names from a list literal, including the literal halves of ``a + [...]``.

    ``collect_submodules(...)`` calls are resolved by PyInstaller at build time, so
    they contribute nothing to check here.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _literal_names(node.left) + _literal_names(node.right)
    if isinstance(node, ast.Call):
        return []
    return list(ast.literal_eval(node))


def _spec_hiddenimports() -> list[str]:
    tree = ast.parse(SPEC.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "hiddenimports" for t in node.targets):
            return _literal_names(node.value)
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


BUILD_SCRIPT = ROOT / "scripts" / "build-windows-installer.ps1"
BUILD_WRAPPER = ROOT / "scripts" / "build-windows-installer.cmd"


def test_one_command_build_script_covers_the_pipeline():
    """The documented one-command build must actually run every packaging step."""
    assert BUILD_SCRIPT.exists(), "scripts/build-windows-installer.ps1 missing"
    assert BUILD_WRAPPER.exists(), "scripts/build-windows-installer.cmd missing"

    script = BUILD_SCRIPT.read_text()
    for expected in ("pyinstaller", "makensis", "nssm", "npm", "install.nsi", "icon.ico"):
        assert expected in script, f"build script no longer handles {expected}"
    assert "$LASTEXITCODE" in script, "the build must fail when a step fails"
    assert "Set-StrictMode" in script


def test_build_script_parses_on_windows_powershell_5_1():
    """PowerShell 5.1 decodes a BOM-less script as Windows-1252.

    A UTF-8 box-drawing character then turns into ``â”€``, and the ``”`` is a smart
    quote that ends a string early, so the parser reports a missing brace far from
    the real line. Keep the script ASCII and BOM-prefixed so 5.1 and 7 agree.
    """
    raw = BUILD_SCRIPT.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "script needs a UTF-8 BOM for Windows PowerShell 5.1"
    body = raw[3:]
    assert body.isascii(), f"non-ASCII bytes break Windows PowerShell 5.1: {[b for b in body if b > 127][:5]}"
    assert b"\r\n" not in body, "use LF; 5.1 handles both, but mixed endings hide parse errors"


def test_every_python_step_runs_a_module():
    """`python install ...` passes "install" to the interpreter, not to pip.

    That is how the dependency step failed: the argument list lost its "-m pip",
    so Python tried to open a file called `install` and exited with code 2.
    """
    script = BUILD_SCRIPT.read_text(encoding="utf-8-sig")
    invocations = script.split("Invoke-Checked $VenvPython @(")[1:]
    assert invocations, "build script no longer runs Python steps"
    for block in invocations:
        first = block.split('"')
        assert len(first) > 1, f"malformed Python invocation: {block[:60]!r}"
        target = first[1]
        # Either run a module (-m <name>) or a script file; never a bare verb.
        assert target == "-m" or target.endswith(".py"), f"Python step must run a module or a script: {block[:60]!r}"


def test_dependency_install_goes_through_pip():
    script = BUILD_SCRIPT.read_text(encoding="utf-8-sig")
    assert '"-m", "pip", "install"' in script, "dependencies must be installed with python -m pip"
    assert '".[production]"' in script, "the build venv needs the production extras"


def test_install_guide_points_at_the_one_command_build():
    install = (ROOT / "INSTALL.md").read_text()
    assert "build-windows-installer.cmd" in install
    assert "build-windows-installer.ps1" in install


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
    assert "makensis" in text
    assert "UniMonitor-Setup-" in text
