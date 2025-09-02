"""Data export management for WLAN scanner measurements."""

import csv
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
try:
    from .models import MeasurementResult
except ImportError:
    from models import MeasurementResult


logger = logging.getLogger(__name__)


class DataExportManager:
    """Manages CSV data export for measurement results."""
    
    def __init__(self, output_directory: Optional[Union[str, Path]] = None):
        """
        Initialize the DataExportManager.
        
        Args:
            output_directory: Directory for output files. Defaults to 'data' if None.
        """
        self.output_directory = Path(output_directory) if output_directory else Path("data")
        self.output_directory.mkdir(exist_ok=True, parents=True)
        self._csv_headers: Optional[List[str]] = None
    
    @property
    def csv_headers(self) -> List[str]:
        """Get the CSV headers for all possible measurement fields."""
        if self._csv_headers is None:
            # Define all possible CSV headers based on MeasurementResult.to_csv_row()
            self._csv_headers = [
                # Base fields
                "measurement_id",
                "timestamp",
                # WiFi info fields
                "wifi_ssid",
                "wifi_rssi",
                "wifi_link_quality",
                "wifi_tx_rate",
                "wifi_rx_rate",
                "wifi_channel",
                "wifi_frequency",
                # Ping result fields
                "ping_target",
                "ping_packet_loss",
                "ping_avg_rtt",
                "ping_min_rtt",
                "ping_max_rtt",
                "ping_std_dev",
                # iPerf TCP result fields
                "iperf_tcp_upload",
                "iperf_tcp_download",
                "iperf_tcp_retransmits",
                # iPerf UDP result fields
                "iperf_udp_throughput",
                "iperf_udp_packet_loss",
                "iperf_udp_jitter",
                # File transfer result fields
                "file_transfer_speed",
                "file_transfer_throughput",
                "file_transfer_direction",
                # Error count
                "error_count",
            ]
        return self._csv_headers
    
    def initialize_csv_file(self, file_path: Union[str, Path], overwrite: bool = False) -> bool:
        """
        Initialize a CSV file with headers.
        
        Args:
            file_path: Path to the CSV file
            overwrite: If True, overwrite existing file. If False, skip if exists.
        
        Returns:
            bool: True if file was initialized, False if skipped
        
        Raises:
            OSError: If file operations fail
        """
        file_path = Path(file_path)
        
        try:
            # Check if file exists and overwrite is False
            if file_path.exists() and not overwrite:
                logger.info(f"CSV file already exists, skipping initialization: {file_path}")
                return False
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write headers to file
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                writer.writeheader()
            
            logger.info(f"CSV file initialized with headers: {file_path}")
            return True
            
        except OSError as e:
            logger.error(f"Failed to initialize CSV file {file_path}: {e}")
            raise
    
    def write_measurement(self, file_path: Union[str, Path], 
                         measurement: MeasurementResult,
                         append: bool = True) -> bool:
        """
        Write a single measurement to CSV file.
        
        Args:
            file_path: Path to the CSV file
            measurement: MeasurementResult to write
            append: If True, append to file. If False, create new file.
        
        Returns:
            bool: True if write was successful
        
        Raises:
            OSError: If file operations fail
        """
        file_path = Path(file_path)
        
        try:
            # Check if file exists when appending
            file_exists = file_path.exists()
            
            if append and not file_exists:
                # Initialize file with headers if it doesn't exist
                self.initialize_csv_file(file_path)
                file_exists = True
            
            # Get CSV row data
            row_data = measurement.to_csv_row()
            
            # Ensure all expected fields are present
            for header in self.csv_headers:
                if header not in row_data:
                    row_data[header] = None
            
            # Write mode based on append flag and file existence
            mode = 'a' if (append and file_exists) else 'w'
            
            with open(file_path, mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                
                # Write header if creating new file
                if mode == 'w':
                    writer.writeheader()
                
                writer.writerow(row_data)
            
            logger.debug(f"Measurement written to CSV: {file_path}")
            return True
            
        except OSError as e:
            logger.error(f"Failed to write measurement to CSV {file_path}: {e}")
            raise
    
    def write_measurements_batch(self, file_path: Union[str, Path],
                               measurements: List[MeasurementResult],
                               append: bool = True) -> int:
        """
        Write multiple measurements to CSV file in batch.
        
        Args:
            file_path: Path to the CSV file
            measurements: List of MeasurementResult objects to write
            append: If True, append to file. If False, create new file.
        
        Returns:
            int: Number of measurements successfully written
        
        Raises:
            OSError: If file operations fail
        """
        if not measurements:
            logger.warning("No measurements provided for batch write")
            return 0
        
        file_path = Path(file_path)
        
        try:
            # Check if file exists when appending
            file_exists = file_path.exists()
            
            if append and not file_exists:
                # Initialize file with headers if it doesn't exist
                self.initialize_csv_file(file_path)
                file_exists = True
            
            # Write mode based on append flag and file existence
            mode = 'a' if (append and file_exists) else 'w'
            
            written_count = 0
            
            with open(file_path, mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.csv_headers)
                
                # Write header if creating new file
                if mode == 'w':
                    writer.writeheader()
                
                for measurement in measurements:
                    try:
                        # Get CSV row data
                        row_data = measurement.to_csv_row()
                        
                        # Ensure all expected fields are present
                        for header in self.csv_headers:
                            if header not in row_data:
                                row_data[header] = None
                        
                        writer.writerow(row_data)
                        written_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to process measurement {measurement.measurement_id}: {e}")
                        continue
            
            logger.info(f"Batch write completed: {written_count}/{len(measurements)} measurements written to {file_path}")
            return written_count
            
        except OSError as e:
            logger.error(f"Failed to write measurements batch to CSV {file_path}: {e}")
            raise
    
    def export_to_csv(self, measurements: List[MeasurementResult],
                     filename: Optional[str] = None,
                     append: bool = False) -> Path:
        """
        Export measurements to a CSV file with automatic filename generation.
        
        Args:
            measurements: List of MeasurementResult objects to export
            filename: Optional filename. If None, auto-generate based on timestamp.
            append: If True, append to existing file. If False, create new file.
        
        Returns:
            Path: Path to the created CSV file
        
        Raises:
            ValueError: If no measurements provided
            OSError: If file operations fail
        """
        if not measurements:
            raise ValueError("No measurements provided for export")
        
        # Generate filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"wlan_measurements_{timestamp}.csv"
        
        # Ensure .csv extension
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        file_path = self.output_directory / filename
        
        # Write measurements
        written_count = self.write_measurements_batch(file_path, measurements, append=append)
        
        if written_count == 0:
            logger.warning(f"No measurements were written to {file_path}")
        
        logger.info(f"Export completed: {written_count} measurements exported to {file_path}")
        return file_path
    
    def append_measurement(self, measurement: MeasurementResult,
                          filename: Optional[str] = None) -> Path:
        """
        Append a single measurement to an existing or new CSV file.
        
        Args:
            measurement: MeasurementResult to append
            filename: Optional filename. If None, use default name.
        
        Returns:
            Path: Path to the CSV file
        
        Raises:
            OSError: If file operations fail
        """
        # Generate filename if not provided
        if filename is None:
            filename = "wlan_measurements.csv"
        
        # Ensure .csv extension
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        file_path = self.output_directory / filename
        
        # Write measurement
        self.write_measurement(file_path, measurement, append=True)
        
        logger.debug(f"Measurement appended to {file_path}")
        return file_path
    
    def validate_csv_file(self, file_path: Union[str, Path]) -> bool:
        """
        Validate that a CSV file has the correct headers.
        
        Args:
            file_path: Path to the CSV file to validate
        
        Returns:
            bool: True if file is valid, False otherwise
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"CSV file does not exist: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                # Try to read the first line as headers
                reader = csv.reader(csvfile)
                first_row = next(reader, None)
                
                if first_row is None:
                    logger.error(f"CSV file is empty: {file_path}")
                    return False
                
                # Check if headers match expected headers
                expected_headers = set(self.csv_headers)
                actual_headers = set(first_row)
                
                if expected_headers != actual_headers:
                    missing = expected_headers - actual_headers
                    extra = actual_headers - expected_headers
                    
                    if missing:
                        logger.error(f"CSV file missing headers: {missing}")
                    if extra:
                        logger.warning(f"CSV file has extra headers: {extra}")
                    
                    return False
                
                logger.info(f"CSV file validation successful: {file_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to validate CSV file {file_path}: {e}")
            return False
    
    def get_output_path(self, filename: str) -> Path:
        """
        Get the full output path for a given filename.
        
        Args:
            filename: Name of the file
        
        Returns:
            Path: Full path to the file in the output directory
        """
        return self.output_directory / filename