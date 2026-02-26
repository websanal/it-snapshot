"""Pydantic v2 schema definitions for it-snapshot v2."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CpuInfo(BaseModel):
    brand: Optional[str] = None
    physical_cores: Optional[int] = None
    logical_cores: Optional[int] = None
    max_frequency_mhz: Optional[float] = None
    current_frequency_mhz: Optional[float] = None
    usage_percent: Optional[float] = None


class RamInfo(BaseModel):
    total_gb: Optional[float] = None
    available_gb: Optional[float] = None
    used_gb: Optional[float] = None
    percent_used: Optional[float] = None


class GpuInfo(BaseModel):
    name: Optional[str] = None
    driver_version: Optional[str] = None
    vram_mb: Optional[float] = None


class MotherboardInfo(BaseModel):
    manufacturer: Optional[str] = None
    product: Optional[str] = None
    serial: Optional[str] = None


class BiosInfo(BaseModel):
    manufacturer: Optional[str] = None
    version: Optional[str] = None
    release_date: Optional[str] = None


class HardwareSection(BaseModel):
    cpu: Optional[CpuInfo] = None
    ram: Optional[RamInfo] = None
    gpu: list[GpuInfo] = []
    motherboard: Optional[MotherboardInfo] = None
    bios: Optional[BiosInfo] = None


class StorageVolume(BaseModel):
    device: Optional[str] = None
    mountpoint: Optional[str] = None
    fstype: Optional[str] = None
    opts: Optional[str] = None
    total_gb: Optional[float] = None
    used_gb: Optional[float] = None
    free_gb: Optional[float] = None
    percent_used: Optional[float] = None
    status: str = "ok"


class NetworkInterface(BaseModel):
    name: str
    mac_address: Optional[str] = None
    ip_addresses: list[str] = []
    ipv6_addresses: list[str] = []
    is_up: bool = False
    speed_mbps: Optional[int] = None


class NetworkSection(BaseModel):
    interfaces: list[NetworkInterface] = []
    dns_servers: list[str] = []
    default_gateway: Optional[str] = None


class SoftwareItem(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    publisher: Optional[str] = None
    install_date: Optional[str] = None


class SoftwareSection(BaseModel):
    installed: list[SoftwareItem] = []
    count: int = 0


class AntiVirusItem(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    up_to_date: Optional[bool] = None
    product_state: Optional[int] = None


class FirewallStatus(BaseModel):
    domain_enabled: Optional[bool] = None
    private_enabled: Optional[bool] = None
    public_enabled: Optional[bool] = None


class EncryptionStatus(BaseModel):
    bitlocker_volumes: list[dict[str, Any]] = []
    filevault_enabled: Optional[bool] = None


class DefenderStatus(BaseModel):
    enabled: Optional[bool] = None
    real_time_protection: Optional[bool] = None
    signatures_last_updated: Optional[str] = None


class SecuritySection(BaseModel):
    antivirus: list[AntiVirusItem] = []
    firewall: FirewallStatus = FirewallStatus()
    uac_enabled: Optional[bool] = None
    encryption: EncryptionStatus = EncryptionStatus()
    windows_defender: Optional[DefenderStatus] = None
    secure_boot_enabled: Optional[bool] = None
    gatekeeper_enabled: Optional[bool] = None
    sip_enabled: Optional[bool] = None


class LogEntry(BaseModel):
    time: Optional[str] = None
    event_id: Optional[int] = None
    source: Optional[str] = None
    message: Optional[str] = None
    level: Optional[str] = None


class LogsSection(BaseModel):
    recent_errors: list[LogEntry] = []
    recent_warnings: list[LogEntry] = []
    failed_logins: list[LogEntry] = []


class DeviceIdentitySection(BaseModel):
    hostname: Optional[str] = None
    fqdn: Optional[str] = None
    domain: Optional[str] = None
    workgroup: Optional[str] = None
    os_machine_id: Optional[str] = None
    primary_macs: list[str] = []
    azure_ad_device_id: Optional[str] = None


class Finding(BaseModel):
    id: str
    severity: str
    title: str
    detail: str


class RiskScore(BaseModel):
    score: int = 0
    level: str = "low"
    factors: list[str] = []


class SnapshotReport(BaseModel):
    schema_version: str = "2.0"
    agent_version: str = "2.0.0"
    run_id: str
    collected_at: str
    device_identity: DeviceIdentitySection = DeviceIdentitySection()
    hardware: HardwareSection = HardwareSection()
    storage: list[StorageVolume] = []
    network: NetworkSection = NetworkSection()
    software: SoftwareSection = SoftwareSection()
    security: SecuritySection = SecuritySection()
    logs: LogsSection = LogsSection()
    findings: list[Finding] = []
    risk_score: RiskScore = RiskScore()
    errors: list[str] = []
    # Legacy v1 keys (always present, unchanged shape)
    snapshot: dict[str, Any] = {}
    os: dict[str, Any] = {}
    reboot: dict[str, Any] = {}
    disks: list[dict[str, Any]] = []
