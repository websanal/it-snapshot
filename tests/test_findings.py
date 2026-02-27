"""Unit tests for the findings engine and risk scoring.

All tests operate on plain dicts — no I/O, no mocking required.
Run with:  python -m pytest tests/  or  python -m unittest discover tests/
"""

import unittest

from src.report.findings import compute_findings, _SEVERITY_WEIGHTS


def _clean_report(**overrides) -> dict:
    """Return a baseline 'healthy' report that triggers no findings."""
    base = {
        "security": {
            "antivirus": [{"name": "Windows Defender", "enabled": True, "up_to_date": True}],
            "firewall": {
                "domain_enabled":  True,
                "private_enabled": True,
                "public_enabled":  True,
            },
            "uac_enabled": True,
            "encryption": {"bitlocker_volumes": []},
        },
        "logs": {"failed_logins": []},
        "reboot": {"uptime": {"days": 5, "hours": 0, "minutes": 0, "seconds": 0}},
        "storage": [{"mountpoint": "C:\\", "percent_used": 50.0, "status": "ok"}],
    }
    for k, v in overrides.items():
        base[k] = v
    return base


class TestFindingsSEC001(unittest.TestCase):
    """SEC-001: no active antivirus."""

    def test_no_av_list_triggers(self):
        r = _clean_report()
        r["security"]["antivirus"] = []
        findings, _ = compute_findings(r)
        self.assertIn("SEC-001", [f["id"] for f in findings])

    def test_disabled_av_triggers(self):
        r = _clean_report()
        r["security"]["antivirus"] = [{"name": "Old AV", "enabled": False}]
        findings, _ = compute_findings(r)
        self.assertIn("SEC-001", [f["id"] for f in findings])

    def test_active_av_suppresses(self):
        r = _clean_report()
        findings, _ = compute_findings(r)
        self.assertNotIn("SEC-001", [f["id"] for f in findings])

    def test_sec001_severity_is_high(self):
        r = _clean_report()
        r["security"]["antivirus"] = []
        findings, _ = compute_findings(r)
        f = next(x for x in findings if x["id"] == "SEC-001")
        self.assertEqual(f["severity"], "high")


class TestFindingsSEC002(unittest.TestCase):
    """SEC-002: UAC disabled."""

    def test_uac_false_triggers(self):
        r = _clean_report()
        r["security"]["uac_enabled"] = False
        findings, _ = compute_findings(r)
        self.assertIn("SEC-002", [f["id"] for f in findings])

    def test_uac_true_suppresses(self):
        r = _clean_report()
        findings, _ = compute_findings(r)
        self.assertNotIn("SEC-002", [f["id"] for f in findings])

    def test_uac_none_suppresses(self):
        # None means "unknown" — don't raise a finding
        r = _clean_report()
        r["security"]["uac_enabled"] = None
        findings, _ = compute_findings(r)
        self.assertNotIn("SEC-002", [f["id"] for f in findings])


class TestFindingsSEC003(unittest.TestCase):
    """SEC-003: public firewall disabled."""

    def test_public_disabled_triggers(self):
        r = _clean_report()
        r["security"]["firewall"]["public_enabled"] = False
        findings, _ = compute_findings(r)
        self.assertIn("SEC-003", [f["id"] for f in findings])

    def test_public_enabled_suppresses(self):
        r = _clean_report()
        findings, _ = compute_findings(r)
        self.assertNotIn("SEC-003", [f["id"] for f in findings])

    def test_public_none_suppresses(self):
        r = _clean_report()
        r["security"]["firewall"]["public_enabled"] = None
        findings, _ = compute_findings(r)
        self.assertNotIn("SEC-003", [f["id"] for f in findings])


class TestFindingsSEC004(unittest.TestCase):
    """SEC-004: BitLocker not active."""

    def test_unprotected_volume_triggers(self):
        r = _clean_report()
        r["security"]["encryption"]["bitlocker_volumes"] = [
            {"mount_point": "C:\\", "protection_status": 0}
        ]
        findings, _ = compute_findings(r)
        self.assertIn("SEC-004", [f["id"] for f in findings])

    def test_protected_volume_suppresses(self):
        r = _clean_report()
        r["security"]["encryption"]["bitlocker_volumes"] = [
            {"mount_point": "C:\\", "protection_status": 1}
        ]
        findings, _ = compute_findings(r)
        self.assertNotIn("SEC-004", [f["id"] for f in findings])

    def test_no_bitlocker_data_suppresses(self):
        r = _clean_report()
        r["security"]["encryption"]["bitlocker_volumes"] = []
        findings, _ = compute_findings(r)
        self.assertNotIn("SEC-004", [f["id"] for f in findings])


