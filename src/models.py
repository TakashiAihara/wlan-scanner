"""Data models for wireless LAN analyzer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class MeasurementType(Enum):
    """Types of network measurements."""
    WIFI_INFO = "wifi_info"
    PING = "ping"
    IPERF_TCP = "iperf_tcp"
    IPERF_UDP = "iperf_udp"
    FILE_TRANSFER = "file_transfer"


@dataclass
class WiFiInfo:
    """Wireless LAN information from Win32 API."""
    ssid: str
    rssi: int  # dBm
    link_quality: int  # percentage
    tx_rate: float  # Mbps
    rx_rate: float  # Mbps
    channel: int
    frequency: float  # GHz
    interface_name: str
    mac_address: str
    timestamp: datetime = field(default_factory=datetime.now)

    def validate(self) -> bool:
        """Validate WiFi information values."""
        if not (-100 <= self.rssi <= 0):
            raise ValueError(f"Invalid RSSI value: {self.rssi}")
        if not (0 <= self.link_quality <= 100):
            raise ValueError(f"Invalid link quality: {self.link_quality}")
        if self.tx_rate < 0 or self.rx_rate < 0:
            raise ValueError("Tx/Rx rates cannot be negative")
        return True


@dataclass
class PingResult:
    """Ping measurement results."""
    target_ip: str
    packets_sent: int
    packets_received: int
    packet_loss: float  # percentage
    min_rtt: float  # ms
    max_rtt: float  # ms
    avg_rtt: float  # ms
    std_dev_rtt: float  # ms
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.packets_sent == 0:
            return 0.0
        return (self.packets_received / self.packets_sent) * 100


@dataclass
class IperfTcpResult:
    """iPerf3 TCP measurement results."""
    server_ip: str
    server_port: int
    duration: float  # seconds
    bytes_sent: int
    bytes_received: int
    throughput_upload: float  # Mbps
    throughput_download: float  # Mbps
    retransmits: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class IperfUdpResult:
    """iPerf3 UDP measurement results."""
    server_ip: str
    server_port: int
    duration: float  # seconds
    bytes_sent: int
    packets_sent: int
    packets_lost: int
    packet_loss: float  # percentage
    jitter: float  # ms
    throughput: float  # Mbps
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FileTransferResult:
    """File transfer performance measurement results."""
    server_address: str
    file_size: int  # bytes
    transfer_time: float  # seconds
    transfer_speed: float  # MB/s
    protocol: str  # e.g., "SMB", "FTP", "HTTP"
    direction: str  # "upload" or "download"
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def throughput_mbps(self) -> float:
        """Calculate throughput in Mbps."""
        return (self.transfer_speed * 8)  # Convert MB/s to Mbps


@dataclass
class MeasurementResult:
    """Complete measurement result containing all test data."""
    measurement_id: str
    wifi_info: Optional[WiFiInfo] = None
    ping_result: Optional[PingResult] = None
    iperf_tcp_result: Optional[IperfTcpResult] = None
    iperf_udp_result: Optional[IperfUdpResult] = None
    file_transfer_result: Optional[FileTransferResult] = None
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def add_error(self, error_msg: str) -> None:
        """Add an error message to the measurement."""
        self.errors.append(f"[{datetime.now().isoformat()}] {error_msg}")

    def to_csv_row(self) -> Dict[str, Any]:
        """Convert measurement to CSV row format."""
        row = {
            "measurement_id": self.measurement_id,
            "timestamp": self.timestamp.isoformat(),
        }

        # Add WiFi info
        if self.wifi_info:
            row.update({
                "wifi_ssid": self.wifi_info.ssid,
                "wifi_rssi": self.wifi_info.rssi,
                "wifi_link_quality": self.wifi_info.link_quality,
                "wifi_tx_rate": self.wifi_info.tx_rate,
                "wifi_rx_rate": self.wifi_info.rx_rate,
                "wifi_channel": self.wifi_info.channel,
                "wifi_frequency": self.wifi_info.frequency,
            })

        # Add ping results
        if self.ping_result:
            row.update({
                "ping_target": self.ping_result.target_ip,
                "ping_packet_loss": self.ping_result.packet_loss,
                "ping_avg_rtt": self.ping_result.avg_rtt,
                "ping_min_rtt": self.ping_result.min_rtt,
                "ping_max_rtt": self.ping_result.max_rtt,
                "ping_std_dev": self.ping_result.std_dev_rtt,
            })

        # Add iPerf TCP results
        if self.iperf_tcp_result:
            row.update({
                "iperf_tcp_upload": self.iperf_tcp_result.throughput_upload,
                "iperf_tcp_download": self.iperf_tcp_result.throughput_download,
                "iperf_tcp_retransmits": self.iperf_tcp_result.retransmits,
            })

        # Add iPerf UDP results
        if self.iperf_udp_result:
            row.update({
                "iperf_udp_throughput": self.iperf_udp_result.throughput,
                "iperf_udp_packet_loss": self.iperf_udp_result.packet_loss,
                "iperf_udp_jitter": self.iperf_udp_result.jitter,
            })

        # Add file transfer results
        if self.file_transfer_result:
            row.update({
                "file_transfer_speed": self.file_transfer_result.transfer_speed,
                "file_transfer_throughput": self.file_transfer_result.throughput_mbps,
                "file_transfer_direction": self.file_transfer_result.direction,
            })

        # Add error count
        row["error_count"] = len(self.errors)

        return row


@dataclass
class Configuration:
    """Application configuration."""
    # Network settings
    interface_name: str = "Wi-Fi"
    target_ips: List[str] = field(default_factory=lambda: ["192.168.1.1"])
    scan_interval: int = 60  # seconds
    timeout: int = 10  # seconds

    # Ping settings
    ping_count: int = 10
    ping_size: int = 32  # bytes
    ping_interval: float = 1.0  # seconds

    # iPerf3 settings
    iperf_server: str = "192.168.1.100"
    iperf_port: int = 5201
    iperf_duration: int = 10  # seconds
    iperf_parallel: int = 1
    iperf_udp_bandwidth: str = "10M"

    # File transfer settings
    file_server: str = "192.168.1.100"
    file_size_mb: int = 100
    file_protocol: str = "SMB"

    # Output settings
    output_dir: str = "data"
    output_format: str = "csv"
    verbose: bool = False
    log_level: str = "INFO"

    def validate(self) -> bool:
        """Validate configuration values."""
        if self.scan_interval <= 0:
            raise ValueError("Scan interval must be positive")
        if self.timeout <= 0:
            raise ValueError("Timeout must be positive")
        if self.ping_count <= 0:
            raise ValueError("Ping count must be positive")
        if self.iperf_duration <= 0:
            raise ValueError("iPerf duration must be positive")
        if self.file_size_mb <= 0:
            raise ValueError("File size must be positive")
        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid log level: {self.log_level}")
        return True

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "Configuration":
        """Create configuration from dictionary."""
        return cls(**{
            key: value for key, value in config_dict.items()
            if key in cls.__dataclass_fields__
        })