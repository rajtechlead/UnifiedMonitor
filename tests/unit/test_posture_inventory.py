"""The automatic posture inventory and the requirement/level catalogue."""

from __future__ import annotations

from unimonitor.posture.assemble import assemble, load_inventory, write_inventory


class TestAssembleInventory:
    def test_aws_storage_security_and_logging_become_resources(self):
        inventory = assemble(
            {
                "aws_s3_buckets": [
                    {
                        "Name": "public-bucket",
                        "PublicAccessBlock": {"BlockPublicAcls": False, "BlockPublicPolicy": False, "RestrictPublicBuckets": False},
                        "Encryption": {},
                    }
                ],
                "aws_security_groups": [
                    {
                        "GroupId": "sg-1",
                        "GroupName": "web",
                        "IpPermissions": [{"FromPort": 22, "ToPort": 22, "IpProtocol": "tcp", "Cidrs": ["0.0.0.0/0"]}],
                    }
                ],
                "aws_cloudtrail_trails": [{"Name": "main", "IsLogging": True, "IsMultiRegionTrail": True}],
                "aws_root_mfa_enabled": False,
            }
        )
        by_type = {resource["type"]: resource for resource in inventory["resources"]}

        assert by_type["storage"]["public"] is True
        assert by_type["storage"]["encrypted"] is False
        assert by_type["security_group"]["open_admin_ports"] is True
        assert by_type["security_group"]["open_ingress"] is True
        assert by_type["logging"]["logging_enabled"] is True
        assert by_type["tenant_settings"]["mfa_enforced"] is False

    def test_gcp_and_workspace_are_assembled(self):
        inventory = assemble(
            {
                "gcp_storage_buckets": [
                    {"name": "bucket", "iamConfiguration": {"publicAccessPrevention": "enforced"}, "encryption": {"defaultKmsKeyName": "kms/1"}}
                ],
                "gcp_audit_log_sinks": [{"name": "sink", "destination": "storage.googleapis.com/logs"}],
                "gws_two_step_enforcement": {"enforced": True, "enrollmentPct": 100},
                "gws_super_admins": [{"email": "admin@example.com"}],
            }
        )
        by_type: dict[str, list[dict]] = {}
        for resource in inventory["resources"]:
            by_type.setdefault(resource["type"], []).append(resource)

        assert by_type["storage"][0]["public"] is False
        assert by_type["logging"][0]["logging_enabled"] is True
        assert by_type["tenant_settings"][0]["mfa_enforced"] is True
        assert by_type["identity"][0]["admin"] is True

    def test_an_empty_collection_produces_no_inventories(self):
        assert assemble({}) == {"resources": [], "edges": []}

    def test_a_malformed_section_is_skipped(self):
        inventory = assemble({"aws_s3_buckets": "not-a-list", "aws_cloudtrail_trails": [{"Name": "t", "IsLogging": False}]})
        assert [resource["type"] for resource in inventory["resources"]] == ["logging"]

    def test_the_inventory_round_trips_through_disk(self, tmp_path, monkeypatch):
        from unimonitor.config import get_settings

        monkeypatch.setattr(get_settings(), "POSTURE_AUTO_INVENTORY_PATH", str(tmp_path))
        monkeypatch.setattr(get_settings(), "POSTURE_AUTO_INVENTORY", True)

        written = write_inventory(assemble({"aws_cloudtrail_trails": [{"Name": "t", "IsLogging": True}]}), "tenant-1")
        assert written is not None
        assert load_inventory("tenant-1")["resources"][0]["type"] == "logging"
        assert (tmp_path / "latest.json").is_file()


class TestRequirementCatalogue:
    def test_cpcsc_keeps_its_official_levels(self):
        from unimonitor.grc.requirements import catalogue

        result = catalogue("cpcsc")
        assert result["catalogue"] == "official"
        assert result["requirement_count"] == 98
        assert {level["level"] for level in result["levels"]} == {1, 2}

    def test_nis2_uses_its_named_measures(self):
        from unimonitor.grc.requirements import requirements_for

        rows = requirements_for("nis2")
        assert len(rows) >= 10
        assert all(row["source"] == "mapping" for row in rows)
        assert all(row["controls"] for row in rows)

    def test_a_derived_framework_still_has_requirements(self):
        from unimonitor.grc.requirements import requirements_for

        rows = requirements_for("fedramp-low")
        assert rows
        assert all(row["level"] == 1 for row in rows)
        assert all(row["level_name"] == "Low" for row in rows)
        assert {row["id"] for row in rows} == {row["id"] for row in requirements_for("nist-800-53-r5")}

    def test_every_framework_resolves_a_catalogue(self):
        from unimonitor.grc.frameworks import FRAMEWORKS
        from unimonitor.grc.requirements import levels_for, requirements_for

        for meta in FRAMEWORKS.values():
            assert requirements_for(meta.slug), meta.slug
            assert levels_for(meta.slug)
