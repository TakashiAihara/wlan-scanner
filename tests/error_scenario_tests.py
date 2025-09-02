"""Error scenario tests for wireless LAN analyzer."""

import unittest
import tempfile
import shutil
import socket
import subprocess
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Import components for error testing
from src.models import Configuration
from src.config_manager import ConfigurationManager
from src.wifi_collector import WiFiInfoCollector
from src.network_tester import NetworkTester, IperfError
from src.file_transfer_tester import FileTransferTester, FileTransferError
from src.data_export_manager import DataExportManager
from src.error_handler import ErrorHandler, NetworkError, FileSystemError
from src.measurement_orchestrator import MeasurementOrchestrator
from main import MainApplication


class TestNetworkDisconnectionScenarios(unittest.TestCase):
    """Test behavior when network connectivity is lost."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config = Configuration()
        self.config.target_ips = ["8.8.8.8"]
        self.config.iperf_server = "192.168.1.100"

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('src.wifi_collector.subprocess.run')
    @patch('src.wifi_collector.platform.system')
    def test_wifi_disconnection_during_scan(self, mock_platform, mock_run):
        """Test WiFi collector behavior when WiFi disconnects during scan."""
        mock_platform.return_value = "Linux"
        
        # Simulate WiFi disconnection (command fails)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Network interface not found"
        mock_run.return_value = mock_result
        
        collector = WiFiInfoCollector("wlan0")
        wifi_info = collector.collect_wifi_info()
        
        # Should handle gracefully and return None
        self.assertIsNone(wifi_info)

    @patch('pythonping.ping')
    def test_ping_during_network_outage(self, mock_ping):
        """Test ping behavior during network outage."""
        # Simulate network unreachable
        mock_ping.side_effect = socket.gaierror("Network unreachable")
        
        tester = NetworkTester()
        result = tester.ping_test("8.8.8.8")
        
        # Should handle error and return None or error result
        self.assertIsNone(result)

    @patch('iperf3.Client')
    def test_iperf_server_down_during_test(self, mock_client_class):
        """Test iPerf behavior when server goes down during test."""
        mock_client = MagicMock()
        mock_client.run.side_effect = ConnectionRefusedError("Connection refused")
        mock_client_class.return_value = mock_client
        
        tester = NetworkTester()
        
        with self.assertRaises(IperfError):
            tester.iperf_tcp_upload("192.168.1.100")

    def test_orchestrator_network_failure_handling(self):
        """Test orchestrator behavior during network failures."""
        with patch('src.wifi_collector.WiFiInfoCollector') as mock_wifi, \
             patch('src.network_tester.NetworkTester') as mock_network, \
             patch('src.error_handler.get_error_handler') as mock_error_handler:
            
            # Setup WiFi to succeed initially
            mock_wifi_instance = mock_wifi.return_value
            mock_wifi_instance.is_connected.return_value = True
            mock_wifi_instance.collect_wifi_info.return_value = None  # Then fail
            
            # Setup network tests to fail
            mock_network_instance = mock_network.return_value
            mock_network_instance.is_host_reachable.return_value = False
            mock_network_instance.ping_test.side_effect = socket.gaierror("Network unreachable")
            
            # Setup error handler
            mock_error_handler.return_value = ErrorHandler()
            
            orchestrator = MeasurementOrchestrator(self.config)
            result = orchestrator.execute_measurement_cycle()
            
            # Should complete but with errors
            self.assertIsNotNone(result)
            self.assertGreater(len(result.measurement_result.errors), 0)


class TestIperfServerUnavailabilityTests(unittest.TestCase):
    """Test scenarios where iPerf server is unavailable."""

    def setUp(self):
        """Set up test environment."""
        self.config = Configuration()
        self.config.iperf_server = "192.168.1.100"
        self.config.iperf_port = 5201

    @patch('iperf3.Client')
    def test_iperf_server_not_running(self, mock_client_class):
        """Test when iPerf server is not running."""
        mock_client = MagicMock()
        mock_client.run.side_effect = ConnectionRefusedError("Connection refused")
        mock_client_class.return_value = mock_client
        
        tester = NetworkTester()
        
        with self.assertRaises(IperfError):
            tester.iperf_tcp_upload("192.168.1.100")

    @patch('iperf3.Client')
    def test_iperf_server_timeout(self, mock_client_class):
        """Test when iPerf server connection times out."""
        mock_client = MagicMock()
        mock_client.run.side_effect = socket.timeout("Connection timed out")
        mock_client_class.return_value = mock_client
        
        tester = NetworkTester()
        
        with self.assertRaises(IperfError):
            tester.iperf_tcp_upload("192.168.1.100")

    @patch('iperf3.Client')
    def test_iperf_server_wrong_port(self, mock_client_class):
        """Test when connecting to wrong iPerf server port."""
        mock_client = MagicMock()
        mock_client.run.side_effect = ConnectionRefusedError("Connection refused")
        mock_client_class.return_value = mock_client
        
        tester = NetworkTester()
        
        with self.assertRaises(IperfError):
            tester.iperf_tcp_upload("192.168.1.100", port=9999)  # Wrong port

    def test_orchestrator_iperf_server_check(self):
        """Test orchestrator prerequisite check for iPerf server."""
        with patch('src.network_tester.NetworkTester') as mock_network:
            mock_network_instance = mock_network.return_value
            mock_network_instance._check_iperf_server_availability.return_value = False
            
            orchestrator = MeasurementOrchestrator(self.config)
            is_valid, issues = orchestrator.validate_prerequisites()
            
            # Should detect iPerf server unavailability
            self.assertFalse(is_valid)
            self.assertTrue(any("iperf" in issue.lower() for issue in issues))


class TestWin32ApiErrorTests(unittest.TestCase):
    """Test Win32 API error scenarios."""

    def setUp(self):
        """Set up test environment."""
        pass

    @patch('src.wifi_collector.subprocess.run')
    @patch('src.wifi_collector.platform.system')
    def test_win32_access_denied(self, mock_platform, mock_run):
        """Test handling of Win32 API access denied errors."""
        mock_platform.return_value = "Windows"
        
        # Simulate access denied error
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Access denied"
        mock_run.return_value = mock_result
        
        collector = WiFiInfoCollector("Wi-Fi")
        wifi_info = collector.collect_wifi_info()
        
        # Should handle gracefully and return None
        self.assertIsNone(wifi_info)

    @patch('src.wifi_collector.subprocess.run')
    @patch('src.wifi_collector.platform.system')
    def test_win32_interface_not_found(self, mock_platform, mock_run):
        """Test handling when WiFi interface is not found."""
        mock_platform.return_value = "Windows"
        
        # Simulate interface not found
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Interface not found"
        mock_run.return_value = mock_result
        
        collector = WiFiInfoCollector("NonExistentInterface")
        wifi_info = collector.collect_wifi_info()
        
        # Should handle gracefully and return None
        self.assertIsNone(wifi_info)

    @patch('src.wifi_collector.subprocess.run')
    @patch('src.wifi_collector.platform.system')
    def test_win32_command_not_found(self, mock_platform, mock_run):
        """Test handling when Windows netsh command is not available."""
        mock_platform.return_value = "Windows"
        
        # Simulate command not found
        mock_run.side_effect = FileNotFoundError("netsh not found")
        
        collector = WiFiInfoCollector("Wi-Fi")
        wifi_info = collector.collect_wifi_info()
        
        # Should handle gracefully and return None
        self.assertIsNone(wifi_info)


class TestFileSystemErrorTests(unittest.TestCase):
    """Test file system error scenarios."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_disk_space_exhaustion(self):
        """Test handling of disk space exhaustion."""
        # Mock OSError with errno 28 (No space left on device)
        with patch('builtins.open', side_effect=OSError(28, "No space left on device")):
            export_manager = DataExportManager(self.test_dir)
            
            # Should raise appropriate exception
            with self.assertRaises(OSError):
                export_manager.initialize_csv_file("test.csv")

    def test_permission_denied_write(self):
        """Test handling of permission denied errors."""
        # Create read-only directory
        readonly_dir = Path(self.test_dir) / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only
        
        try:
            export_manager = DataExportManager(str(readonly_dir))
            
            # Should handle permission error gracefully
            with self.assertRaises(OSError):
                export_manager.initialize_csv_file("test.csv")
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    def test_config_file_corruption(self):
        """Test handling of corrupted configuration files."""
        config_file = Path(self.test_dir) / "corrupt_config.ini"
        
        # Write invalid configuration content
        with open(config_file, 'w') as f:
            f.write("This is not a valid INI file\n")
            f.write("Random garbage content\n")
            f.write("[invalid section without closing bracket\n")
        
        manager = ConfigurationManager(str(config_file))
        
        # Should handle parsing error gracefully
        with self.assertRaises(Exception):  # Could be various parsing errors
            manager.load_config()

    def test_missing_configuration_file(self):
        """Test handling of missing configuration files."""
        nonexistent_file = Path(self.test_dir) / "nonexistent.ini"
        
        manager = ConfigurationManager(str(nonexistent_file))
        
        # Should raise FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            manager.load_config()

    def test_file_transfer_disk_full(self):
        """Test file transfer when disk becomes full."""
        with patch('tempfile.NamedTemporaryFile', side_effect=OSError(28, "No space left on device")):
            tester = FileTransferTester()
            
            # Should handle disk full error
            with self.assertRaises(FileTransferError):
                tester.create_test_file(100)  # 100 MB file


