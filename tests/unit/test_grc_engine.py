"""
Unit tests for the GRC engine — control loading, scoring, evaluate().
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


# ── Control loader ────────────────────────────────────────────────────────────

class TestControlLoader:
    def test_load_yaml_control(self, tmp_path: Path):
        """Controls load from YAML and parse into ControlDefinition objects."""
        yaml_content = """
controls:
  - id: TEST-001
    title: Test MFA Control
    description: Ensure MFA is enabled for all users
    severity: CRITICAL
    category: identity
    service: entra_id
    compliance_mapping:
      iso_27001_2022: ["A.9.4.2"]
      nist_csf_2: ["PR.AA-02"]
    collector: entra_identity
    data_path: "mfa_data"
    evaluate: |
      def evaluate(data):
          if not data:
              return "not_implemented"
          enabled = data.get("mfa_enabled_percent", 0)
          if enabled >= 95:
              return "implemented"
          elif enabled >= 50:
              return "partially_implemented"
          return "not_implemented"
"""
        control_file = tmp_path / "test_controls.yaml"
        control_file.write_text(yaml_content)

        from unimonitor.grc.control_loader import ControlLoader
        loader = ControlLoader(controls_dir=str(tmp_path))
        controls = loader.load_all()

        assert len(controls) == 1
        ctrl = controls[0]
        assert ctrl.id == "TEST-001"
        assert ctrl.title == "Test MFA Control"
        assert ctrl.severity == "CRITICAL"
        assert "iso_27001_2022" in ctrl.compliance_mapping
        assert ctrl.compliance_mapping["iso_27001_2022"] == ["A.9.4.2"]

    def test_evaluate_function_implemented(self, tmp_path: Path):
        """evaluate() returns 'implemented' for passing data."""
        yaml_content = """
controls:
  - id: TEST-002
    title: Test Control
    description: Test
    severity: HIGH
    category: test
    service: test
    compliance_mapping: {}
    collector: test_collector
    data_path: "test_data"
    evaluate: |
      def evaluate(data):
          return "implemented" if data.get("ok") else "not_implemented"
"""
        (tmp_path / "test2.yaml").write_text(yaml_content)
        from unimonitor.grc.control_loader import ControlLoader
        loader = ControlLoader(controls_dir=str(tmp_path))
        controls = loader.load_all()
        ctrl = controls[0]

        result = ctrl.run_evaluate({"ok": True})
        assert result == "implemented"

        result = ctrl.run_evaluate({"ok": False})
        assert result == "not_implemented"

    def test_evaluate_function_partial(self, tmp_path: Path):
        """evaluate() can return 'partially_implemented'."""
        yaml_content = """
controls:
  - id: TEST-003
    title: Partial Control
    description: Test
    severity: MEDIUM
    category: test
    service: test
    compliance_mapping: {}
    collector: test_collector
    data_path: "test_data"
    evaluate: |
      def evaluate(data):
          coverage = data.get("coverage", 0)
          if coverage >= 90:
              return "implemented"
          elif coverage >= 50:
              return "partially_implemented"
          return "not_implemented"
"""
        (tmp_path / "test3.yaml").write_text(yaml_content)
        from unimonitor.grc.control_loader import ControlLoader
        loader = ControlLoader(controls_dir=str(tmp_path))
        controls = loader.load_all()
        ctrl = controls[0]

        assert ctrl.run_evaluate({"coverage": 95}) == "implemented"
        assert ctrl.run_evaluate({"coverage": 70}) == "partially_implemented"
        assert ctrl.run_evaluate({"coverage": 20}) == "not_implemented"

    def test_load_multiple_yaml_files(self, tmp_path: Path):
        """Loader finds all YAML files recursively."""
        (tmp_path / "subdir").mkdir()
        for i, path in enumerate(["a.yaml", "subdir/b.yaml"]):
            (tmp_path / path).write_text(f"""
controls:
  - id: CTRL-{i:03d}
    title: Control {i}
    description: Test
    severity: LOW
    category: test
    service: test
    compliance_mapping: {{}}
    collector: c
    data_path: d
    evaluate: |
      def evaluate(data): return "implemented"
