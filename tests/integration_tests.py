"""Integration tests and End-to-End tests for wireless LAN analyzer."""

import unittest
import tempfile
import os
import shutil
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import all main components
from src.models import Configuration, MeasurementResult, WiFiInfo, PingResult
from src.config_manager import ConfigurationManager
from src.wifi_collector import WiFiInfoCollector
from src.network_tester import NetworkTester
from src.file_transfer_tester import FileTransferTester
from src.data_export_manager import DataExportManager
from src.error_handler import ErrorHandler, get_error_handler
from src.measurement_orchestrator import MeasurementOrchestrator
from main import MainApplication


class TestSystemIntegration(unittest.TestCase):
    """Test system integration with real components."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "test_config.ini")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_configuration_manager_integration(self):
        """Test ConfigurationManager with full workflow."""
        # Create config manager and default config
        manager = ConfigurationManager()
        manager.create_default_config(self.config_file)
        
        # Verify file was created
        self.assertTrue(Path(self.config_file).exists())
        
        # Load configuration
        config = manager.load_config()
        self.assertIsInstance(config, Configuration)
        
        # Validate configuration
        self.assertTrue(config.validate())
        self.assertTrue(manager.validate_network_settings())

    def test_data_export_integration(self):
        """Test data export with real measurement results."""
        # Create test measurement result
        measurement = MeasurementResult(measurement_id="test_001")
        measurement.wifi_info = WiFiInfo(
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
        measurement.ping_result = PingResult(
            target_ip="8.8.8.8",
            packets_sent=10,
            packets_received=10,
            packet_loss=0.0,
            min_rtt=1.5,
            max_rtt=5.0,
            avg_rtt=2.5,
            std_dev_rtt=0.8
        )
        
        # Create export manager and export data
        export_manager = DataExportManager(self.output_dir)
        csv_file = os.path.join(self.output_dir, "test_measurements.csv")
        
        # Export measurement
        export_manager.export_to_csv([measurement], csv_file)
        
        # Verify file was created and has content
        self.assertTrue(Path(csv_file).exists())
        
        # Read and verify CSV content
        with open(csv_file, 'r') as f:
            content = f.read()
            self.assertIn("measurement_id", content)
            self.assertIn("test_001", content)
            self.assertIn("TestNetwork", content)
            self.assertIn("8.8.8.8", content)


class TestMockedIntegration(unittest.TestCase):
    """Integration tests with mocked external dependencies."""

    def setUp(self):
        """Set up test environment with mocks."""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "test_config.ini")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create test configuration
        self.config = Configuration()
        self.config.target_ips = ["8.8.8.8"]
        self.config.iperf_server = "192.168.1.100"
        self.config.file_server = "192.168.1.100"
        self.config.output_dir = self.output_dir

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('src.wifi_collector.platform.system')
    @patch('src.wifi_collector.subprocess.run')
    def test_wifi_collector_integration(self, mock_run, mock_platform):
        """Test WiFi collector with mocked system calls."""
        mock_platform.return_value = "Linux"
        
        # Mock iw command output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
Connected to 00:11:22:33:44:55 (on wlan0)
    SSID: TestNetwork
    freq: 2437
    signal: -60 dBm
    tx bitrate: 150.0 MBit/s
        """
        
        def side_effect(*args, **kwargs):
            if 'iw dev' in ' '.join(args[0]):
                return mock_result
            elif 'ip link show' in ' '.join(args[0]):
                mock_result.stdout = "link/ether aa:bb:cc:dd:ee:ff"
                return mock_result
            return mock_result
        
        mock_run.side_effect = side_effect
        
        # Test WiFi collection
        collector = WiFiInfoCollector("wlan0")
        wifi_info = collector.collect_wifi_info()
        
        self.assertIsNotNone(wifi_info)
        self.assertEqual(wifi_info.ssid, "TestNetwork")
        self.assertEqual(wifi_info.rssi, -60)

    @patch('pythonping.ping')
    def test_network_tester_integration(self, mock_ping):
        """Test network tester with mocked ping."""
        # Mock ping results
        mock_response = MagicMock()
        mock_response.time_elapsed = 0.025  # 25ms
        mock_response.time_elapsed_ms = 25.0
        mock_response.success = True
        
        mock_ping.return_value = [mock_response] * 10  # 10 successful pings
        
        # Test ping functionality
        tester = NetworkTester()
        result = tester.ping_host("8.8.8.8")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.target_ip, "8.8.8.8")
        self.assertEqual(result.packets_sent, 10)
        self.assertEqual(result.packets_received, 10)

    @patch('iperf3.Client')
    def test_iperf_integration(self, mock_client_class):
        """Test iPerf integration with mocked client."""
        # Mock iPerf client and results
        mock_client = MagicMock()
        mock_result = MagicMock()
        
        # TCP test result
        mock_result.sent_Mbps = 100.0
        mock_result.received_Mbps = 95.0
        mock_result.retransmits = 5
        mock_result.sent_bytes = 125000000
        mock_result.received_bytes = 118750000
        
        mock_client.run.return_value = mock_result
        mock_client_class.return_value = mock_client
        
        # Test TCP upload
        tester = NetworkTester()
        result = tester.iperf_tcp_upload("192.168.1.100")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.server_ip, "192.168.1.100")
        self.assertEqual(result.throughput_upload, 100.0)

    def test_measurement_orchestrator_integration(self):
        """Test measurement orchestrator with mocked components."""
        with patch('src.wifi_collector.WiFiInfoCollector') as mock_wifi, \
             patch('src.network_tester.NetworkTester') as mock_network, \
             patch('src.file_transfer_tester.FileTransferTester') as mock_file, \
             patch('src.data_export_manager.DataExportManager') as mock_export:
            
            # Mock WiFi collector
            mock_wifi_instance = mock_wifi.return_value
            mock_wifi_instance.collect_wifi_info.return_value = WiFiInfo(
                ssid="TestNetwork", rssi=-60, link_quality=80,
                tx_rate=150, rx_rate=150, channel=6, frequency=2.437,
                interface_name="wlan0", mac_address="00:11:22:33:44:55"
            )
            mock_wifi_instance.is_connected.return_value = True
            
            # Mock network tester
            mock_network_instance = mock_network.return_value
            mock_network_instance.ping_test.return_value = PingResult(
                target_ip="8.8.8.8", packets_sent=10, packets_received=10,
                packet_loss=0.0, min_rtt=1.0, max_rtt=5.0,
                avg_rtt=2.5, std_dev_rtt=0.8
            )
            mock_network_instance.is_host_reachable.return_value = True
            
            # Mock file transfer tester
            mock_file_instance = mock_file.return_value
            mock_file_instance.test_http_transfer.return_value = None
            
            # Mock data export manager
            mock_export_instance = mock_export.return_value
            mock_export_instance.write_measurement.return_value = None
            
            # Create orchestrator and run measurement
            orchestrator = MeasurementOrchestrator(self.config)
            result = orchestrator.execute_measurement_cycle()
            
            # Verify measurement was executed
            self.assertIsNotNone(result)
            self.assertIsNotNone(result.measurement_result)
            self.assertIsNotNone(result.measurement_result.wifi_info)
            self.assertIsNotNone(result.measurement_result.ping_result)

    def test_error_handler_integration(self):
        """Test error handler integration across components."""
        error_handler = get_error_handler()
        
        # Test network error handling
        import socket
        network_error = error_handler.handle_network_error(
            socket.timeout("Test timeout"),
            component="integration_test",
            operation="test"
        )
        
        self.assertIsNotNone(network_error)
        self.assertEqual(error_handler.error_counts['network_error'], 1)
        
        # Test file system error handling
        fs_error = error_handler.handle_file_system_error(
            FileNotFoundError("Test file not found"),
            component="integration_test",
            operation="test"
        )
        
        self.assertIsNotNone(fs_error)
        self.assertEqual(error_handler.error_counts['file_system_error'], 1)
        
        # Test error statistics
        stats = error_handler.get_error_statistics()
        self.assertEqual(stats['total_errors'], 2)