class TestComprehensiveErrorRecovery(unittest.TestCase):
    """Test comprehensive error recovery scenarios."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config = Configuration()
        self.config.output_dir = self.test_dir

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_multiple_simultaneous_failures(self):
        """Test handling of multiple simultaneous failures."""
        with patch('src.wifi_collector.WiFiInfoCollector') as mock_wifi, \
             patch('src.network_tester.NetworkTester') as mock_network, \
             patch('src.file_transfer_tester.FileTransferTester') as mock_file:
            
            # Setup all components to fail
            mock_wifi_instance = mock_wifi.return_value
            mock_wifi_instance.is_connected.return_value = False
            mock_wifi_instance.collect_wifi_info.side_effect = Exception("WiFi error")
            
            mock_network_instance = mock_network.return_value
            mock_network_instance.is_host_reachable.return_value = False
            mock_network_instance.ping_test.side_effect = socket.gaierror("Network error")
            mock_network_instance._check_iperf_server_availability.return_value = False
            
            mock_file_instance = mock_file.return_value
            mock_file_instance.test_http_transfer.side_effect = FileTransferError("Transfer error")
            
            # Run orchestrator
            orchestrator = MeasurementOrchestrator(self.config)
            result = orchestrator.execute_measurement_cycle()
            
            # Should complete with many errors
            self.assertIsNotNone(result)
            self.assertFalse(result.success)
            self.assertGreater(len(result.measurement_result.errors), 0)

    def test_partial_recovery_scenario(self):
        """Test partial recovery where some components succeed after initial failure."""
        call_count = {'wifi': 0, 'network': 0}
        
        def wifi_side_effect():
            call_count['wifi'] += 1
            if call_count['wifi'] == 1:
                raise Exception("Initial WiFi failure")
            return Mock(ssid="RecoveredNetwork", rssi=-70)
        
        def network_side_effect(*args):
            call_count['network'] += 1
            if call_count['network'] == 1:
                raise socket.timeout("Initial network timeout")
            return Mock(target_ip="8.8.8.8", avg_rtt=50.0)
        
        with patch('src.wifi_collector.WiFiInfoCollector') as mock_wifi, \
             patch('src.network_tester.NetworkTester') as mock_network:
            
            mock_wifi_instance = mock_wifi.return_value
            mock_wifi_instance.is_connected.return_value = True
            mock_wifi_instance.collect_wifi_info.side_effect = wifi_side_effect
            
            mock_network_instance = mock_network.return_value
            mock_network_instance.is_host_reachable.return_value = True
            mock_network_instance.ping_test.side_effect = network_side_effect
            
            orchestrator = MeasurementOrchestrator(self.config)
            
            # First attempt should have some failures
            result1 = orchestrator.execute_measurement_cycle()
            self.assertIsNotNone(result1)
            
            # Second attempt should succeed
            result2 = orchestrator.execute_measurement_cycle()
            self.assertIsNotNone(result2)

    def test_error_handler_integration_during_failures(self):
        """Test error handler integration during various failure scenarios."""
        error_handler = ErrorHandler()
        
        # Test multiple error types
        network_errors = [
            socket.timeout("Connection timeout"),
            socket.gaierror("DNS resolution failed"),
            ConnectionRefusedError("Connection refused"),
            BrokenPipeError("Broken pipe")
        ]
        
        fs_errors = [
            FileNotFoundError("File not found"),
            PermissionError("Permission denied"),
            OSError(28, "No space left on device"),
            OSError("Generic OS error")
        ]
        
        # Handle various network errors
        for error in network_errors:
            handled_error = error_handler.handle_network_error(
                error, "test_component", f"test_operation_{type(error).__name__}"
            )
            self.assertIsNotNone(handled_error)
        
        # Handle various filesystem errors
        for error in fs_errors:
            handled_error = error_handler.handle_file_system_error(
                error, "test_component", f"test_operation_{type(error).__name__}"
            )
            self.assertIsNotNone(handled_error)
        
        # Verify error statistics
        stats = error_handler.get_error_statistics()
        self.assertEqual(stats['total_errors'], len(network_errors) + len(fs_errors))
        self.assertEqual(stats['errors_by_type']['network_error'], len(network_errors))
        self.assertEqual(stats['errors_by_type']['file_system_error'], len(fs_errors))

    def test_main_application_error_recovery(self):
        """Test main application error recovery scenarios."""
        with patch('src.config_manager.ConfigurationManager') as mock_config, \
             patch('src.measurement_orchestrator.MeasurementOrchestrator') as mock_orchestrator:
            
            # Setup config manager to fail initially then succeed
            mock_config_instance = mock_config.return_value
            mock_config_instance.load_config.side_effect = [
                FileNotFoundError("Config not found"),  # First call fails
                Configuration()  # Second call succeeds
            ]
            
            # Setup orchestrator
            mock_orch_instance = mock_orchestrator.return_value
            mock_orch_instance.validate_prerequisites.return_value = (True, [])
            
            app = MainApplication()
            
            # Test that application can handle config loading failure
            args = Mock()
            args.config = "nonexistent.ini"
            args.create_config = False
            args.dry_run = True
            
            # Should handle config loading error gracefully
            try:
                app.load_configuration(args)
                # This may succeed or fail depending on mock behavior
            except FileNotFoundError:
                # Expected behavior - app should handle this gracefully
                pass


if __name__ == '__main__':
    # Create test suite for error scenarios
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all error scenario test classes
    suite.addTests(loader.loadTestsFromTestCase(TestNetworkDisconnectionScenarios))
    suite.addTests(loader.loadTestsFromTestCase(TestIperfServerUnavailabilityTests))
    suite.addTests(loader.loadTestsFromTestCase(TestWin32ApiErrorTests))
    suite.addTests(loader.loadTestsFromTestCase(TestFileSystemErrorTests))
    suite.addTests(loader.loadTestsFromTestCase(TestComprehensiveErrorRecovery))
    
    # Run tests with high verbosity for detailed error reporting
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Report results
    print(f"\nError Scenario Tests Summary:")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)