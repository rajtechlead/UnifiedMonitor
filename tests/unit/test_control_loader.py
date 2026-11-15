"""
Unit tests for grc/control_loader.py

Tests ControlDefinition, ControlLoader, _parse_list_format, _parse_legacy_format,
_load_yaml_file, load_all_controls, load_controls_for_frameworks, _normalise.
"""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch


# ---------------------------------------------------------------------------
# ControlDefinition.run_evaluate
# ---------------------------------------------------------------------------

class TestControlDefinitionRunEvaluate:
    def _make_ctrl(self, code: str, ctrl_id="C1"):
        from unimonitor.grc.control_loader import ControlDefinition
        return ControlDefinition(
            id=ctrl_id,
            title="Test",
            severity="HIGH",
            category="identity",
            service="entra_id",
            compliance_mapping={},
            _evaluate_code=code,
        )

    def test_returns_implemented_when_data_matches(self):
        code = "def evaluate(data):\n    return 'implemented' if data.get('mfa') else 'not_implemented'"
        ctrl = self._make_ctrl(code)
        assert ctrl.run_evaluate({"mfa": True}) == "implemented"

    def test_returns_not_implemented_when_data_mismatches(self):
        code = "def evaluate(data):\n    return 'implemented' if data.get('mfa') else 'not_implemented'"
        ctrl = self._make_ctrl(code)
        assert ctrl.run_evaluate({}) == "not_implemented"

    def test_normalises_pass_to_implemented(self):
        code = "def evaluate(data):\n    return 'pass'"
        ctrl = self._make_ctrl(code)
        assert ctrl.run_evaluate({}) == "implemented"

    def test_normalises_fail_to_not_implemented(self):
        code = "def evaluate(data):\n    return 'fail'"
        ctrl = self._make_ctrl(code)
        assert ctrl.run_evaluate({}) == "not_implemented"

    def test_normalises_partial_to_partially_implemented(self):
        code = "def evaluate(data):\n    return 'partial'"
        ctrl = self._make_ctrl(code)
        assert ctrl.run_evaluate({}) == "partially_implemented"

    def test_normalises_na_to_not_applicable(self):
        code = "def evaluate(data):\n    return 'n/a'"
        ctrl = self._make_ctrl(code)
        assert ctrl.run_evaluate({}) == "not_applicable"

    def test_returns_error_on_exception(self):
        code = "def evaluate(data):\n    raise ValueError('boom')"
        ctrl = self._make_ctrl(code)
        assert ctrl.run_evaluate({}) == "error"

    def test_unknown_result_returned_as_is(self):
        code = "def evaluate(data):\n    return 'custom_state'"
        ctrl = self._make_ctrl(code)
        result = ctrl.run_evaluate({})
        assert result == "custom_state"

    def test_returns_partially_implemented(self):
        code = "def evaluate(data):\n    return 'partially_implemented'"
        ctrl = self._make_ctrl(code)
        assert ctrl.run_evaluate({}) == "partially_implemented"


# ---------------------------------------------------------------------------
# _parse_list_format
# ---------------------------------------------------------------------------

class TestParseListFormat:
    def test_basic_parse(self):
        from unimonitor.grc.control_loader import _parse_list_format
        ctrl = {
            "id": "CTRL-001",
            "title": "MFA Enforcement",
            "severity": "CRITICAL",
            "category": "identity",
            "service": "entra_id",
            "evaluate": "def evaluate(data):\n    return 'implemented'",
        }
        defn = _parse_list_format(ctrl)
        assert defn is not None
        assert defn.id == "CTRL-001"
        assert defn.title == "MFA Enforcement"
        assert defn.severity == "CRITICAL"

    def test_missing_id_returns_none(self):
        from unimonitor.grc.control_loader import _parse_list_format
        result = _parse_list_format({"title": "No ID"})
        assert result is None

    def test_bare_code_wrapped_in_function(self):
        from unimonitor.grc.control_loader import _parse_list_format
        ctrl = {
            "id": "CTRL-002",
            "evaluate": "return 'implemented'",
        }
        defn = _parse_list_format(ctrl)
        assert defn is not None
        # Should have wrapped into a function
        assert "def evaluate(data):" in defn._evaluate_code

    def test_no_evaluate_defaults_to_not_implemented(self):
        from unimonitor.grc.control_loader import _parse_list_format
        ctrl = {"id": "CTRL-003", "title": "No eval"}
        defn = _parse_list_format(ctrl)
        assert defn is not None
        assert "not_implemented" in defn._evaluate_code

    def test_severity_uppercase(self):
        from unimonitor.grc.control_loader import _parse_list_format
        ctrl = {"id": "C4", "severity": "medium"}
        defn = _parse_list_format(ctrl)
        assert defn.severity == "MEDIUM"

    def test_defaults_for_missing_fields(self):
        from unimonitor.grc.control_loader import _parse_list_format
        defn = _parse_list_format({"id": "C5"})
        assert defn.category == ""
        assert defn.service == ""
        assert defn.compliance_mapping == {}

    def test_compliance_mapping_preserved(self):
        from unimonitor.grc.control_loader import _parse_list_format
        ctrl = {
            "id": "C6",
            "compliance_mapping": {"iso_27001": ["A.9.1"]},
        }
        defn = _parse_list_format(ctrl)
        assert defn.compliance_mapping == {"iso_27001": ["A.9.1"]}