class TestEndToEndWorkflow(unittest.TestCase):
    """End-to-end workflow tests with full application integration."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "e2e_config.ini")
        self.output_dir = os.path.join(self.test_dir, "e2e_output")
        self.log_file = os.path.join(self.test_dir, "e2e_test.log")

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('sys.argv', ['main.py', '--create-config', '--config'])
    @patch('src.config_manager.ConfigurationManager')
    def test_config_creation_workflow(self, mock_config_manager, mock_argv):
        """Test configuration creation workflow."""
        mock_manager = mock_config_manager.return_value
        mock_manager.create_default_config = MagicMock()
        
        # Test config creation (would normally be done via command line)
        config_manager = ConfigurationManager()
        config_manager.create_default_config(self.config_file)
        
        # Verify method was called
        mock_manager.create_default_config.assert_called()

    def test_measurement_workflow_with_mocks(self):
        """Test complete measurement workflow with mocked components."""
        with patch('src.wifi_collector.WiFiInfoCollector') as mock_wifi, \
             patch('src.network_tester.NetworkTester') as mock_network, \
             patch('src.file_transfer_tester.FileTransferTester') as mock_file, \
             patch('src.data_export_manager.DataExportManager') as mock_export:
            
            # Setup mocks for successful measurement
            self._setup_successful_mocks(mock_wifi, mock_network, mock_file, mock_export)
            
            # Create configuration
            config = Configuration()
            config.output_dir = self.output_dir
            
            # Create and run orchestrator
            orchestrator = MeasurementOrchestrator(config)
            result = orchestrator.execute_measurement_cycle()
            
            # Verify successful execution
            self.assertIsNotNone(result)
            self.assertIsNotNone(result.measurement_result)
            self.assertTrue(result.success)

    def test_error_recovery_workflow(self):
        """Test error recovery in full workflow."""
        with patch('src.wifi_collector.WiFiInfoCollector') as mock_wifi, \
             patch('src.network_tester.NetworkTester') as mock_network, \
             patch('src.file_transfer_tester.FileTransferTester') as mock_file, \
             patch('src.data_export_manager.DataExportManager') as mock_export:
            
            # Setup mocks with some failures
            self._setup_partial_failure_mocks(mock_wifi, mock_network, mock_file, mock_export)
            
            # Create configuration
            config = Configuration()
            config.output_dir = self.output_dir
            
            # Create and run orchestrator
            orchestrator = MeasurementOrchestrator(config)
            result = orchestrator.execute_measurement_cycle()
            
            # Verify partial success (some measurements succeeded, some failed)
            self.assertIsNotNone(result)
            self.assertIsNotNone(result.measurement_result)
            # Even with partial failures, the orchestrator should continue

    def test_main_application_dry_run(self):
        """Test main application in dry run mode."""
        with patch('src.config_manager.ConfigurationManager') as mock_config, \
             patch('src.measurement_orchestrator.MeasurementOrchestrator') as mock_orchestrator:
            
            # Setup mocks
            mock_config_instance = mock_config.return_value
            mock_config_instance.load_config.return_value = Configuration()
            
            mock_orch_instance = mock_orchestrator.return_value
            mock_orch_instance.validate_prerequisites.return_value = (True, [])
            
            # Create main application
            app = MainApplication()
            
            # Test dry run mode
            args = Mock()
            args.dry_run = True
            args.config = self.config_file
            args.create_config = False
            args.validate_config = False
            args.check_prerequisites = False
            args.continuous = False
            args.verbose = False
            args.log_file = None
            args.log_level = "INFO"
            args.quiet = False
            
            # This should not raise an exception
            try:
                # Note: We're testing the setup, not full execution
                app.load_configuration(args)
                # If we get here, the basic setup worked
                self.assertTrue(True)
            except Exception as e:
                # Expected in test environment due to missing config file
                self.assertIn("config", str(e).lower())

    def _setup_successful_mocks(self, mock_wifi, mock_network, mock_file, mock_export):
        """Setup mocks for successful measurement scenario."""
        # WiFi collector mock
        mock_wifi_instance = mock_wifi.return_value
        mock_wifi_instance.collect_wifi_info.return_value = WiFiInfo(
            ssid="TestNetwork", rssi=-60, link_quality=80,
            tx_rate=150, rx_rate=150, channel=6, frequency=2.437,
            interface_name="wlan0", mac_address="00:11:22:33:44:55"
        )
        mock_wifi_instance.is_connected.return_value = True
        
        # Network tester mock
        mock_network_instance = mock_network.return_value
        mock_network_instance.ping_test.return_value = PingResult(
            target_ip="8.8.8.8", packets_sent=10, packets_received=10,
            packet_loss=0.0, min_rtt=1.0, max_rtt=5.0,
            avg_rtt=2.5, std_dev_rtt=0.8
        )
        mock_network_instance.is_host_reachable.return_value = True
        mock_network_instance._check_iperf_server_availability.return_value = True
        
        # File transfer tester mock
        mock_file_instance = mock_file.return_value
        mock_file_instance.test_http_transfer.return_value = None
        
        # Export manager mock
        mock_export_instance = mock_export.return_value
        mock_export_instance.write_measurement.return_value = None

    def _setup_partial_failure_mocks(self, mock_wifi, mock_network, mock_file, mock_export):
        """Setup mocks for partial failure scenario."""
        # WiFi collector - success
        mock_wifi_instance = mock_wifi.return_value
        mock_wifi_instance.collect_wifi_info.return_value = WiFiInfo(
            ssid="TestNetwork", rssi=-60, link_quality=80,
            tx_rate=150, rx_rate=150, channel=6, frequency=2.437,
            interface_name="wlan0", mac_address="00:11:22:33:44:55"
        )
        mock_wifi_instance.is_connected.return_value = True
        
        # Network tester - partial success
        mock_network_instance = mock_network.return_value
        mock_network_instance.ping_test.return_value = PingResult(
            target_ip="8.8.8.8", packets_sent=10, packets_received=8,
            packet_loss=20.0, min_rtt=1.0, max_rtt=100.0,
            avg_rtt=15.0, std_dev_rtt=25.0
        )
        mock_network_instance.is_host_reachable.return_value = True
        mock_network_instance._check_iperf_server_availability.return_value = False  # Failure
        
        # File transfer tester - failure
        mock_file_instance = mock_file.return_value
        mock_file_instance.test_http_transfer.side_effect = Exception("Connection failed")
        
        # Export manager - success
        mock_export_instance = mock_export.return_value
        mock_export_instance.write_measurement.return_value = None


class TestConcurrentExecution(unittest.TestCase):
    """Test concurrent execution and timing scenarios."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config = Configuration()
        self.config.output_dir = self.test_dir

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_measurement_timing(self):
        """Test measurement timing and duration tracking."""
        with patch('src.wifi_collector.WiFiInfoCollector') as mock_wifi, \
             patch('src.network_tester.NetworkTester') as mock_network:
            
            # Setup mocks with artificial delay
            mock_wifi_instance = mock_wifi.return_value
            mock_wifi_instance.collect_wifi_info.side_effect = lambda: self._delayed_wifi_result()
            mock_wifi_instance.is_connected.return_value = True
            
            mock_network_instance = mock_network.return_value
            mock_network_instance.ping_test.side_effect = lambda *args: self._delayed_ping_result()
            mock_network_instance.is_host_reachable.return_value = True
            
            # Create orchestrator and measure execution time
            orchestrator = MeasurementOrchestrator(self.config)
            
            start_time = time.time()
            result = orchestrator.execute_measurement_cycle()
            end_time = time.time()
            
            # Verify timing information
            self.assertIsNotNone(result)
            self.assertGreater(end_time - start_time, 0.1)  # Should take some time due to mock delays

    def _delayed_wifi_result(self):
        """Create WiFi result with artificial delay."""
        time.sleep(0.05)  # 50ms delay
        return WiFiInfo(
            ssid="TestNetwork", rssi=-60, link_quality=80,
            tx_rate=150, rx_rate=150, channel=6, frequency=2.437,
            interface_name="wlan0", mac_address="00:11:22:33:44:55"
        )

    def _delayed_ping_result(self):
        """Create ping result with artificial delay."""
        time.sleep(0.05)  # 50ms delay
        return PingResult(
            target_ip="8.8.8.8", packets_sent=10, packets_received=10,
            packet_loss=0.0, min_rtt=1.0, max_rtt=5.0,
            avg_rtt=2.5, std_dev_rtt=0.8
        )


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_empty_measurement_results(self):
        """Test handling of empty measurement results."""
        # Create measurement with no data
        measurement = MeasurementResult(measurement_id="empty_test")
        
        # Test CSV export with empty measurement
        export_manager = DataExportManager(self.test_dir)
        csv_file = os.path.join(self.test_dir, "empty_test.csv")
        
        # This should not fail
        export_manager.export_to_csv([measurement], csv_file)
        
        # Verify file exists and has minimal content
        self.assertTrue(Path(csv_file).exists())
        
        with open(csv_file, 'r') as f:
            content = f.read()
            self.assertIn("measurement_id", content)
            self.assertIn("empty_test", content)

    def test_invalid_configuration_handling(self):
        """Test handling of invalid configurations."""
        # Create invalid configuration
        config = Configuration()
        config.scan_interval = -1  # Invalid value
        
        # This should raise validation error
        with self.assertRaises(ValueError):
            config.validate()

    def test_disk_space_simulation(self):
        """Test behavior when disk space is limited."""
        with patch('builtins.open', side_effect=OSError(28, "No space left on device")):
            export_manager = DataExportManager(self.test_dir)
            measurement = MeasurementResult(measurement_id="disk_test")
            
            # This should handle the error gracefully
            with self.assertRaises(OSError):
                export_manager.write_measurement(measurement, "test.csv")


if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSystemIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestMockedIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrentExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)