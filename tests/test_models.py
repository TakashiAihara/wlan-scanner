"""Unit tests for data models."""

import unittest
from datetime import datetime
from src.models import (
    WiFiInfo, PingResult, IperfTcpResult, IperfUdpResult,
    FileTransferResult, MeasurementResult, Configuration,
    MeasurementType
)


class TestWiFiInfo(unittest.TestCase):
    """Test WiFiInfo data model."""

    def setUp(self):
        """Set up test data."""
        self.valid_wifi_info = WiFiInfo(
            ssid="TestNetwork",
            rssi=-60,
            link_quality=75,
            tx_rate=150.0,
            rx_rate=150.0,
            channel=6,
            frequency=2.437,
            interface_name="Wi-Fi",
            mac_address="00:11:22:33:44:55"
        )

    def test_valid_wifi_info(self):
        """Test valid WiFi info validation."""
        self.assertTrue(self.valid_wifi_info.validate())

    def test_invalid_rssi(self):
        """Test invalid RSSI value."""
        invalid_wifi = WiFiInfo(
            ssid="Test",
            rssi=10,  # Invalid: should be negative
            link_quality=50,
            tx_rate=100,
            rx_rate=100,
            channel=1,
            frequency=2.412,
            interface_name="Wi-Fi",
            mac_address="00:00:00:00:00:00"
        )
        with self.assertRaises(ValueError):
            invalid_wifi.validate()

    def test_invalid_link_quality(self):
        """Test invalid link quality value."""
        invalid_wifi = WiFiInfo(
            ssid="Test",
            rssi=-50,
            link_quality=150,  # Invalid: should be 0-100
            tx_rate=100,
            rx_rate=100,
            channel=1,
            frequency=2.412,
            interface_name="Wi-Fi",
            mac_address="00:00:00:00:00:00"
        )
        with self.assertRaises(ValueError):
            invalid_wifi.validate()


class TestPingResult(unittest.TestCase):
    """Test PingResult data model."""

    def setUp(self):
        """Set up test data."""
        self.ping_result = PingResult(
            target_ip="192.168.1.1",
            packets_sent=10,
            packets_received=9,
            packet_loss=10.0,
            min_rtt=1.5,
            max_rtt=10.2,
            avg_rtt=3.7,
            std_dev_rtt=2.1
        )

    def test_success_rate(self):
        """Test success rate calculation."""
        self.assertEqual(self.ping_result.success_rate, 90.0)

    def test_zero_packets_sent(self):
        """Test success rate with zero packets sent."""
        ping = PingResult(
            target_ip="192.168.1.1",
            packets_sent=0,
            packets_received=0,
            packet_loss=0,
            min_rtt=0,
            max_rtt=0,
            avg_rtt=0,
            std_dev_rtt=0
        )
        self.assertEqual(ping.success_rate, 0.0)


class TestIperfResults(unittest.TestCase):
    """Test iPerf result data models."""

    def test_tcp_result(self):
        """Test IperfTcpResult creation."""
        tcp_result = IperfTcpResult(
            server_ip="192.168.1.100",
            server_port=5201,
            duration=10.0,
            bytes_sent=125000000,
            bytes_received=125000000,
            throughput_upload=100.0,
            throughput_download=100.0,
            retransmits=5
        )
        self.assertEqual(tcp_result.throughput_upload, 100.0)
        self.assertEqual(tcp_result.retransmits, 5)

    def test_udp_result(self):
        """Test IperfUdpResult creation."""
        udp_result = IperfUdpResult(
            server_ip="192.168.1.100",
            server_port=5201,
            duration=10.0,
            bytes_sent=12500000,
            packets_sent=10000,
            packets_lost=50,
            packet_loss=0.5,
            jitter=1.2,
            throughput=10.0
        )
        self.assertEqual(udp_result.packet_loss, 0.5)
        self.assertEqual(udp_result.jitter, 1.2)


