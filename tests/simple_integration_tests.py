"""Simplified integration tests for wireless LAN analyzer."""

import unittest
import tempfile
import shutil
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Import components for testing
from src.models import Configuration, MeasurementResult, WiFiInfo, PingResult
from src.config_manager import ConfigurationManager
from src.data_export_manager import DataExportManager
from src.error_handler import ErrorHandler


class TestBasicIntegration(unittest.TestCase):
    """Test basic integration between core components."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "test_config.ini")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_configuration_workflow(self):
        """Test configuration creation, loading, and validation."""
        # Create config manager
        manager = ConfigurationManager()
        
        # Create default config
        manager.create_default_config(self.config_file)
        self.assertTrue(Path(self.config_file).exists())
        
        # Load configuration
        manager = ConfigurationManager(self.config_file)
        config = manager.load_config()
        
        # Validate
        self.assertIsInstance(config, Configuration)
        self.assertTrue(config.validate())
        self.assertTrue(manager.validate_network_settings())

    def test_data_models_integration(self):
        """Test data models with CSV export integration."""
        # Create test measurement result
        measurement = MeasurementResult(measurement_id="integration_test_001")
        
        # Add WiFi info
        measurement.wifi_info = WiFiInfo(
            ssid="TestNetwork",
            rssi=-65,
            link_quality=75,
            tx_rate=100.0,
            rx_rate=100.0,
            channel=11,
            frequency=2.462,
            interface_name="wlan0",
            mac_address="aa:bb:cc:dd:ee:ff"
        )
        
        # Add ping result
        measurement.ping_result = PingResult(
            target_ip="8.8.8.8",
            packets_sent=5,
            packets_received=5,
            packet_loss=0.0,
            min_rtt=10.5,
            max_rtt=25.3,
            avg_rtt=15.8,
            std_dev_rtt=3.2
        )
        
        # Add some errors for testing
        measurement.add_error("Test error message")
        
        # Test CSV conversion
        csv_row = measurement.to_csv_row()
        self.assertIn("measurement_id", csv_row)
        self.assertEqual(csv_row["measurement_id"], "integration_test_001")
        self.assertEqual(csv_row["wifi_ssid"], "TestNetwork")
        self.assertEqual(csv_row["ping_target"], "8.8.8.8")
        self.assertEqual(csv_row["error_count"], 1)

    def test_csv_export_workflow(self):
        """Test complete CSV export workflow."""
        # Create test measurements
        measurements = []
        for i in range(3):
            measurement = MeasurementResult(measurement_id=f"test_{i:03d}")
            measurement.wifi_info = WiFiInfo(
                ssid=f"TestNetwork_{i}",
                rssi=-60 - i,
                link_quality=80 - i,
                tx_rate=150.0,
                rx_rate=150.0,
                channel=6,
                frequency=2.437,
                interface_name="wlan0",
                mac_address="00:11:22:33:44:55"
            )
            measurements.append(measurement)
        
        # Create export manager
        export_manager = DataExportManager(self.output_dir)
        csv_file = os.path.join(self.output_dir, "integration_test.csv")
        
        # Export measurements
        export_manager.export_to_csv(measurements, csv_file)
        
        # Verify file exists and has content
        self.assertTrue(Path(csv_file).exists())
        
        with open(csv_file, 'r') as f:
            content = f.read()
            
        # Check header and data
        lines = content.strip().split('\n')
        self.assertGreater(len(lines), 1)  # Header + data rows
        
        # Check header contains expected fields
        header = lines[0]
        self.assertIn("measurement_id", header)
        self.assertIn("wifi_ssid", header)
        self.assertIn("wifi_rssi", header)
        
        # Check data rows
        self.assertEqual(len(lines), 4)  # Header + 3 data rows
        for i in range(1, 4):
            self.assertIn(f"test_{i-1:03d}", lines[i])
            self.assertIn(f"TestNetwork_{i-1}", lines[i])

    def test_error_handler_workflow(self):
        """Test error handler with various error types."""
        handler = ErrorHandler("integration_test")
        
        # Test network error
        import socket
        network_error = handler.handle_network_error(
            socket.timeout("Test timeout"),
            component="integration_test",
            operation="network_test"
        )
        
        self.assertIsNotNone(network_error)
        self.assertEqual(handler.error_counts[network_error.error_type], 1)
        
        # Test file system error
        fs_error = handler.handle_file_system_error(
            FileNotFoundError("Test file not found"),
            component="integration_test",
            operation="file_test"
        )
        
        self.assertIsNotNone(fs_error)
        self.assertEqual(handler.error_counts[fs_error.error_type], 1)
        
        # Test error statistics
        stats = handler.get_error_statistics()
        self.assertEqual(stats['total_errors'], 2)
        self.assertIn('latest_error', stats)
        
        # Test error history
        self.assertEqual(len(handler.error_history), 2)
        self.assertEqual(handler.error_history[0].component, "integration_test")

    def test_configuration_override_workflow(self):
        """Test configuration with command-line overrides."""
        # Create base configuration
        config = Configuration()
        config.ping_count = 10
        config.iperf_duration = 10
        config.verbose = False
        
        # Test that configuration validates
        self.assertTrue(config.validate())
        
        # Test configuration modification
        config.ping_count = 20
        config.verbose = True
        
        # Should still validate
        self.assertTrue(config.validate())
        
        # Test invalid configuration
        config.scan_interval = -1
        with self.assertRaises(ValueError):
            config.validate()

    def test_component_error_recovery(self):
        """Test error recovery across components."""
        # Create measurements with errors
        measurement_with_errors = MeasurementResult(measurement_id="error_test")
        measurement_with_errors.add_error("Network timeout occurred")
        measurement_with_errors.add_error("WiFi signal lost")
        measurement_with_errors.add_error("iPerf server unavailable")
        
        # Should still be exportable to CSV
        export_manager = DataExportManager(self.output_dir)
        csv_file = os.path.join(self.output_dir, "error_test.csv")
        
        # Export should succeed even with errors
        export_manager.export_to_csv([measurement_with_errors], csv_file)
        
        # Verify file exists and contains error count
        self.assertTrue(Path(csv_file).exists())
        
        with open(csv_file, 'r') as f:
            content = f.read()
        
        # Should contain error count
        self.assertIn("error_count", content)
        self.assertIn("3", content)  # 3 errors were added

    def test_data_validation_workflow(self):
        """Test data validation across the system."""
        # Test WiFi info validation
        wifi_info = WiFiInfo(
            ssid="TestNetwork",
            rssi=-65,  # Valid RSSI
            link_quality=75,  # Valid quality
            tx_rate=150.0,
            rx_rate=150.0,
            channel=6,
            frequency=2.437,
            interface_name="wlan0",
            mac_address="00:11:22:33:44:55"
        )
        
        # Should validate successfully
        self.assertTrue(wifi_info.validate())
        
        # Test invalid WiFi info
        invalid_wifi = WiFiInfo(
            ssid="TestNetwork",
            rssi=10,  # Invalid RSSI (should be negative)
            link_quality=75,
            tx_rate=150.0,
            rx_rate=150.0,
            channel=6,
            frequency=2.437,
            interface_name="wlan0",
            mac_address="00:11:22:33:44:55"
        )
        
        # Should raise validation error
        with self.assertRaises(ValueError):
            invalid_wifi.validate()

    def test_file_operations_workflow(self):
        """Test file operations across components."""
        # Test CSV file initialization
        export_manager = DataExportManager(self.output_dir)
        csv_file = os.path.join(self.output_dir, "file_ops_test.csv")
        
        # Initialize CSV file
        export_manager.initialize_csv_file(csv_file)
        self.assertTrue(Path(csv_file).exists())
        
        # Verify CSV headers
        with open(csv_file, 'r') as f:
            header_line = f.readline().strip()
        
        expected_fields = [
            "measurement_id", "timestamp", "wifi_ssid", "wifi_rssi",
            "ping_target", "ping_avg_rtt", "error_count"
        ]
        
        for field in expected_fields:
            self.assertIn(field, header_line)
        
        # Test appending data
        measurement = MeasurementResult(measurement_id="file_ops_test")
        export_manager.append_measurement(measurement, csv_file)
        
        # Verify file has data
        with open(csv_file, 'r') as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 2)  # Header + 1 data row
        self.assertIn("file_ops_test", lines[1])

    def test_memory_efficiency(self):
        """Test memory efficiency with large datasets."""
        # Create large number of measurements
        measurements = []
        for i in range(100):  # 100 measurements
            measurement = MeasurementResult(measurement_id=f"mem_test_{i:03d}")
            measurements.append(measurement)
        
        # Export should handle large datasets efficiently
        export_manager = DataExportManager(self.output_dir)
        csv_file = os.path.join(self.output_dir, "large_dataset.csv")
        
        # This should complete without memory issues
        export_manager.export_to_csv(measurements, csv_file)
        
        # Verify file was created with correct number of rows
        with open(csv_file, 'r') as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 101)  # Header + 100 data rows


if __name__ == '__main__':
    # Run only the basic integration tests
    unittest.main(verbosity=2)