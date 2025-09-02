"""Unit tests for WiFi information collector."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import subprocess
from src.wifi_collector import WiFiInfoCollector
from src.models import WiFiInfo


class TestWiFiInfoCollector(unittest.TestCase):
    """Test WiFiInfoCollector class."""

    def setUp(self):
        """Set up test fixtures."""
        self.collector = WiFiInfoCollector("Wi-Fi")

    def test_channel_to_frequency_2ghz(self):
        """Test 2.4GHz channel to frequency conversion."""
        # Test common 2.4GHz channels
        self.assertAlmostEqual(self.collector._channel_to_frequency(1), 2.412, places=3)
        self.assertAlmostEqual(self.collector._channel_to_frequency(6), 2.437, places=3)
        self.assertAlmostEqual(self.collector._channel_to_frequency(11), 2.462, places=3)
        self.assertAlmostEqual(self.collector._channel_to_frequency(14), 2.484, places=3)

    def test_channel_to_frequency_5ghz(self):
        """Test 5GHz channel to frequency conversion."""
        # Test common 5GHz channels
        self.assertAlmostEqual(self.collector._channel_to_frequency(36), 5.180, places=3)
        self.assertAlmostEqual(self.collector._channel_to_frequency(40), 5.200, places=3)
        self.assertAlmostEqual(self.collector._channel_to_frequency(149), 5.745, places=3)

    def test_frequency_to_channel_2ghz(self):
        """Test 2.4GHz frequency to channel conversion."""
        self.assertEqual(self.collector._frequency_to_channel(2.412), 1)
        self.assertEqual(self.collector._frequency_to_channel(2.437), 6)
        self.assertEqual(self.collector._frequency_to_channel(2.462), 11)
        self.assertEqual(self.collector._frequency_to_channel(2.484), 14)

    def test_frequency_to_channel_5ghz(self):
        """Test 5GHz frequency to channel conversion."""
        self.assertEqual(self.collector._frequency_to_channel(5.180), 36)
        self.assertEqual(self.collector._frequency_to_channel(5.200), 40)
        self.assertEqual(self.collector._frequency_to_channel(5.745), 149)

    def test_rssi_to_quality(self):
        """Test RSSI to quality percentage conversion."""
        # Test boundary cases
        self.assertEqual(self.collector._rssi_to_quality(-100), 0)
        self.assertEqual(self.collector._rssi_to_quality(-50), 100)
        
        # Test intermediate values
        self.assertEqual(self.collector._rssi_to_quality(-75), 50)
        self.assertEqual(self.collector._rssi_to_quality(-60), 80)
        self.assertEqual(self.collector._rssi_to_quality(-90), 20)

    def test_quality_to_rssi(self):
        """Test quality percentage to RSSI conversion."""
        # Test boundary cases
        self.assertEqual(self.collector._quality_to_rssi(0), -100)
        self.assertEqual(self.collector._quality_to_rssi(100), -50)
        
        # Test intermediate values
        self.assertEqual(self.collector._quality_to_rssi(50), -75)
        self.assertEqual(self.collector._quality_to_rssi(80), -60)
        self.assertEqual(self.collector._quality_to_rssi(20), -90)

    @patch('subprocess.run')
    @patch('platform.system')
    def test_collect_windows_wifi_info(self, mock_platform, mock_run):
        """Test Windows WiFi info collection."""
        mock_platform.return_value = "Windows"
        
        # Mock netsh output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
    SSID                   : TestNetwork
    BSSID                  : 00:11:22:33:44:55
    Channel                : 6
    Receive rate (Mbps)    : 150
    Transmit rate (Mbps)   : 150
    Signal                 : 80%
        """
        mock_run.return_value = mock_result
        
        collector = WiFiInfoCollector("Wi-Fi")
        wifi_info = collector.collect_wifi_info()
        
        self.assertIsNotNone(wifi_info)
        self.assertEqual(wifi_info.ssid, "TestNetwork")
        self.assertEqual(wifi_info.channel, 6)
        self.assertEqual(wifi_info.link_quality, 80)

    @patch('subprocess.run')
    @patch('platform.system')
    def test_collect_linux_wifi_info_iw(self, mock_platform, mock_run):
        """Test Linux WiFi info collection using iw."""
        mock_platform.return_value = "Linux"
        
        # Create different mock results for different commands
        def side_effect(*args, **kwargs):
            mock_result = MagicMock()
            
            if 'iw dev' in ' '.join(args[0]) if isinstance(args[0], list) else args[0]:
                mock_result.returncode = 0
                mock_result.stdout = """
Connected to 00:11:22:33:44:55 (on wlan0)
    SSID: TestNetwork
    freq: 2437
    signal: -60 dBm
    tx bitrate: 150.0 MBit/s
                """
            elif 'ip link show' in ' '.join(args[0]) if isinstance(args[0], list) else args[0]:
                mock_result.returncode = 0
                mock_result.stdout = """
3: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DORMANT group default qlen 1000
    link/ether aa:bb:cc:dd:ee:ff brd ff:ff:ff:ff:ff:ff
                """
            else:
                mock_result.returncode = 1
                mock_result.stdout = ""
            
            return mock_result
        
        mock_run.side_effect = side_effect
        
        collector = WiFiInfoCollector("wlan0")
        wifi_info = collector.collect_wifi_info()
        
        self.assertIsNotNone(wifi_info)
        self.assertEqual(wifi_info.ssid, "TestNetwork")
        self.assertEqual(wifi_info.rssi, -60)
        self.assertEqual(wifi_info.tx_rate, 150.0)

    @patch('subprocess.run')
    @patch('platform.system')
    def test_collect_macos_wifi_info(self, mock_platform, mock_run):
        """Test macOS WiFi info collection."""
        mock_platform.return_value = "Darwin"
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
     agrCtlRSSI: -60
     agrExtRSSI: 0
    agrCtlNoise: -90
    agrExtNoise: 0
          state: running
        op mode: station 
     lastTxRate: 150
        maxRate: 300