""")
        from unimonitor.grc.control_loader import ControlLoader
        loader = ControlLoader(controls_dir=str(tmp_path))
        controls = loader.load_all()
        assert len(controls) == 2


# ── Scoring engine ────────────────────────────────────────────────────────────

class TestScoringEngine:
    def test_severity_weights(self):
        """Severity weights are correct per spec."""
        from unimonitor.grc.scoring import SEVERITY_WEIGHTS
        assert SEVERITY_WEIGHTS["CRITICAL"] == 10
        assert SEVERITY_WEIGHTS["HIGH"] == 8
        assert SEVERITY_WEIGHTS["MEDIUM"] == 5
        assert SEVERITY_WEIGHTS["LOW"] == 3
        assert SEVERITY_WEIGHTS["INFORMATIONAL"] == 1

    def test_score_all_implemented(self):
        """100% score when all controls are implemented."""
        from unimonitor.grc.scoring import compute_score

        findings = [
            {"severity": "CRITICAL", "state": "implemented"},
            {"severity": "HIGH", "state": "implemented"},
            {"severity": "MEDIUM", "state": "implemented"},
        ]
        score = compute_score(findings)
        assert score == 100

    def test_score_all_not_implemented(self):
        """Score is 0 when all controls are not implemented."""
        from unimonitor.grc.scoring import compute_score

        findings = [
            {"severity": "CRITICAL", "state": "not_implemented"},
            {"severity": "HIGH", "state": "not_implemented"},
        ]
        score = compute_score(findings)
        assert score == 0

    def test_score_mixed(self):
        """Mixed results produce a weighted score between 0 and 100."""
        from unimonitor.grc.scoring import compute_score

        findings = [
            {"severity": "CRITICAL", "state": "implemented"},       # weight 10
            {"severity": "HIGH", "state": "not_implemented"},        # weight 8
            {"severity": "MEDIUM", "state": "partially_implemented"},# weight 5, half credit
        ]
        score = compute_score(findings)
        # 10 + 0 + 2.5 out of 10 + 8 + 5 = 12.5 / 23 ≈ 54.3
        assert 50 <= score <= 60

    def test_score_excludes_not_applicable(self):
        """N/A findings are excluded from scoring denominator."""
        from unimonitor.grc.scoring import compute_score

        findings = [
            {"severity": "CRITICAL", "state": "implemented"},
            {"severity": "HIGH", "state": "not_applicable"},  # excluded
        ]
        score = compute_score(findings)
        # Only CRITICAL counts: 10/10 = 100
        assert score == 100

    def test_score_empty_findings(self):
        """Empty findings list returns 100 (nothing failing)."""
        from unimonitor.grc.scoring import compute_score
        assert compute_score([]) == 100


# ── Framework crosswalk ───────────────────────────────────────────────────────

class TestFrameworkCrosswalk:
    def test_crosswalk_lookup(self, tmp_path: Path):
        """Controls are indexed by framework control reference."""
        yaml_content = """
controls:
  - id: CTRL-ENT-001
    title: MFA Required
    description: Require MFA
    severity: CRITICAL
    category: identity
    service: entra_id
    compliance_mapping:
      iso_27001_2022: ["A.9.4.2", "A.9.4.3"]
      nist_csf_2: ["PR.AA-02"]
    collector: entra_identity
    data_path: mfa_data
    evaluate: |
      def evaluate(data): return "implemented"
"""
        (tmp_path / "ctrl.yaml").write_text(yaml_content)
        from unimonitor.grc.control_loader import ControlLoader
        from unimonitor.grc.crosswalk import FrameworkCrosswalk

        loader = ControlLoader(controls_dir=str(tmp_path))
        controls = loader.load_all()
        crosswalk = FrameworkCrosswalk(controls)

        # Look up by ISO reference
        matched = crosswalk.find_by_reference("iso_27001_2022", "A.9.4.2")
        assert any(c.id == "CTRL-ENT-001" for c in matched)

        # Look up by NIST reference
        matched = crosswalk.find_by_reference("nist_csf_2", "PR.AA-02")
        assert any(c.id == "CTRL-ENT-001" for c in matched)

        # Unknown reference returns empty
        matched = crosswalk.find_by_reference("iso_27001_2022", "X.99.99")
        assert matched == []
