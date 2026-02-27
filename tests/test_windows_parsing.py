"""Tests for Windows collector JSON-parsing logic.

Each test patches run_powershell to return a fixed JSON string, then verifies
the collector correctly parses and maps the fields. No real PowerShell is invoked.

Run with:  python -m pytest tests/  or  python -m unittest discover tests/
Skipped automatically on non-Windows (winreg not available).
"""

import json
import sys
import unittest
import unittest.mock as mock

# These tests only make sense on Windows where winreg is available.
# On other platforms the import itself would fail.
if sys.platform != "win32":
    raise unittest.SkipTest("Windows-only tests")

from src.collectors.windows.hardware import HardwareCollector
from src.collectors.windows.storage  import StorageCollector
from src.collectors.windows.network  import NetworkCollector
from src.collectors.windows.logs     import LogsCollector
from src.collectors.windows.os_info  import OsInfoCollector


PATCH_PS = "src.collectors.windows._utils.run_powershell"


# ── Hardware ──────────────────────────────────────────────────────────────────

class TestHardwareParsing(unittest.TestCase):

    def test_cpu_name_and_cores_parsed(self):
        cpu_json = json.dumps([{
            "Name": "Intel(R) Core(TM) i7-12700 CPU @ 2.10GHz",
            "Manufacturer": "GenuineIntel",
            "NumberOfCores": 12,
            "NumberOfLogicalProcessors": 20,
            "MaxClockSpeed": 2100,
        }])

        with mock.patch(PATCH_PS, return_value=cpu_json):
            result = HardwareCollector()._get_cpu()

        self.assertIn("i7-12700", result["name"])
        self.assertEqual(result["manufacturer"], "GenuineIntel")
        self.assertEqual(result["physical_cores"], 12)
        self.assertEqual(result["logical_processors"], 20)
        self.assertEqual(result["max_clock_mhz"], 2100)

    def test_cpu_name_stripped(self):
        cpu_json = json.dumps([{"Name": "  AMD Ryzen 9  ", "Manufacturer": "AuthenticAMD",
                                "NumberOfCores": 16, "NumberOfLogicalProcessors": 32,
                                "MaxClockSpeed": 4500}])
        with mock.patch(PATCH_PS, return_value=cpu_json):
            result = HardwareCollector()._get_cpu()
        self.assertEqual(result["name"], "AMD Ryzen 9")

    def test_ram_modules_parsed(self):
        mods_json = json.dumps([
            {"DeviceLocator": "DIMM A1", "Capacity": 17179869184,
             "Speed": 3200, "Manufacturer": "Samsung",
             "PartNumber": "M471A2K43DB1", "SerialNumber": "12345678"},
        ])
        with mock.patch(PATCH_PS, return_value=mods_json):
            # Patch psutil so the test isn't coupled to the host's RAM
            with mock.patch("psutil.virtual_memory") as vm:
                vm.return_value = mock.Mock(
                    total=17179869184, available=8589934592,
                    used=8589934592, percent=50.0,
                )
                result = HardwareCollector()._get_ram()

        self.assertEqual(len(result["modules"]), 1)
        m = result["modules"][0]
        self.assertEqual(m["slot"], "DIMM A1")
        self.assertAlmostEqual(m["capacity_gb"], 16.0, places=1)
        self.assertEqual(m["speed_mhz"], 3200)
        self.assertEqual(m["manufacturer"], "Samsung")
        self.assertEqual(m["serial"], "12345678")

    def test_ram_module_empty_serial_becomes_none(self):
        mods_json = json.dumps([
            {"DeviceLocator": "DIMM A1", "Capacity": 8589934592,
             "Speed": 2666, "Manufacturer": "Hynix",
             "PartNumber": "HMA82GS6AFR8N", "SerialNumber": "  "},
        ])
        with mock.patch(PATCH_PS, return_value=mods_json):
            with mock.patch("psutil.virtual_memory") as vm:
                vm.return_value = mock.Mock(total=0, available=0, used=0, percent=0)
                result = HardwareCollector()._get_ram()
        self.assertIsNone(result["modules"][0]["serial"])

    def test_gpu_vram_conversion(self):
        gpu_json = json.dumps([{
            "Name": "NVIDIA GeForce RTX 4070",
            "DriverVersion": "31.0.15.3179",
            "AdapterRAM": 8589934592,
        }])
        with mock.patch(PATCH_PS, return_value=gpu_json):
            gpus = HardwareCollector()._get_gpu()
        self.assertEqual(len(gpus), 1)
        self.assertEqual(gpus[0]["name"], "NVIDIA GeForce RTX 4070")
        self.assertEqual(gpus[0]["vram_mb"], 8192)

    def test_gpu_no_vram(self):
        gpu_json = json.dumps([{"Name": "Microsoft Basic Display Adapter",
                                "DriverVersion": "10.0.22631", "AdapterRAM": None}])
        with mock.patch(PATCH_PS, return_value=gpu_json):
            gpus = HardwareCollector()._get_gpu()
        self.assertIsNone(gpus[0]["vram_mb"])

    def test_bios_parsed(self):
        bios_json = json.dumps({
            "Manufacturer": "Dell Inc.",
            "SMBIOSBIOSVersion": "1.15.0",
            "ReleaseDate": "/Date(1704067200000)/",
        })
        with mock.patch(PATCH_PS, return_value=bios_json):
            bios = HardwareCollector()._get_bios()
        self.assertEqual(bios["vendor"], "Dell Inc.")
        self.assertEqual(bios["version"], "1.15.0")

    def test_motherboard_serial_none_on_empty(self):
        mobo_json = json.dumps({
            "Manufacturer": "ASUSTeK",
            "Product": "PRIME Z790-P",
            "SerialNumber": "",
        })
        with mock.patch(PATCH_PS, return_value=mobo_json):
            mobo = HardwareCollector()._get_motherboard()
        self.assertIsNone(mobo["serial"])

    def test_tpm_version_parsed(self):
        tpm_json   = json.dumps({"TpmPresent": True, "TpmReady": True})
        spec_json  = json.dumps({"SpecVersion": "2.0, 1.38, ..."})
        call_count = [0]

        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            return tpm_json if call_count[0] == 1 else spec_json

        with mock.patch(PATCH_PS, side_effect=side_effect):
            tpm = HardwareCollector()._get_tpm()

        self.assertTrue(tpm["present"])
        self.assertEqual(tpm["version"], "2.0")

    def test_secure_boot_true(self):
        with mock.patch(PATCH_PS, return_value="True"):
            sb = HardwareCollector()._get_secure_boot()
        self.assertTrue(sb["enabled"])

    def test_secure_boot_false(self):
        with mock.patch(PATCH_PS, return_value="False"):
            sb = HardwareCollector()._get_secure_boot()
        self.assertFalse(sb["enabled"])

    def test_printers_parsed(self):
        p_json = json.dumps([
            {"Name": "Microsoft Print to PDF", "Default": True, "Network": False},
            {"Name": "HP LaserJet",            "Default": False, "Network": True},
        ])
        with mock.patch(PATCH_PS, return_value=p_json):
            printers = HardwareCollector()._get_printers()
        self.assertEqual(len(printers), 2)
        self.assertTrue(printers[0]["default"])
        self.assertTrue(printers[1]["network"])

    def test_powershell_error_returns_empty(self):
        with mock.patch(PATCH_PS, side_effect=RuntimeError("access denied")):
            result = HardwareCollector()._get_gpu()
        self.assertEqual(result, [])