lastAssocStatus: 0
    802.11 auth: open
      link auth: wpa2-psk
          BSSID: 00:11:22:33:44:55
           SSID: TestNetwork
            MCS: 7
        channel: 6
        """
        mock_run.return_value = mock_result
        
        collector = WiFiInfoCollector("en0")
        wifi_info = collector.collect_wifi_info()
        
        self.assertIsNotNone(wifi_info)
        self.assertEqual(wifi_info.ssid, "TestNetwork")
        self.assertEqual(wifi_info.rssi, -60)
        self.assertEqual(wifi_info.channel, 6)
        self.assertEqual(wifi_info.tx_rate, 150.0)

    @patch('subprocess.run')
    @patch('platform.system')
    def test_get_available_interfaces_windows(self, mock_platform, mock_run):
        """Test getting available interfaces on Windows."""
        mock_platform.return_value = "Windows"
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
Name                   : Wi-Fi
Description            : Intel(R) Wireless-AC 9260 160MHz
GUID                   : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Physical address       : 00:11:22:33:44:55

Name                   : Wi-Fi 2
Description            : Realtek 8822CE Wireless LAN 802.11ac PCI-E NIC
        """
        mock_run.return_value = mock_result
        
        collector = WiFiInfoCollector()
        interfaces = collector.get_available_interfaces()
        
        self.assertIn("Wi-Fi", interfaces)
        self.assertIn("Wi-Fi 2", interfaces)

    @patch('subprocess.run')
    @patch('platform.system')
    def test_get_available_interfaces_linux(self, mock_platform, mock_run):
        """Test getting available interfaces on Linux."""
        mock_platform.return_value = "Linux"
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000
3: wlan0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DORMANT group default qlen 1000
        """
        mock_run.return_value = mock_result
        
        collector = WiFiInfoCollector()
        interfaces = collector.get_available_interfaces()
        
        self.assertIn("eth0", interfaces)
        self.assertIn("wlan0", interfaces)
        self.assertNotIn("lo", interfaces)  # Loopback should be excluded

    @patch.object(WiFiInfoCollector, 'collect_wifi_info')
    def test_is_connected_true(self, mock_collect):
        """Test is_connected returns True when connected."""
        mock_wifi_info = WiFiInfo(
            ssid="TestNetwork",
            rssi=-60,
            link_quality=80,
            tx_rate=150.0,
            rx_rate=150.0,
            channel=6,
            frequency=2.437,
            interface_name="Wi-Fi",
            mac_address="00:11:22:33:44:55"
        )
        mock_collect.return_value = mock_wifi_info
        
        self.assertTrue(self.collector.is_connected())

    @patch.object(WiFiInfoCollector, 'collect_wifi_info')
    def test_is_connected_false(self, mock_collect):
        """Test is_connected returns False when not connected."""
        mock_collect.return_value = None
        
        self.assertFalse(self.collector.is_connected())

    @patch('subprocess.run')
    @patch('platform.system')
    def test_collect_wifi_info_error_handling(self, mock_platform, mock_run):
        """Test error handling in WiFi info collection."""
        mock_platform.return_value = "Windows"
        
        # Mock command failure
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Network interface not found"
        mock_run.return_value = mock_result
        
        wifi_info = self.collector.collect_wifi_info()
        
        self.assertIsNone(wifi_info)

    def test_unsupported_platform(self):
        """Test handling of unsupported platform."""
        with patch('platform.system', return_value='UnknownOS'):
            collector = WiFiInfoCollector()
            wifi_info = collector.collect_wifi_info()
            
            self.assertIsNone(wifi_info)


if __name__ == '__main__':
    unittest.main()