# ---------------------------------------------------------------------------
# _parse_legacy_format
# ---------------------------------------------------------------------------

class TestParseLegacyFormat:
    def test_basic_legacy_parse(self):
        from unimonitor.grc.control_loader import _parse_legacy_format
        raw = {
            "control_id": "ENT-001",
            "metadata": {"name": "Legacy Control", "severity": "HIGH"},
            "check": {},
        }
        defn = _parse_legacy_format(raw, Path("/controls/entra_id/ENT-001.yaml"))
        assert defn is not None
        assert defn.id == "ENT-001"
        assert defn.severity == "HIGH"
        assert defn.service == "entra_id"

    def test_missing_control_id_returns_none(self):
        from unimonitor.grc.control_loader import _parse_legacy_format
        raw = {"metadata": {}, "check": {}}
        result = _parse_legacy_format(raw, Path("/controls/x/x.yaml"))
        assert result is None

    def test_condition_generates_evaluate_code(self):
        from unimonitor.grc.control_loader import _parse_legacy_format
        raw = {
            "control_id": "ENT-002",
            "check": {
                "evaluation": {
                    "condition": "data.get('mfa_enabled')"
                }
            },
        }
        defn = _parse_legacy_format(raw, Path("/controls/x/x.yaml"))
        assert defn is not None
        assert "mfa_enabled" in defn._evaluate_code
        # Verify it runs correctly
        assert defn.run_evaluate({"mfa_enabled": True}) == "implemented"
        assert defn.run_evaluate({}) == "not_implemented"

    def test_no_condition_defaults_to_not_implemented(self):
        from unimonitor.grc.control_loader import _parse_legacy_format
        raw = {"control_id": "ENT-003", "check": {"evaluation": {}}}
        defn = _parse_legacy_format(raw, Path("/x.yaml"))
        assert "not_implemented" in defn._evaluate_code

    def test_service_derived_from_parent_dir(self):
        from unimonitor.grc.control_loader import _parse_legacy_format
        raw = {"control_id": "INT-001"}
        defn = _parse_legacy_format(raw, Path("/controls/intune/INT-001.yaml"))
        assert defn.service == "intune"


# ---------------------------------------------------------------------------
# ControlLoader with temporary directory
# ---------------------------------------------------------------------------

class TestControlLoader:
    def _write_yaml(self, directory: Path, filename: str, content: str) -> Path:
        (directory / filename).write_text(textwrap.dedent(content))
        return directory / filename

    def test_load_all_from_list_format(self):
        from unimonitor.grc.control_loader import ControlLoader
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            self._write_yaml(d, "ctrls.yaml", """\
                controls:
                  - id: TEST-001
                    title: "Test Control"
                    severity: HIGH
                    category: identity
                    service: entra_id
                    evaluate: |
                      def evaluate(data):
                          return 'implemented'
                """)
            loader = ControlLoader(controls_dir=str(d))
            definitions = loader.load_all()
        assert len(definitions) == 1
        assert definitions[0].id == "TEST-001"

    def test_load_all_from_legacy_format(self):
        from unimonitor.grc.control_loader import ControlLoader
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            self._write_yaml(d, "legacy.yaml", """\
                control_id: ENT-999
                metadata:
                  name: Legacy
                  severity: MEDIUM
                check: {}
                """)
            loader = ControlLoader(controls_dir=str(d))
            definitions = loader.load_all()
        assert len(definitions) == 1
        assert definitions[0].id == "ENT-999"

    def test_missing_directory_returns_empty(self):
        from unimonitor.grc.control_loader import ControlLoader
        loader = ControlLoader(controls_dir="/nonexistent/path/controls")
        result = loader.load_all()
        assert result == []

    def test_invalid_yaml_skipped(self):
        from unimonitor.grc.control_loader import ControlLoader
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "bad.yaml").write_text("{{ invalid: yaml: content ]]")
            loader = ControlLoader(controls_dir=str(d))
            result = loader.load_all()
        assert result == []

    def test_multiple_controls_in_one_file(self):
        from unimonitor.grc.control_loader import ControlLoader
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            self._write_yaml(d, "multi.yaml", """\
                controls:
                  - id: C1
                    title: First
                  - id: C2
                    title: Second
                """)
            loader = ControlLoader(controls_dir=str(d))
            defs = loader.load_all()
        assert len(defs) == 2

    def test_control_missing_id_skipped(self):
        from unimonitor.grc.control_loader import ControlLoader
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            self._write_yaml(d, "noid.yaml", """\
                controls:
                  - title: No ID here
                  - id: C1
                    title: Good one
                """)
            loader = ControlLoader(controls_dir=str(d))
            defs = loader.load_all()
        assert len(defs) == 1
        assert defs[0].id == "C1"