# ── Storage ───────────────────────────────────────────────────────────────────

class TestStorageParsing(unittest.TestCase):

    def test_physical_disk_parsed(self):
        disk_json = json.dumps([{
            "Model": "Samsung SSD 980 PRO 1TB",
            "SerialNumber": " S5GXNX0T123456 ",
            "MediaType": "SSD",
            "Size": "1000204886016",
            "InterfaceType": "SCSI",
        }])
        with mock.patch(PATCH_PS, return_value=disk_json):
            disks = StorageCollector()._get_physical_disks()
        self.assertEqual(len(disks), 1)
        d = disks[0]
        self.assertEqual(d["model"],      "Samsung SSD 980 PRO 1TB")
        self.assertEqual(d["serial"],     "S5GXNX0T123456")
        self.assertEqual(d["media_type"], "SSD")
        self.assertAlmostEqual(d["size_gb"], 931.51, delta=0.1)

    def test_physical_disk_empty_serial_is_none(self):
        disk_json = json.dumps([{
            "Model": "Virtual HD", "SerialNumber": "",
            "MediaType": "Fixed hard disk media",
            "Size": "107374182400", "InterfaceType": "IDE",
        }])
        with mock.patch(PATCH_PS, return_value=disk_json):
            disks = StorageCollector()._get_physical_disks()
        self.assertIsNone(disks[0]["serial"])

    def test_bitlocker_enrichment(self):
        bl_json = json.dumps([
            {"MountPoint": "C:\\", "VolumeStatus": "FullyEncrypted", "ProtectionStatus": 1},
            {"MountPoint": "D:\\", "VolumeStatus": "FullyDecrypted",  "ProtectionStatus": 0},
        ])

        fake_parts = [
            mock.Mock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw"),
            mock.Mock(device="D:\\", mountpoint="D:\\", fstype="NTFS", opts="rw"),
        ]

        def fake_usage(mp):
            return mock.Mock(total=500*1024**3, used=200*1024**3, free=300*1024**3, percent=40.0)

        with mock.patch("psutil.disk_partitions", return_value=fake_parts), \
             mock.patch("psutil.disk_usage", side_effect=fake_usage), \
             mock.patch(PATCH_PS, return_value=bl_json):
            vols = StorageCollector()._get_logical_volumes()

        c_vol = next(v for v in vols if v["drive_letter"] == "C:\\")
        d_vol = next(v for v in vols if v["drive_letter"] == "D:\\")
        self.assertEqual(c_vol["bitlocker_protection"], "On")
        self.assertEqual(d_vol["bitlocker_protection"], "Off")
        self.assertEqual(c_vol["bitlocker_status"], "FullyEncrypted")


