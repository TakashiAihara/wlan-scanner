#!/usr/bin/env python3
"""Main application for wireless LAN scanner and performance analyzer."""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.config_manager import ConfigurationManager
from src.measurement_orchestrator import MeasurementOrchestrator, MeasurementSequence
from src.models import Configuration, MeasurementType
from src.error_handler import get_error_handler, ErrorType, ErrorSeverity


@dataclass
class ApplicationState:
    """Application state tracking."""
    running: bool = True
    shutdown_requested: bool = False
    measurement_count: int = 0
    start_time: Optional[datetime] = None
    last_measurement_time: Optional[datetime] = None


class MainApplication:
    """
    Main application class for wireless LAN scanner and performance analyzer.
    
    This class provides:
    - Command-line argument processing using argparse
    - Configuration loading and initialization
    - Integration with MeasurementOrchestrator for measurement execution and CSV output
    - Support for continuous measurement mode with configurable intervals
    - Proper logging setup and signal handling for graceful shutdown
    - Comprehensive help text and usage examples
    """
    
    def __init__(self):
        """Initialize the main application."""
        self.logger = None  # Will be initialized in setup_logging
        self.config_manager: Optional[ConfigurationManager] = None
        self.configuration: Optional[Configuration] = None
        self.measurement_orchestrator: Optional[MeasurementOrchestrator] = None
        self.error_handler = get_error_handler()
        self.state = ApplicationState()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # On Windows, also handle CTRL_BREAK_EVENT
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, self._signal_handler)
    
    def setup_logging(self, log_level: str = "INFO", log_file: Optional[str] = None, 
                      verbose: bool = False) -> None:
        """
        Set up logging configuration.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Optional log file path
            verbose: Enable verbose logging
        """
        # Convert string to logging level
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        
        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if verbose else numeric_level)
        
        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(simple_formatter if not verbose else detailed_formatter)
        root_logger.addHandler(console_handler)
        
        # File handler if specified
        if log_file:
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                
                file_handler = logging.FileHandler(log_path)
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(detailed_formatter)
                root_logger.addHandler(file_handler)
            except Exception as e:
                print(f"Warning: Could not set up file logging to {log_file}: {e}")
        
        # Set up application logger
        self.logger = logging.getLogger(__name__)
        self.logger.info("Logging initialized")
        
        # Suppress some noisy loggers unless in debug mode
        if numeric_level > logging.DEBUG:
            logging.getLogger('urllib3').setLevel(logging.WARNING)
            logging.getLogger('requests').setLevel(logging.WARNING)
    
    def create_argument_parser(self) -> argparse.ArgumentParser:
        """
        Create and configure the argument parser.
        
        Returns:
            Configured ArgumentParser instance
        """
        parser = argparse.ArgumentParser(
            description="Wireless LAN Scanner and Performance Analyzer",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s                           # Run single measurement with default config
  %(prog)s -c custom_config.ini      # Use custom configuration file
  %(prog)s --continuous              # Run continuous measurements
  %(prog)s --continuous -i 300       # Run every 5 minutes
  %(prog)s --tests ping,iperf_tcp    # Run only specific tests
  %(prog)s --dry-run                 # Validate configuration and prerequisites only
  %(prog)s --create-config           # Create default configuration file
  %(prog)s -v --log-level DEBUG      # Enable verbose debug logging
  %(prog)s --log-file scanner.log    # Log to file

Supported measurement types:
  wifi_info     - WiFi connection information (RSSI, channel, etc.)
  ping          - Ping latency and packet loss measurements
  iperf_tcp     - iPerf3 TCP throughput testing (bidirectional)
  iperf_udp     - iPerf3 UDP throughput testing
  file_transfer - File transfer performance testing

Configuration:
  The application uses configuration files in INI format. Use --create-config
  to generate a default configuration file, then customize as needed.
  
  Default configuration file: config/config.ini
  
  Configuration sections:
    [network]     - Network interface and target settings
    [measurement] - Measurement parameters (ping, iPerf, file transfer)
    [output]      - Output format and logging settings

Prerequisites:
  - WiFi connection active
  - Target hosts reachable
  - iPerf3 server running (for iPerf tests)
  - File server accessible (for file transfer tests)
            """.strip()
        )
        
        # Configuration options
        config_group = parser.add_argument_group('Configuration')
        config_group.add_argument(
            '-c', '--config', 
            type=str,
            help='Configuration file path (default: config/config.ini)'
        )
        config_group.add_argument(
            '--create-config',
            action='store_true',
            help='Create default configuration file and exit'
        )
        
        # Measurement options
        measurement_group = parser.add_argument_group('Measurement Control')
        measurement_group.add_argument(
            '--continuous',
            action='store_true',
            help='Run measurements continuously'
        )
        measurement_group.add_argument(
            '-i', '--interval',
            type=int,
            default=60,
            help='Interval between measurements in continuous mode (seconds, default: 60)'
        )
        measurement_group.add_argument(
            '--tests',
            type=str,
            help='Comma-separated list of tests to run: wifi_info,ping,iperf_tcp,iperf_udp,file_transfer'
        )
        measurement_group.add_argument(
            '--max-measurements',
            type=int,
            help='Maximum number of measurements to perform (continuous mode only)'
        )
        measurement_group.add_argument(
            '--timeout',
            type=int,
            help='Override default timeout for measurements (seconds)'
        )
        measurement_group.add_argument(
            '--location',
            type=str,
            help='Location identifier for measurements (e.g., "Room1", "Office")'
        )
        
        # Network options
        network_group = parser.add_argument_group('Network Settings')
        network_group.add_argument(
            '--interface',
            type=str,
            help='WiFi interface name (default: auto-detect)'
        )
        network_group.add_argument(
            '--targets',
            type=str,
            help='Comma-separated list of target IPs for ping tests (default: 8.8.8.8,1.1.1.1)'
        )
        
        # Ping options
        ping_group = parser.add_argument_group('Ping Settings')
        ping_group.add_argument(
            '--ping-count',
            type=int,
            help='Number of ping packets to send (default: 10)'
        )
        ping_group.add_argument(
            '--ping-size',
            type=int,
            help='Size of ping packets in bytes (default: 32)'
        )
        ping_group.add_argument(
            '--ping-interval',
            type=float,
            help='Interval between ping packets in seconds (default: 1.0)'
        )
        
        # iPerf3 options
        iperf_group = parser.add_argument_group('iPerf3 Settings')
        iperf_group.add_argument(
            '--iperf-server',
            type=str,
            help='iPerf3 server address'
        )
        iperf_group.add_argument(
            '--iperf-port',
            type=int,
            help='iPerf3 server port (default: 5201)'
        )
        iperf_group.add_argument(
            '--iperf-duration',
            type=int,
            help='iPerf3 test duration in seconds (default: 10)'
        )
        iperf_group.add_argument(
            '--iperf-parallel',
            type=int,
            help='Number of parallel iPerf3 connections (default: 1)'
        )
        iperf_group.add_argument(
            '--iperf-udp-bandwidth',
            type=str,
            help='Bandwidth for UDP tests (default: 10M)'
        )
        
        # Validation and testing
        validation_group = parser.add_argument_group('Validation')
        validation_group.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate configuration and prerequisites without running measurements'
        )
        validation_group.add_argument(
            '--validate-config',
            action='store_true',
            help='Validate configuration file and exit'
        )
        validation_group.add_argument(
            '--check-prerequisites',
            action='store_true',
            help='Check measurement prerequisites and exit'
        )
        
        # Output options
        output_group = parser.add_argument_group('Output and Logging')
        output_group.add_argument(
            '-v', '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
        output_group.add_argument(
            '--log-level',
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            default='INFO',
            help='Set logging level (default: INFO)'
        )
        output_group.add_argument(
            '--log-file',
            type=str,
            help='Log to file in addition to console'
        )
        output_group.add_argument(
            '--output-dir',
            type=str,
            help='Override output directory for measurement data'
        )
        output_group.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress non-essential output'
        )
        
        return parser
    
    def parse_arguments(self, args: Optional[List[str]] = None) -> argparse.Namespace:
        """
        Parse command-line arguments.
        
        Args:
            args: Arguments to parse (uses sys.argv if None)
            
        Returns:
            Parsed arguments namespace
        """
        parser = self.create_argument_parser()
        return parser.parse_args(args)
    
    def load_configuration(self, config_path: Optional[str] = None) -> Configuration:
        """
        Load application configuration.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Loaded Configuration object
            
        Raises:
            SystemExit: If configuration loading fails critically
        """
        # If no config file specified, check default location
        if not config_path:
            config_path = "config/config.ini"
        
        config_path_obj = Path(config_path)
        
        # If config file doesn't exist, use default configuration
        if not config_path_obj.exists():
            self.logger.info(f"Config file not found at {config_path}, using default configuration")
            self.logger.info("You can create a config file with --create-config or use command-line options")
            # Create default configuration
            from src.models import Configuration
            self.configuration = Configuration()
            # Set sensible defaults
            self.configuration.interface_name = "auto"
            self.configuration.target_ips = ["8.8.8.8", "1.1.1.1"]
            self.configuration.iperf_server = ""  # Empty = skip iPerf tests
            self.configuration.file_server = ""   # Empty = skip file transfer tests
            return self.configuration
        
        try:
            self.config_manager = ConfigurationManager(config_path)
            self.configuration = self.config_manager.load_config()
            
            self.logger.info(f"Configuration loaded successfully from {self.config_manager.config_path}")
            return self.configuration
            
        except Exception as e:
            self.logger.warning(f"Failed to load configuration: {e}, using defaults")
            from src.models import Configuration
            self.configuration = Configuration()
            self.configuration.interface_name = "auto"
            self.configuration.target_ips = ["8.8.8.8", "1.1.1.1"]
            self.configuration.iperf_server = ""
            self.configuration.file_server = ""
            return self.configuration
    
    def apply_cli_overrides(self, args: argparse.Namespace) -> None:
        """
        Apply command-line argument overrides to configuration.
        
        Args:
            args: Parsed command-line arguments
        """
        if not self.configuration:
            return
        
        # Network settings
        if args.interface:
            self.configuration.interface_name = args.interface
            self.logger.info(f"Interface overridden to {args.interface}")
        
        if args.targets:
            self.configuration.target_ips = [ip.strip() for ip in args.targets.split(',')]
            self.logger.info(f"Target IPs overridden to {self.configuration.target_ips}")
        
        # Ping settings
        if args.ping_count:
            self.configuration.ping_count = args.ping_count
            self.logger.info(f"Ping count overridden to {args.ping_count}")
        
        if args.ping_size:
            self.configuration.ping_size = args.ping_size
            self.logger.info(f"Ping size overridden to {args.ping_size} bytes")
        
        if args.ping_interval:
            self.configuration.ping_interval = args.ping_interval
            self.logger.info(f"Ping interval overridden to {args.ping_interval} seconds")
        
        # iPerf3 settings
        if args.iperf_server:
            self.configuration.iperf_server = args.iperf_server
            self.logger.info(f"iPerf3 server overridden to {args.iperf_server}")
        
        if args.iperf_port:
            self.configuration.iperf_port = args.iperf_port
            self.logger.info(f"iPerf3 port overridden to {args.iperf_port}")
        
        if args.iperf_duration:
            self.configuration.iperf_duration = args.iperf_duration
            self.logger.info(f"iPerf3 duration overridden to {args.iperf_duration} seconds")
        
        if args.iperf_parallel:
            self.configuration.iperf_parallel = args.iperf_parallel
            self.logger.info(f"iPerf3 parallel connections overridden to {args.iperf_parallel}")
        
        if args.iperf_udp_bandwidth:
            self.configuration.iperf_udp_bandwidth = args.iperf_udp_bandwidth
            self.logger.info(f"iPerf3 UDP bandwidth overridden to {args.iperf_udp_bandwidth}")
        
        # General settings
        if args.timeout:
            self.configuration.timeout = args.timeout
            self.logger.info(f"Timeout overridden to {args.timeout} seconds")
        
        # Override output directory
        if args.output_dir:
            self.configuration.output_dir = args.output_dir
            self.logger.info(f"Output directory overridden to {args.output_dir}")
        
        # Override scan interval for continuous mode
        if args.continuous and args.interval:
            self.configuration.scan_interval = args.interval
            self.logger.info(f"Scan interval set to {args.interval} seconds")
        
        # Apply logging overrides
        if args.verbose:
            self.configuration.verbose = True
        
        if args.log_level:
            self.configuration.log_level = args.log_level
        
        if args.quiet:
            self.configuration.log_level = "WARNING"
    
    def initialize_orchestrator(self) -> None:
        """Initialize the measurement orchestrator."""
        if not self.configuration:
            raise RuntimeError("Configuration must be loaded before initializing orchestrator")
        
        self.measurement_orchestrator = MeasurementOrchestrator(self.configuration)
        self.logger.info("Measurement orchestrator initialized")
    
    def create_measurement_sequence(self, args: argparse.Namespace) -> MeasurementSequence:
        """
        Create measurement sequence based on CLI arguments.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Configured MeasurementSequence
        """
        if not self.measurement_orchestrator:
            raise RuntimeError("Measurement orchestrator not initialized")
        
        # Parse enabled tests
        enabled_tests = set()
        if args.tests:
            test_names = [t.strip() for t in args.tests.split(',')]
            for test_name in test_names:
                try:
                    measurement_type = MeasurementType(test_name)
                    enabled_tests.add(measurement_type)
                except ValueError:
                    self.logger.warning(f"Unknown test type: {test_name}")
        else:
            # Enable all tests by default
            enabled_tests = set(MeasurementType)
        
        # Create timeout overrides
        timeout_overrides = {}
        if args.timeout:
            for test_type in enabled_tests:
                timeout_overrides[test_type] = float(args.timeout)
        
        if enabled_tests == set(MeasurementType):
            # Use default sequence if all tests are enabled
            sequence = self.measurement_orchestrator.create_default_sequence()
        else:
            # Create custom sequence with selected tests
            sequence = self.measurement_orchestrator.create_custom_sequence(
                enabled_measurements=enabled_tests,
                timeout_overrides=timeout_overrides
            )
        
        self.logger.info(f"Measurement sequence created with {len(sequence.steps)} steps")
        return sequence
    
    def validate_prerequisites(self) -> bool:
        """
        Validate measurement prerequisites.
        
        Returns:
            True if all prerequisites are met
        """
        if not self.measurement_orchestrator:
            return False
        
        self.logger.info("Validating measurement prerequisites...")
        
        is_valid, issues = self.measurement_orchestrator.validate_prerequisites()
        
        if is_valid:
            self.logger.info("All prerequisites validated successfully")
        else:
            self.logger.error("Prerequisites validation failed:")
            for issue in issues:
                self.logger.error(f"  - {issue}")
        
        return is_valid
    
    def run_single_measurement(self, sequence: MeasurementSequence) -> bool:
        """
        Run a single measurement cycle.
        
        Args:
            sequence: Measurement sequence to execute
            
        Returns:
            True if measurement completed successfully
        """
        if not self.measurement_orchestrator:
            return False
        
        try:
            self.logger.info("Starting single measurement cycle")
            # Get location from args if provided
            location = getattr(self.args, 'location', '') if hasattr(self, 'args') else ''
            result = self.measurement_orchestrator.execute_measurement_cycle(sequence, location=location)
            
            # Log results
            self.logger.info(f"Measurement {result.measurement_id} completed in {result.execution_time:.2f}s")
            
            # Log step results
            successful_steps = sum(1 for status in result.step_results.values() 
                                 if status.value == "completed")
            total_steps = len(result.step_results)
            self.logger.info(f"Steps completed: {successful_steps}/{total_steps}")
            
            # Log errors and warnings
            if result.errors:
                for error in result.errors:
                    self.logger.error(f"Measurement error: {error}")
            
            if result.warnings:
                for warning in result.warnings:
                    self.logger.warning(f"Measurement warning: {warning}")
            
            self.state.measurement_count += 1
            self.state.last_measurement_time = datetime.now()
            
            return len(result.errors) == 0
            
        except Exception as e:
            self.logger.error(f"Measurement failed: {e}")
            self.error_handler.handle_generic_error(
                e, ErrorType.MEASUREMENT_ERROR, "main_application", "run_single_measurement"
            )
            return False
    
    def run_continuous_measurements(self, sequence: MeasurementSequence, 
                                   interval: int, max_measurements: Optional[int] = None) -> None:
        """
        Run continuous measurements with specified interval.
        
        Args:
            sequence: Measurement sequence to execute
            interval: Interval between measurements in seconds
            max_measurements: Maximum number of measurements (None for unlimited)
        """
        self.logger.info(f"Starting continuous measurements (interval: {interval}s)")
        if max_measurements:
            self.logger.info(f"Maximum measurements: {max_measurements}")
        
        self.state.start_time = datetime.now()
        
        try:
            while self.state.running and not self.state.shutdown_requested:
                # Check if we've reached the maximum
                if max_measurements and self.state.measurement_count >= max_measurements:
                    self.logger.info(f"Reached maximum number of measurements ({max_measurements})")
                    break
                
                # Run measurement
                measurement_start = time.time()
                success = self.run_single_measurement(sequence)
                measurement_duration = time.time() - measurement_start
                
                if not success:
                    self.logger.warning("Measurement completed with errors")
                
                # Calculate sleep time (ensure we don't sleep negative time)
                sleep_time = max(0, interval - measurement_duration)
                
                if sleep_time > 0 and self.state.running and not self.state.shutdown_requested:
                    self.logger.debug(f"Sleeping for {sleep_time:.1f} seconds until next measurement")
                    
                    # Sleep in smaller intervals to allow for responsive shutdown
                    sleep_interval = min(5.0, sleep_time)  # Sleep in 5-second chunks
                    elapsed_sleep = 0
                    
                    while elapsed_sleep < sleep_time and self.state.running and not self.state.shutdown_requested:
                        time.sleep(sleep_interval)
                        elapsed_sleep += sleep_interval
                        sleep_interval = min(sleep_interval, sleep_time - elapsed_sleep)
        
        except KeyboardInterrupt:
            self.logger.info("Continuous measurements interrupted by user")
        
        except Exception as e:
            self.logger.error(f"Continuous measurements failed: {e}")
            self.error_handler.handle_generic_error(
                e, ErrorType.MEASUREMENT_ERROR, "main_application", "run_continuous_measurements"
            )
        
        finally:
            self._print_summary()
    
    def _signal_handler(self, signum: int, frame) -> None:
        """
        Handle shutdown signals gracefully.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_names = {
            signal.SIGINT: "SIGINT",
            signal.SIGTERM: "SIGTERM",
        }
        
        if sys.platform == "win32":
            signal_names[signal.SIGBREAK] = "SIGBREAK"
        
        signal_name = signal_names.get(signum, f"Signal {signum}")
        
        if not self.state.shutdown_requested:
            print(f"\n{signal_name} received. Initiating graceful shutdown...")
            if self.logger:
                self.logger.info(f"{signal_name} received. Initiating graceful shutdown...")
            
            self.state.shutdown_requested = True
            self.state.running = False
        else:
            print("Second shutdown signal received. Forcing exit...")
            if self.logger:
                self.logger.warning("Second shutdown signal received. Forcing exit...")
            sys.exit(1)
    
    def _print_summary(self) -> None:
        """Print execution summary."""
        if self.state.start_time:
            total_time = datetime.now() - self.state.start_time
            self.logger.info(f"Total execution time: {total_time}")
        
        self.logger.info(f"Total measurements completed: {self.state.measurement_count}")
        
        if self.state.last_measurement_time:
            self.logger.info(f"Last measurement: {self.state.last_measurement_time}")
    
    def cleanup(self) -> None:
        """Perform application cleanup."""
        if self.measurement_orchestrator:
            try:
                self.measurement_orchestrator.cleanup()
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Cleanup failed: {e}")
        
        if self.logger:
            self.logger.info("Application cleanup completed")
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """
        Main application entry point.
        
        Args:
            args: Command-line arguments (uses sys.argv if None)
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            # Parse arguments
            parsed_args = self.parse_arguments(args)
            self.args = parsed_args  # Store for later use
            
            # Set up logging early
            self.setup_logging(
                log_level=parsed_args.log_level,
                log_file=parsed_args.log_file,
                verbose=parsed_args.verbose and not parsed_args.quiet
            )
            
            self.logger.info("Wireless LAN Scanner and Performance Analyzer starting...")
            
            # Handle special modes
            if parsed_args.create_config:
                return self._handle_create_config(parsed_args)
            
            # Load configuration
            self.load_configuration(parsed_args.config)
            
            # Apply CLI overrides
            self.apply_cli_overrides(parsed_args)
            
            # Handle validation-only modes
            if parsed_args.validate_config:
                self.logger.info("Configuration validation successful")
                return 0
            
            # Initialize orchestrator
            self.initialize_orchestrator()
            
            # Check prerequisites
            if parsed_args.check_prerequisites:
                return 0 if self.validate_prerequisites() else 1
            
            # Create measurement sequence
            sequence = self.create_measurement_sequence(parsed_args)
            
            # Handle dry run
            if parsed_args.dry_run:
                self.logger.info("Dry run mode - validating configuration and prerequisites")
                prerequisites_ok = self.validate_prerequisites()
                if prerequisites_ok:
                    self.logger.info("Dry run completed successfully - ready to run measurements")
                    return 0
                else:
                    self.logger.error("Dry run failed - prerequisites not met")
                    return 1
            
            # Validate prerequisites before running
            if not self.validate_prerequisites():
                self.logger.error("Prerequisites not met. Use --dry-run to diagnose issues.")
                return 1
            
            # Run measurements
            if parsed_args.continuous:
                self.run_continuous_measurements(
                    sequence, 
                    parsed_args.interval, 
                    parsed_args.max_measurements
                )
            else:
                success = self.run_single_measurement(sequence)
                if not success:
                    return 1
            
            return 0
            
        except KeyboardInterrupt:
            if self.logger:
                self.logger.info("Application interrupted by user")
            return 0
        
        except Exception as e:
            if self.logger:
                self.logger.critical(f"Unexpected error: {e}", exc_info=True)
            else:
                print(f"Critical error: {e}", file=sys.stderr)
            return 1
        
        finally:
            try:
                self.cleanup()
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Cleanup error: {e}")
    
    def _handle_create_config(self, args: argparse.Namespace) -> int:
        """
        Handle --create-config mode.
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Exit code
        """
        try:
            config_path = args.config or "config/config.ini"
            config_manager = ConfigurationManager()
            config_manager.create_default_config(config_path)
            
            print(f"Default configuration file created: {config_path}")
            print("Please review and customize the configuration before running measurements.")
            return 0
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to create configuration: {e}")
            else:
                print(f"Error creating configuration: {e}", file=sys.stderr)
            return 1


def main() -> int:
    """Main entry point."""
    app = MainApplication()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())