class TestFileTransferResult(unittest.TestCase):
    """Test FileTransferResult data model."""

    def test_throughput_calculation(self):
        """Test throughput calculation in Mbps."""
        result = FileTransferResult(
            server_address="192.168.1.100",
            file_size=104857600,  # 100 MB
            transfer_time=10.0,
            transfer_speed=10.0,  # 10 MB/s
            protocol="SMB",
            direction="download"
        )
        self.assertEqual(result.throughput_mbps, 80.0)  # 10 MB/s * 8 = 80 Mbps


class TestMeasurementResult(unittest.TestCase):
    """Test MeasurementResult data model."""

    def setUp(self):
        """Set up test data."""
        self.measurement = MeasurementResult(
            measurement_id="test_001"
        )

    def test_add_error(self):
        """Test adding error messages."""
        self.measurement.add_error("Test error 1")
        self.measurement.add_error("Test error 2")
        self.assertEqual(len(self.measurement.errors), 2)
        self.assertIn("Test error 1", self.measurement.errors[0])
        self.assertIn("Test error 2", self.measurement.errors[1])

    def test_to_csv_row(self):
        """Test CSV row conversion."""
        # Add some test data
        self.measurement.wifi_info = WiFiInfo(
            ssid="TestNet",
            rssi=-60,
            link_quality=75,
            tx_rate=150,
            rx_rate=150,
            channel=6,
            frequency=2.437,
            interface_name="Wi-Fi",
            mac_address="00:00:00:00:00:00"
        )
        self.measurement.ping_result = PingResult(
            target_ip="192.168.1.1",
            packets_sent=10,
            packets_received=10,
            packet_loss=0,
            min_rtt=1,
            max_rtt=5,
            avg_rtt=2.5,
            std_dev_rtt=0.5
        )

        csv_row = self.measurement.to_csv_row()

        # Check required fields
        self.assertIn("measurement_id", csv_row)
        self.assertIn("timestamp", csv_row)
        
        # Check WiFi fields
        self.assertEqual(csv_row["wifi_ssid"], "TestNet")
        self.assertEqual(csv_row["wifi_rssi"], -60)
        self.assertEqual(csv_row["wifi_link_quality"], 75)
        
        # Check ping fields
        self.assertEqual(csv_row["ping_target"], "192.168.1.1")
        self.assertEqual(csv_row["ping_packet_loss"], 0)
        self.assertEqual(csv_row["ping_avg_rtt"], 2.5)


class TestConfiguration(unittest.TestCase):
    """Test Configuration data model."""

    def setUp(self):
        """Set up test data."""
        self.config = Configuration()

    def test_default_values(self):
        """Test default configuration values."""
        self.assertEqual(self.config.interface_name, "Wi-Fi")
        self.assertEqual(self.config.ping_count, 10)
        self.assertEqual(self.config.iperf_port, 5201)
        self.assertEqual(self.config.log_level, "INFO")

    def test_validation_valid(self):
        """Test valid configuration validation."""
        self.assertTrue(self.config.validate())

    def test_validation_invalid_scan_interval(self):
        """Test invalid scan interval."""
        self.config.scan_interval = -1
        with self.assertRaises(ValueError):
            self.config.validate()

    def test_validation_invalid_log_level(self):
        """Test invalid log level."""
        self.config.log_level = "INVALID"
        with self.assertRaises(ValueError):
            self.config.validate()

    def test_from_dict(self):
        """Test creating configuration from dictionary."""
        config_dict = {
            "interface_name": "Ethernet",
            "ping_count": 20,
            "iperf_server": "10.0.0.1",
            "verbose": True,
            "invalid_field": "ignored"  # Should be ignored
        }
        config = Configuration.from_dict(config_dict)
        self.assertEqual(config.interface_name, "Ethernet")
        self.assertEqual(config.ping_count, 20)
        self.assertEqual(config.iperf_server, "10.0.0.1")
        self.assertTrue(config.verbose)


if __name__ == "__main__":
    unittest.main()