# ── Network ───────────────────────────────────────────────────────────────────

class TestNetworkParsing(unittest.TestCase):

    def test_adapters_parsed(self):
        adapters_json = json.dumps([{
            "Name": "Ethernet",
            "Description": "Intel I225-V",
            "MacAddress": "AA-BB-CC-DD-EE-FF",
            "Status": "Up",
            "LinkSpeed": "1 Gbps",
            "DriverVersion": "28.0.1.1",
            "IpAddresses": ["192.168.1.100"],
            "IPv6Addresses": [],
            "DhcpEnabled": False,
            "Gateway": "192.168.1.1",
            "DnsServers": ["8.8.8.8", "8.8.4.4"],
        }])
        with mock.patch(PATCH_PS, return_value=adapters_json):
            adapters = NetworkCollector()._get_adapters()

        self.assertEqual(len(adapters), 1)
        a = adapters[0]
        self.assertEqual(a["name"],        "Ethernet")
        self.assertEqual(a["mac_address"], "AA-BB-CC-DD-EE-FF")
        self.assertEqual(a["ip_addresses"], ["192.168.1.100"])
        self.assertEqual(a["gateway"],     "192.168.1.1")
        self.assertEqual(a["dns_servers"], ["8.8.8.8", "8.8.4.4"])
        self.assertFalse(a["dhcp_enabled"])

    def test_dns_aggregation_deduplicates(self):
        adapters = [
            {"dns_servers": ["8.8.8.8", "1.1.1.1"]},
            {"dns_servers": ["8.8.8.8", "1.0.0.1"]},
        ]
        result = NetworkCollector._aggregate_dns(adapters)
        self.assertEqual(result, ["8.8.8.8", "1.1.1.1", "1.0.0.1"])

    def test_wifi_ssid_parsed(self):
        netsh_output = (
            "   SSID                   : MyHomeNetwork\n"
            "   BSSID                  : aa:bb:cc:dd:ee:ff\n"
        )
        import src.collectors.windows._utils as _utils
        with mock.patch.object(_utils, "run_command", return_value=netsh_output):
            ssid = NetworkCollector()._get_wifi_ssid()
        self.assertEqual(ssid, "MyHomeNetwork")

    def test_wifi_ssid_none_when_not_connected(self):
        import src.collectors.windows._utils as _utils
        with mock.patch.object(_utils, "run_command", return_value="There is no wireless interface"):
            ssid = NetworkCollector()._get_wifi_ssid()
        self.assertIsNone(ssid)