class TestFindingsSEC005(unittest.TestCase):
    """SEC-005: failed login attempts."""

    def test_four_logins_suppressed(self):
        r = _clean_report()
        r["logs"]["failed_logins"] = [{}] * 4
        findings, _ = compute_findings(r)
        self.assertNotIn("SEC-005", [f["id"] for f in findings])

    def test_five_logins_triggers_medium(self):
        r = _clean_report()
        r["logs"]["failed_logins"] = [{}] * 5
        findings, _ = compute_findings(r)
        ids = [f["id"] for f in findings]
        self.assertIn("SEC-005", ids)
        f = next(x for x in findings if x["id"] == "SEC-005")
        self.assertEqual(f["severity"], "medium")

    def test_ten_logins_triggers_high(self):
        r = _clean_report()
        r["logs"]["failed_logins"] = [{}] * 10
        findings, _ = compute_findings(r)
        f = next(x for x in findings if x["id"] == "SEC-005")
        self.assertEqual(f["severity"], "high")


class TestFindingsSYS001(unittest.TestCase):
    """SYS-001: long uptime."""

    def test_5_days_suppressed(self):
        r = _clean_report()
        findings, _ = compute_findings(r)
        self.assertNotIn("SYS-001", [f["id"] for f in findings])

    def test_31_days_triggers_medium(self):
        r = _clean_report()
        r["reboot"]["uptime"]["days"] = 31
        findings, _ = compute_findings(r)
        f = next((x for x in findings if x["id"] == "SYS-001"), None)
        self.assertIsNotNone(f)
        self.assertEqual(f["severity"], "medium")

    def test_61_days_triggers_high(self):
        r = _clean_report()
        r["reboot"]["uptime"]["days"] = 61
        findings, _ = compute_findings(r)
        f = next((x for x in findings if x["id"] == "SYS-001"), None)
        self.assertIsNotNone(f)
        self.assertEqual(f["severity"], "high")


class TestFindingsSYS002(unittest.TestCase):
    """SYS-002: disk full."""

    def test_50pct_suppressed(self):
        r = _clean_report()
        findings, _ = compute_findings(r)
        self.assertNotIn("SYS-002", [f["id"] for f in findings])

    def test_91pct_triggers_medium(self):
        r = _clean_report()
        r["storage"] = [{"mountpoint": "C:\\", "percent_used": 91.0, "status": "ok"}]
        findings, _ = compute_findings(r)
        f = next((x for x in findings if x["id"] == "SYS-002"), None)
        self.assertIsNotNone(f)
        self.assertEqual(f["severity"], "medium")

    def test_96pct_triggers_high(self):
        r = _clean_report()
        r["storage"] = [{"mountpoint": "C:\\", "percent_used": 96.0, "status": "ok"}]
        findings, _ = compute_findings(r)
        f = next((x for x in findings if x["id"] == "SYS-002"), None)
        self.assertIsNotNone(f)
        self.assertEqual(f["severity"], "high")

    def test_multiple_disks_multiple_findings(self):
        r = _clean_report()
        r["storage"] = [
            {"mountpoint": "C:\\", "percent_used": 92.0, "status": "ok"},
            {"mountpoint": "D:\\", "percent_used": 97.0, "status": "ok"},
        ]
        findings, _ = compute_findings(r)
        sys002 = [f for f in findings if f["id"] == "SYS-002"]
        self.assertEqual(len(sys002), 2)


class TestRiskScoring(unittest.TestCase):
    """Risk score computation."""

    def test_clean_report_scores_zero(self):
        r = _clean_report()
        _, risk = compute_findings(r)
        self.assertEqual(risk["score"], 0)
        self.assertEqual(risk["level"], "low")

    def test_score_capped_at_100(self):
        # Trigger as many high-severity findings as possible
        r = _clean_report()
        r["security"]["antivirus"]              = []
        r["security"]["uac_enabled"]            = False
        r["security"]["firewall"]["public_enabled"] = False
        r["logs"]["failed_logins"]              = [{}] * 15
        r["reboot"]["uptime"]["days"]           = 65
        r["storage"]                            = [
            {"mountpoint": "C:\\", "percent_used": 97.0, "status": "ok"}
        ]
        _, risk = compute_findings(r)
        self.assertLessEqual(risk["score"], 100)

    def test_single_high_finding_gives_medium_level(self):
        # 1 high finding = 30 points → "medium" level (11-30)
        r = _clean_report()
        r["security"]["antivirus"] = []
        _, risk = compute_findings(r)
        self.assertIn(risk["level"], ("medium",))

    def test_three_high_findings_give_critical_level(self):
        # 3 high = 90 points → critical (>=61)
        r = _clean_report()
        r["security"]["antivirus"]                 = []
        r["security"]["uac_enabled"]               = False
        r["security"]["firewall"]["public_enabled"] = False
        _, risk = compute_findings(r)
        self.assertEqual(risk["level"], "critical")

    def test_factors_list_contains_finding_ids(self):
        r = _clean_report()
        r["security"]["antivirus"] = []
        _, risk = compute_findings(r)
        self.assertIn("SEC-001", risk["factors"])

    def test_severity_weights_known(self):
        self.assertEqual(_SEVERITY_WEIGHTS["low"],      5)
        self.assertEqual(_SEVERITY_WEIGHTS["medium"],  15)
        self.assertEqual(_SEVERITY_WEIGHTS["high"],    30)
        self.assertEqual(_SEVERITY_WEIGHTS["critical"], 50)


if __name__ == "__main__":
    unittest.main()