# ---------------------------------------------------------------------------
# load_all_controls (module-level function, reads from CONTROLS_DIR)
# ---------------------------------------------------------------------------

class TestLoadAllControls:
    def test_returns_list(self):
        from unimonitor.grc.control_loader import load_all_controls
        # May return 0 or more controls depending on controls/ directory
        result = load_all_controls()
        assert isinstance(result, list)

    def test_missing_controls_dir_returns_empty(self):
        from unimonitor.grc.control_loader import load_all_controls
        with patch("unimonitor.grc.control_loader.CONTROLS_DIR", Path("/nonexistent")):
            result = load_all_controls()
        assert result == []


# ---------------------------------------------------------------------------
# load_controls_for_frameworks
# ---------------------------------------------------------------------------

class TestLoadControlsForFrameworks:
    def _make_control(self, ctrl_id, frameworks):
        return {"id": ctrl_id, "frameworks": frameworks}

    def test_no_framework_ids_returns_all(self):
        from unimonitor.grc.control_loader import load_controls_for_frameworks
        controls = [
            self._make_control("C1", ["iso27001_2022"]),
            self._make_control("C2", ["soc2"]),
        ]
        with patch("unimonitor.grc.control_loader.load_all_controls", return_value=controls):
            result = load_controls_for_frameworks([])
        assert len(result) == 2

    def test_filters_to_matching_framework(self):
        from unimonitor.grc.control_loader import load_controls_for_frameworks
        controls = [
            self._make_control("C1", ["iso27001_2022"]),
            self._make_control("C2", ["soc2"]),
            self._make_control("C3", ["iso27001_2022", "soc2"]),
        ]
        with patch("unimonitor.grc.control_loader.load_all_controls", return_value=controls):
            result = load_controls_for_frameworks(["iso27001_2022"])
        ids = [c["id"] for c in result]
        assert "C1" in ids
        assert "C3" in ids
        assert "C2" not in ids

    def test_all_framework_includes_everything(self):
        from unimonitor.grc.control_loader import load_controls_for_frameworks
        controls = [
            self._make_control("C1", ["iso27001_2022"]),
            self._make_control("C2", ["soc2"]),
        ]
        with patch("unimonitor.grc.control_loader.load_all_controls", return_value=controls):
            result = load_controls_for_frameworks(["all"])
        assert len(result) == 2

    def test_no_match_returns_all(self):
        """When no controls match, all controls are returned as universal fallback."""
        from unimonitor.grc.control_loader import load_controls_for_frameworks
        controls = [
            self._make_control("C1", ["iso27001_2022"]),
        ]
        with patch("unimonitor.grc.control_loader.load_all_controls", return_value=controls):
            result = load_controls_for_frameworks(["nonexistent_fw"])
        # Falls back to returning all controls
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _normalise
# ---------------------------------------------------------------------------

class TestNormalise:
    def _make_raw(self, ctrl_id="IDN-001", fw_key="iso_27001"):
        return {
            "control_id": ctrl_id,
            "metadata": {"name": "Test", "severity": "high", "tags": ["mfa"]},
            "check": {
                "evaluation": {"condition": "data.get('x')"},
                "data_requirements": [{"endpoint": "/v1.0/users"}],
            },
            "remediation": {
                "summary": "Enable MFA",
                "steps": [{"action": "Go to settings"}],
            },
            "compliance_mapping": {fw_key: ["A.9.1"]},
        }

    def test_id_preserved(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw("APP-001"), Path("/controls/apps/f.yaml"))
        assert result["id"] == "APP-001"

    def test_name_from_metadata(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw(), Path("/controls/x/f.yaml"))
        assert result["name"] == "Test"

    def test_service_from_parent_dir(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw(), Path("/controls/devices/f.yaml"))
        assert result["service"] == "devices"

    def test_category_mapped_from_prefix(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw("IDN-001"), Path("/controls/x/f.yaml"))
        assert result["category"] == "Identity"

    def test_frameworks_mapped_from_compliance_keys(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw(fw_key="iso_27001"), Path("/controls/x/f.yaml"))
        assert "iso27001_2022" in result["frameworks"]

    def test_remediation_summary(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw(), Path("/controls/x/f.yaml"))
        assert result["remediation_summary"] == "Enable MFA"

    def test_remediation_steps_extracted(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw(), Path("/controls/x/f.yaml"))
        assert result["remediation_steps"] == ["Go to settings"]

    def test_data_keys_from_data_requirements(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw(), Path("/controls/x/f.yaml"))
        assert "v1.0_users" in result["data_keys"]

    def test_tags_from_metadata(self):
        from unimonitor.grc.control_loader import _normalise
        result = _normalise(self._make_raw(), Path("/controls/x/f.yaml"))
        assert "mfa" in result["tags"]

    def test_unknown_fw_key_not_added(self):
        from unimonitor.grc.control_loader import _normalise
        raw = self._make_raw(fw_key="unknown_fw_xyz")
        result = _normalise(raw, Path("/controls/x/f.yaml"))
        assert result["frameworks"] == []