# ── OS Info ───────────────────────────────────────────────────────────────────

class TestOsInfoParsing(unittest.TestCase):

    def test_os_cim_fields_mapped(self):
        os_json = json.dumps({
            "Caption": "Microsoft Windows 11 Pro",
            "Version": "10.0.22631",
            "BuildNumber": "22631",
            "InstallDate": "/Date(1705622400000)/",
            "LastBootUpTime": "/Date(1740556800000)/",
            "RegisteredUser": "John Doe",
        })
        with mock.patch(PATCH_PS, return_value=os_json):
            result = OsInfoCollector()._get_os_cim()
        self.assertEqual(result["edition"], "Microsoft Windows 11 Pro")
        self.assertEqual(result["version"], "10.0.22631")
        self.assertEqual(result["build"],   "22631")

    def test_patches_sorted_and_counted(self):
        hotfix_json = json.dumps([
            {"HotFixID": "KB5034441", "Description": "Security Update", "InstalledOn": "/Date(1706745600000)/"},
            {"HotFixID": "KB5033375", "Description": "Security Update", "InstalledOn": "/Date(1704067200000)/"},
        ])
        with mock.patch(PATCH_PS, return_value=hotfix_json):
            patches = OsInfoCollector()._get_patches()
        self.assertEqual(patches["count"], 2)
        self.assertEqual(patches["hotfixes"][0]["id"], "KB5034441")

    def test_patches_error_returns_graceful(self):
        with mock.patch(PATCH_PS, side_effect=RuntimeError("timeout")):
            patches = OsInfoCollector()._get_patches()
        self.assertEqual(patches["count"], 0)
        self.assertIn("warning", patches)


# ── Logs ─────────────────────────────────────────────────────────────────────

class TestLogsParsing(unittest.TestCase):

    def test_log_summary_counts_parsed(self):
        counts_json = json.dumps({"critical": 2, "error": 15, "warning": 83})
        events_json = "[]"

        responses = [counts_json, events_json]
        idx = [0]
        def side(cmd, **kw):
            r = responses[idx[0] % len(responses)]
            idx[0] += 1
            return r

        with mock.patch(PATCH_PS, side_effect=side):
            summary, events = LogsCollector()._get_log_data("System")

        self.assertEqual(summary["critical"], 2)
        self.assertEqual(summary["error"],    15)
        self.assertEqual(summary["warning"],  83)

    def test_event_fields_mapped(self):
        counts_json = json.dumps({"critical": 0, "error": 1, "warning": 0})
        events_json = json.dumps([{
            "TimeCreated": "/Date(1740643200000)/",
            "Id": 7034,
            "ProviderName": "Service Control Manager",
            "Level": 2,
            "LevelDisplayName": "Error",
            "LogName": "System",
            "Message": "The service terminated unexpectedly.",
        }])

        responses = [counts_json, events_json]
        idx = [0]
        def side(cmd, **kw):
            r = responses[idx[0] % len(responses)]
            idx[0] += 1
            return r

        with mock.patch(PATCH_PS, side_effect=side):
            _, events = LogsCollector()._get_log_data("System")

        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e["event_id"], 7034)
        self.assertEqual(e["source"],   "Service Control Manager")
        self.assertEqual(e["level"],    "Error")
        self.assertIn("terminated", e["message"])

    def test_failed_logins_parsed(self):
        logins_json = json.dumps([
            {"TimeCreated": "/Date(1740556800000)/", "Id": 4625,
             "Message": "An account failed to log on."},
        ])
        with mock.patch(PATCH_PS, return_value=logins_json):
            logins = LogsCollector()._get_failed_logins()
        self.assertEqual(len(logins), 1)
        self.assertEqual(logins[0]["event_id"], 4625)
        self.assertEqual(logins[0]["source"],   "Security")

    def test_powershell_failure_returns_empty(self):
        with mock.patch(PATCH_PS, side_effect=RuntimeError("access denied")):
            summary, events = LogsCollector()._get_log_data("Security")
        self.assertEqual(events, [])
        self.assertEqual(summary["critical"], 0)


if __name__ == "__main__":
    unittest.main()
