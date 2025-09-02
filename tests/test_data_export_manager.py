"""Unit tests for DataExportManager."""

import csv
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from src.data_export_manager import DataExportManager
from src.models import (
    MeasurementResult, 
    WiFiInfo, 
    PingResult, 
    IperfTcpResult, 
    IperfUdpResult, 
    FileTransferResult
)


class TestDataExportManager(unittest.TestCase):
    """Test cases for DataExportManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = DataExportManager(self.temp_dir)
        
        # Create sample measurement data
        self.wifi_info = WiFiInfo(
            ssid="TestNetwork",
            rssi=-45,
            link_quality=85,
            tx_rate=150.0,
            rx_rate=120.0,
            channel=6,
            frequency=2.437,
            interface_name="Wi-Fi",
            mac_address="00:11:22:33:44:55"
        )
        
        self.ping_result = PingResult(
            target_ip="192.168.1.1",
            packets_sent=10,
            packets_received=9,
            packet_loss=10.0,
            min_rtt=1.5,
            max_rtt=5.2,
            avg_rtt=2.8,
            std_dev_rtt=0.9
        )
        
        self.iperf_tcp_result = IperfTcpResult(
            server_ip="192.168.1.100",
            server_port=5201,
            duration=10.0,
            bytes_sent=1048576,
            bytes_received=1048576,
            throughput_upload=85.5,
            throughput_download=90.2,
            retransmits=2
        )
        
        self.iperf_udp_result = IperfUdpResult(
            server_ip="192.168.1.100",
            server_port=5201,
            duration=10.0,
            bytes_sent=1048576,
            packets_sent=1000,
            packets_lost=5,
            packet_loss=0.5,
            jitter=2.1,
            throughput=80.0
        )
        
        self.file_transfer_result = FileTransferResult(
            server_address="192.168.1.100",
            file_size=104857600,  # 100MB
            transfer_time=12.5,
            transfer_speed=8.39,  # MB/s
            protocol="SMB",
            direction="upload"
        )
        
        self.measurement = MeasurementResult(
            measurement_id="test_001",
            wifi_info=self.wifi_info,
            ping_result=self.ping_result,
            iperf_tcp_result=self.iperf_tcp_result,
            iperf_udp_result=self.iperf_udp_result,
            file_transfer_result=self.file_transfer_result
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_default_directory(self):
        """Test DataExportManager initialization with default directory."""
        manager = DataExportManager()
        self.assertEqual(manager.output_directory, Path("data"))
    
    def test_init_custom_directory(self):
        """Test DataExportManager initialization with custom directory."""
        custom_dir = Path(self.temp_dir) / "custom" / "path"
        manager = DataExportManager(custom_dir)
        self.assertEqual(manager.output_directory, Path(custom_dir))
        self.assertTrue(custom_dir.exists())
    
    def test_csv_headers_property(self):
        """Test csv_headers property returns correct headers."""
        headers = self.manager.csv_headers
        
        # Check that essential headers are present
        expected_headers = [
            "measurement_id", "timestamp", "wifi_ssid", "wifi_rssi",
            "ping_target", "ping_packet_loss", "iperf_tcp_upload",
            "iperf_udp_throughput", "file_transfer_speed", "error_count"
        ]
        
        for header in expected_headers:
            self.assertIn(header, headers)
    
    def test_initialize_csv_file_new(self):
        """Test CSV file initialization for new file."""
        file_path = Path(self.temp_dir) / "test_new.csv"
        
        result = self.manager.initialize_csv_file(file_path)
        
        self.assertTrue(result)
        self.assertTrue(file_path.exists())
        
        # Check that headers were written
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            self.assertEqual(headers, self.manager.csv_headers)
    
    def test_initialize_csv_file_existing_no_overwrite(self):
        """Test CSV file initialization for existing file without overwrite."""
        file_path = Path(self.temp_dir) / "test_existing.csv"
        
        # Create existing file
        with open(file_path, 'w') as f:
            f.write("existing content")
        
        result = self.manager.initialize_csv_file(file_path, overwrite=False)
        
        self.assertFalse(result)
        
        # Check that file content was not changed
        with open(file_path, 'r') as f:
            content = f.read()
            self.assertEqual(content, "existing content")
    
    def test_initialize_csv_file_existing_with_overwrite(self):
        """Test CSV file initialization for existing file with overwrite."""
        file_path = Path(self.temp_dir) / "test_overwrite.csv"
        
        # Create existing file
        with open(file_path, 'w') as f:
            f.write("existing content")
        
        result = self.manager.initialize_csv_file(file_path, overwrite=True)
        
        self.assertTrue(result)
        
        # Check that headers were written
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)
            self.assertEqual(headers, self.manager.csv_headers)
    
    @patch('src.data_export_manager.logger')
    def test_initialize_csv_file_error(self, mock_logger):
        """Test CSV file initialization error handling."""
        # Use invalid path to trigger OSError
        invalid_path = Path("/invalid/path/test.csv")
        
        with self.assertRaises(OSError):
            self.manager.initialize_csv_file(invalid_path)
        
        mock_logger.error.assert_called()
    
    def test_write_measurement_new_file(self):
        """Test writing measurement to new file."""
        file_path = Path(self.temp_dir) / "test_measurement.csv"
        
        result = self.manager.write_measurement(file_path, self.measurement, append=False)
        
        self.assertTrue(result)
        self.assertTrue(file_path.exists())
        
        # Check file contents
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            
            row = rows[0]
            self.assertEqual(row['measurement_id'], 'test_001')
            self.assertEqual(row['wifi_ssid'], 'TestNetwork')
            self.assertEqual(row['wifi_rssi'], '-45')
    
    def test_write_measurement_append_to_existing(self):
        """Test appending measurement to existing file."""
        file_path = Path(self.temp_dir) / "test_append.csv"
        
        # Create initial measurement
        self.manager.write_measurement(file_path, self.measurement, append=False)
        
        # Create second measurement
        measurement2 = MeasurementResult(
            measurement_id="test_002",
            wifi_info=WiFiInfo(
                ssid="TestNetwork2",
                rssi=-50,
                link_quality=75,
                tx_rate=100.0,
                rx_rate=90.0,
                channel=11,
                frequency=2.462,
                interface_name="Wi-Fi",
                mac_address="00:11:22:33:44:66"
            )
        )
        
        # Append second measurement
        result = self.manager.write_measurement(file_path, measurement2, append=True)
        
        self.assertTrue(result)
        
        # Check file contents
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            
            self.assertEqual(rows[0]['measurement_id'], 'test_001')
            self.assertEqual(rows[1]['measurement_id'], 'test_002')
            self.assertEqual(rows[1]['wifi_ssid'], 'TestNetwork2')
    
    def test_write_measurement_append_to_nonexistent(self):
        """Test appending measurement to nonexistent file (should create)."""
        file_path = Path(self.temp_dir) / "test_nonexistent.csv"
        
        result = self.manager.write_measurement(file_path, self.measurement, append=True)
        
        self.assertTrue(result)
        self.assertTrue(file_path.exists())
        
        # Check that headers and data were written
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['measurement_id'], 'test_001')
    
    @patch('src.data_export_manager.logger')
    def test_write_measurement_error(self, mock_logger):
        """Test write measurement error handling."""
        # Use invalid path to trigger OSError
        invalid_path = Path("/invalid/path/test.csv")
        
        with self.assertRaises(OSError):
            self.manager.write_measurement(invalid_path, self.measurement)
        
        mock_logger.error.assert_called()
    
    def test_write_measurements_batch_success(self):
        """Test successful batch write of measurements."""
        file_path = Path(self.temp_dir) / "test_batch.csv"
        
        # Create multiple measurements
        measurements = []
        for i in range(3):
            measurement = MeasurementResult(
                measurement_id=f"test_{i:03d}",
                wifi_info=WiFiInfo(
                    ssid=f"TestNetwork{i}",
                    rssi=-45 - i,
                    link_quality=85 - i*5,
                    tx_rate=150.0 - i*10,
                    rx_rate=120.0 - i*10,
                    channel=6 + i,
                    frequency=2.437 + i*0.005,
                    interface_name="Wi-Fi",
                    mac_address=f"00:11:22:33:44:{55+i:02x}"
                )
            )
            measurements.append(measurement)
        
        written_count = self.manager.write_measurements_batch(file_path, measurements, append=False)
        
        self.assertEqual(written_count, 3)
        self.assertTrue(file_path.exists())
        
        # Check file contents
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            self.assertEqual(len(rows), 3)
            
            for i, row in enumerate(rows):
                self.assertEqual(row['measurement_id'], f'test_{i:03d}')
                self.assertEqual(row['wifi_ssid'], f'TestNetwork{i}')
    
    def test_write_measurements_batch_empty(self):
        """Test batch write with empty measurements list."""
        file_path = Path(self.temp_dir) / "test_empty_batch.csv"
        
        written_count = self.manager.write_measurements_batch(file_path, [], append=False)
        
        self.assertEqual(written_count, 0)
    
    def test_write_measurements_batch_append(self):
        """Test batch write with append mode."""
        file_path = Path(self.temp_dir) / "test_batch_append.csv"
        
        # Write initial measurement
        self.manager.write_measurement(file_path, self.measurement, append=False)
        
        # Create batch measurements
        measurements = []
        for i in range(2):
            measurement = MeasurementResult(
                measurement_id=f"batch_{i:03d}",
                wifi_info=WiFiInfo(
                    ssid=f"BatchNetwork{i}",
                    rssi=-50 - i,
                    link_quality=80 - i*5,
                    tx_rate=100.0,
                    rx_rate=90.0,
                    channel=11,
                    frequency=2.462,
                    interface_name="Wi-Fi",
                    mac_address="00:11:22:33:44:77"
                )
            )
            measurements.append(measurement)
        
        written_count = self.manager.write_measurements_batch(file_path, measurements, append=True)
        
        self.assertEqual(written_count, 2)
        
        # Check total rows
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            self.assertEqual(len(rows), 3)  # 1 initial + 2 batch
    
    @patch('src.data_export_manager.logger')
    def test_write_measurements_batch_partial_failure(self, mock_logger):
        """Test batch write with some measurements failing."""
        file_path = Path(self.temp_dir) / "test_batch_partial.csv"
        
        # Create measurements with one problematic measurement
        measurements = [self.measurement]
        
        # Create a measurement that will cause an error in to_csv_row()
        problematic_measurement = MeasurementResult(measurement_id="problematic")
        
        # Mock to_csv_row to raise exception for problematic measurement
        original_to_csv_row = MeasurementResult.to_csv_row
        def mock_to_csv_row(self):
            if self.measurement_id == "problematic":
                raise ValueError("Test error")
            return original_to_csv_row(self)
        
        with patch.object(MeasurementResult, 'to_csv_row', mock_to_csv_row):
            measurements.append(problematic_measurement)
            written_count = self.manager.write_measurements_batch(file_path, measurements, append=False)
        
        # Should have written only the good measurement
        self.assertEqual(written_count, 1)
        mock_logger.error.assert_called()
    
    def test_export_to_csv_with_filename(self):
        """Test export to CSV with specified filename."""
        measurements = [self.measurement]
        filename = "custom_export.csv"
        
        result_path = self.manager.export_to_csv(measurements, filename=filename)
        
        expected_path = Path(self.temp_dir) / filename
        self.assertEqual(result_path, expected_path)
        self.assertTrue(result_path.exists())
        
        # Check contents
        with open(result_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['measurement_id'], 'test_001')
    
    def test_export_to_csv_auto_filename(self):
        """Test export to CSV with auto-generated filename."""
        measurements = [self.measurement]
        
        with patch('src.data_export_manager.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20231225_143045"
            mock_datetime.now.return_value = mock_now
            
            result_path = self.manager.export_to_csv(measurements)
        
        expected_filename = "wlan_measurements_20231225_143045.csv"
        expected_path = Path(self.temp_dir) / expected_filename
        self.assertEqual(result_path, expected_path)
    
    def test_export_to_csv_add_extension(self):
        """Test export to CSV adds .csv extension if missing."""
        measurements = [self.measurement]
        filename = "export_without_extension"
        
        result_path = self.manager.export_to_csv(measurements, filename=filename)
        
        expected_path = Path(self.temp_dir) / "export_without_extension.csv"
        self.assertEqual(result_path, expected_path)
        self.assertTrue(result_path.exists())
    
    def test_export_to_csv_empty_measurements(self):
        """Test export to CSV with empty measurements list."""
        with self.assertRaises(ValueError) as cm:
            self.manager.export_to_csv([])
        
        self.assertIn("No measurements provided", str(cm.exception))
    
    def test_export_to_csv_append_mode(self):
        """Test export to CSV with append mode."""
        measurements1 = [self.measurement]
        measurements2 = [MeasurementResult(measurement_id="test_002")]
        filename = "append_test.csv"
        
        # First export
        self.manager.export_to_csv(measurements1, filename=filename, append=False)
        
        # Second export with append
        result_path = self.manager.export_to_csv(measurements2, filename=filename, append=True)
        
        # Check total rows
        with open(result_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
    
    def test_append_measurement_default_filename(self):
        """Test append measurement with default filename."""
        result_path = self.manager.append_measurement(self.measurement)
        
        expected_path = Path(self.temp_dir) / "wlan_measurements.csv"
        self.assertEqual(result_path, expected_path)
        self.assertTrue(result_path.exists())
    
    def test_append_measurement_custom_filename(self):
        """Test append measurement with custom filename."""
        filename = "custom_append.csv"
        
        result_path = self.manager.append_measurement(self.measurement, filename=filename)
        
        expected_path = Path(self.temp_dir) / filename
        self.assertEqual(result_path, expected_path)
        self.assertTrue(result_path.exists())
    
    def test_append_measurement_add_extension(self):
        """Test append measurement adds .csv extension if missing."""
        filename = "append_no_extension"
        
        result_path = self.manager.append_measurement(self.measurement, filename=filename)
        
        expected_path = Path(self.temp_dir) / "append_no_extension.csv"
        self.assertEqual(result_path, expected_path)
    
    def test_append_measurement_multiple(self):
        """Test appending multiple measurements."""
        filename = "multiple_append.csv"
        
        # Append first measurement
        self.manager.append_measurement(self.measurement, filename=filename)
        
        # Append second measurement
        measurement2 = MeasurementResult(measurement_id="test_002")
        result_path = self.manager.append_measurement(measurement2, filename=filename)
        
        # Check total rows
        with open(result_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
    
    def test_validate_csv_file_valid(self):
        """Test validation of valid CSV file."""
        file_path = Path(self.temp_dir) / "valid_test.csv"
        
        # Create valid CSV file
        self.manager.write_measurement(file_path, self.measurement, append=False)
        
        result = self.manager.validate_csv_file(file_path)
        
        self.assertTrue(result)
    
    def test_validate_csv_file_nonexistent(self):
        """Test validation of nonexistent CSV file."""
        file_path = Path(self.temp_dir) / "nonexistent.csv"
        
        result = self.manager.validate_csv_file(file_path)
        
        self.assertFalse(result)
    
    def test_validate_csv_file_empty(self):
        """Test validation of empty CSV file."""
        file_path = Path(self.temp_dir) / "empty_test.csv"
        
        # Create empty file
        file_path.touch()
        
        result = self.manager.validate_csv_file(file_path)
        
        self.assertFalse(result)
    
    def test_validate_csv_file_wrong_headers(self):
        """Test validation of CSV file with wrong headers."""
        file_path = Path(self.temp_dir) / "wrong_headers.csv"
        
        # Create CSV with wrong headers
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["wrong", "headers"])
        
        result = self.manager.validate_csv_file(file_path)
        
        self.assertFalse(result)
    
    def test_validate_csv_file_extra_headers(self):
        """Test validation of CSV file with extra headers."""
        file_path = Path(self.temp_dir) / "extra_headers.csv"
        
        # Create CSV with extra headers
        headers = self.manager.csv_headers + ["extra_header"]
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
        
        result = self.manager.validate_csv_file(file_path)
        
        self.assertFalse(result)
    
    def test_validate_csv_file_missing_headers(self):
        """Test validation of CSV file with missing headers."""
        file_path = Path(self.temp_dir) / "missing_headers.csv"
        
        # Create CSV with missing headers
        headers = self.manager.csv_headers[:-1]  # Remove last header
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
        
        result = self.manager.validate_csv_file(file_path)
        
        self.assertFalse(result)
    
    @patch('src.data_export_manager.logger')
    def test_validate_csv_file_read_error(self, mock_logger):
        """Test validation with file read error."""
        file_path = Path(self.temp_dir) / "test.csv"
        
        # Create file then simulate read error
        file_path.touch()
        
        with patch('builtins.open', side_effect=OSError("Read error")):
            result = self.manager.validate_csv_file(file_path)
        
        self.assertFalse(result)
        mock_logger.error.assert_called()
    
    def test_get_output_path(self):
        """Test get_output_path method."""
        filename = "test_file.csv"
        
        result = self.manager.get_output_path(filename)
        
        expected = Path(self.temp_dir) / filename
        self.assertEqual(result, expected)
    
    def test_csv_headers_caching(self):
        """Test that CSV headers are cached properly."""
        # First access
        headers1 = self.manager.csv_headers
        
        # Second access should return the same object (cached)
        headers2 = self.manager.csv_headers
        
        self.assertIs(headers1, headers2)
    
    def test_directory_creation_on_init(self):
        """Test that output directory is created on initialization."""
        new_dir = Path(self.temp_dir) / "new_subdir"
        
        # Ensure directory doesn't exist
        self.assertFalse(new_dir.exists())
        
        # Create manager with new directory
        manager = DataExportManager(new_dir)
        
        # Directory should be created
        self.assertTrue(new_dir.exists())
        self.assertEqual(manager.output_directory, new_dir)


if __name__ == '__main__':
    unittest.main()