"""Tests for the Pydantic v2 schema models.

Run with:  python -m pytest tests/  or  python -m unittest discover tests/
"""

import unittest

from src.models.schema import (
    CpuInfo,
    RamInfo,
    GpuInfo,
    HardwareSection,
    StorageVolume,
    NetworkInterface,
    NetworkSection,
    SoftwareItem,
    SoftwareSection,
    AntiVirusItem,
    FirewallStatus,
    SecuritySection,
    LogEntry,
    LogsSection,
    DeviceIdentitySection,
    Finding,
    RiskScore,
    SnapshotReport,
)


class TestLeafModels(unittest.TestCase):
    def test_cpu_all_optional(self):
        cpu = CpuInfo()
        self.assertIsNone(cpu.brand)
        self.assertIsNone(cpu.physical_cores)

    def test_cpu_with_values(self):
        cpu = CpuInfo(physical_cores=8, logical_cores=16, max_frequency_mhz=3600.0)
        self.assertEqual(cpu.physical_cores, 8)
        self.assertEqual(cpu.max_frequency_mhz, 3600.0)

    def test_ram_rounding(self):
        ram = RamInfo(total_gb=31.97, percent_used=42.5)
        self.assertAlmostEqual(ram.total_gb, 31.97)

    def test_gpu_optional(self):
        gpu = GpuInfo(name="NVIDIA RTX 4060", vram_mb=8192)
        self.assertEqual(gpu.name, "NVIDIA RTX 4060")
        self.assertIsNone(gpu.driver_version)

    def test_storage_volume_defaults(self):
        vol = StorageVolume()
        self.assertEqual(vol.status, "ok")
        self.assertIsNone(vol.percent_used)

    def test_network_interface_required_name(self):
        iface = NetworkInterface(name="Ethernet 0")
        self.assertEqual(iface.name, "Ethernet 0")
        self.assertFalse(iface.is_up)
        self.assertEqual(iface.ip_addresses, [])

    def test_finding_required_fields(self):
        f = Finding(id="SEC-001", severity="high", title="No AV", detail="...")
        self.assertEqual(f.id, "SEC-001")
        self.assertEqual(f.severity, "high")

    def test_risk_score_defaults(self):
        rs = RiskScore()
        self.assertEqual(rs.score, 0)
        self.assertEqual(rs.level, "low")
        self.assertEqual(rs.factors, [])


class TestSectionModels(unittest.TestCase):
    def test_hardware_section_empty(self):
        hw = HardwareSection()
        self.assertIsNone(hw.cpu)
        self.assertEqual(hw.gpu, [])

    def test_hardware_section_with_cpu(self):
        hw = HardwareSection(cpu=CpuInfo(physical_cores=4))
        self.assertEqual(hw.cpu.physical_cores, 4)

    def test_software_section_count(self):
        sw = SoftwareSection(
            installed=[SoftwareItem(name="Notepad++", version="8.6")],
            count=1,
        )
        self.assertEqual(sw.count, 1)
        self.assertEqual(sw.installed[0].name, "Notepad++")

    def test_security_section_defaults(self):
        sec = SecuritySection()
        self.assertEqual(sec.antivirus, [])
        self.assertIsNone(sec.uac_enabled)
        self.assertIsNone(sec.gatekeeper_enabled)

    def test_firewall_status_all_none(self):
        fw = FirewallStatus()
        self.assertIsNone(fw.domain_enabled)
        self.assertIsNone(fw.public_enabled)

    def test_logs_section_empty(self):
        logs = LogsSection()
        self.assertEqual(logs.recent_errors, [])
        self.assertEqual(logs.failed_logins, [])

    def test_network_section_default(self):
        net = NetworkSection()
        self.assertEqual(net.interfaces, [])
        self.assertIsNone(net.default_gateway)

    def test_device_identity_default(self):
        di = DeviceIdentitySection()
        self.assertIsNone(di.hostname)
        self.assertEqual(di.primary_macs, [])


class TestSnapshotReport(unittest.TestCase):
    def _minimal_report(self) -> SnapshotReport:
        return SnapshotReport(run_id="test-uuid", collected_at="2026-01-01T00:00:00+00:00")

    def test_instantiation(self):
        r = self._minimal_report()
        self.assertEqual(r.schema_version, "2.0")
        self.assertEqual(r.agent_version, "2.0.0")

    def test_legacy_keys_default_empty(self):
        r = self._minimal_report()
        self.assertEqual(r.snapshot, {})
        self.assertEqual(r.os, {})
        self.assertEqual(r.reboot, {})
        self.assertEqual(r.disks, [])

    def test_findings_default_empty(self):
        r = self._minimal_report()
        self.assertEqual(r.findings, [])
        self.assertEqual(r.risk_score.level, "low")

    def test_model_dump_round_trip(self):
        r = self._minimal_report()
        r.hardware = HardwareSection(cpu=CpuInfo(physical_cores=8))
        d = r.model_dump()
        self.assertEqual(d["hardware"]["cpu"]["physical_cores"], 8)
        self.assertEqual(d["schema_version"], "2.0")

    def test_errors_list(self):
        r = self._minimal_report()
        r.errors = ["collector_x: timeout"]
        self.assertEqual(len(r.errors), 1)


if __name__ == "__main__":
    unittest.main()
