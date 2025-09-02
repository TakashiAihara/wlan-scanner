"""Unit tests for main application functionality."""

import pytest
import tempfile
import os
import signal
import time
import threading
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
from datetime import datetime
from io import StringIO
import sys
import argparse

# Import the main application and related classes
from main import MainApplication, ApplicationState
from src.config_manager import ConfigurationManager
from src.measurement_orchestrator import MeasurementOrchestrator, OrchestrationResult
from src.models import Configuration, MeasurementType, MeasurementResult


class TestApplicationState:
    """Test ApplicationState dataclass."""
    
    def test_application_state_initialization(self):
        """Test ApplicationState initialization with default values."""
        state = ApplicationState()
        
        assert state.running is True
        assert state.shutdown_requested is False
        assert state.measurement_count == 0
        assert state.start_time is None
        assert state.last_measurement_time is None
    
    def test_application_state_custom_values(self):
        """Test ApplicationState with custom values."""
        start_time = datetime.now()
        
        state = ApplicationState(
            running=False,
            shutdown_requested=True,
            measurement_count=5,
            start_time=start_time,
            last_measurement_time=start_time
        )
        
        assert state.running is False
        assert state.shutdown_requested is True
        assert state.measurement_count == 5
        assert state.start_time == start_time
        assert state.last_measurement_time == start_time


class TestMainApplication:
    """Test MainApplication class."""
    
    @pytest.fixture
    def app(self):
        """Create a MainApplication instance for testing."""
        with patch('main.signal.signal'):  # Prevent actual signal handler registration
            return MainApplication()
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration object."""
        config = Mock(spec=Configuration)
        config.target_ips = ["192.168.1.1"]
        config.timeout = 10
        config.output_dir = "data"
        config.scan_interval = 60
        config.verbose = False
        config.log_level = "INFO"
        config.ping_count = 10
        config.ping_size = 32
        config.ping_interval = 1.0
        config.iperf_server = "192.168.1.100"
        config.iperf_port = 5201
        config.iperf_duration = 10
        config.iperf_parallel = 1
        config.iperf_udp_bandwidth = "10M"
        config.file_server = "192.168.1.100"
        config.file_size_mb = 100
        config.file_protocol = "SMB"
        config.interface_name = "Wi-Fi"
        return config
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Create a mock measurement orchestrator."""
        orchestrator = Mock(spec=MeasurementOrchestrator)
        orchestrator.validate_prerequisites.return_value = (True, [])
        
        # Mock measurement result
        result = Mock(spec=OrchestrationResult)
        result.measurement_id = "test-measurement-id"
        result.execution_time = 5.0
        result.step_results = {MeasurementType.PING: Mock(value="completed")}
        result.errors = []
        result.warnings = []
        
        orchestrator.execute_measurement_cycle.return_value = result
        return orchestrator
    
    def test_initialization(self, app):
        """Test MainApplication initialization."""
        assert app.logger is None
        assert app.config_manager is None
        assert app.configuration is None
        assert app.measurement_orchestrator is None
        assert app.error_handler is not None
        assert isinstance(app.state, ApplicationState)
        assert app.state.running is True
    
    def test_setup_logging_basic(self, app):
        """Test basic logging setup."""
        app.setup_logging(log_level="INFO")
        
        assert app.logger is not None
        assert app.logger.name == "main"
    
    def test_setup_logging_with_file(self, app):
        """Test logging setup with file output."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            try:
                app.setup_logging(log_level="DEBUG", log_file=tmp_file.name, verbose=True)
                
                assert app.logger is not None
                assert os.path.exists(tmp_file.name)
            finally:
                os.unlink(tmp_file.name)
    
    def test_setup_logging_invalid_level(self, app):
        """Test logging setup with invalid level falls back to INFO."""
        app.setup_logging(log_level="INVALID")
        
        assert app.logger is not None
        # Should not raise an exception and use INFO level
    
    def test_create_argument_parser(self, app):
        """Test argument parser creation."""
        parser = app.create_argument_parser()
        
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.description is not None
        
        # Test parsing some basic arguments
        args = parser.parse_args(['--help'], exit=False)  # This would normally exit
    
    def test_parse_arguments_basic(self, app):
        """Test basic argument parsing."""
        args = app.parse_arguments(['--verbose'])
        
        assert args.verbose is True
        assert args.log_level == "INFO"  # default
        assert args.continuous is False  # default
    
    def test_parse_arguments_continuous_mode(self, app):
        """Test parsing continuous mode arguments."""
        args = app.parse_arguments(['--continuous', '-i', '300', '--max-measurements', '10'])
        
        assert args.continuous is True
        assert args.interval == 300
        assert args.max_measurements == 10
    
    def test_parse_arguments_test_selection(self, app):
        """Test parsing test selection arguments."""
        args = app.parse_arguments(['--tests', 'ping,iperf_tcp', '--timeout', '30'])
        
        assert args.tests == 'ping,iperf_tcp'
        assert args.timeout == 30
    
    def test_parse_arguments_validation_modes(self, app):
        """Test parsing validation mode arguments."""
        args = app.parse_arguments(['--dry-run', '--validate-config', '--check-prerequisites'])
        
        assert args.dry_run is True
        assert args.validate_config is True
        assert args.check_prerequisites is True
    
    def test_parse_arguments_create_config(self, app):
        """Test parsing create config argument."""
        args = app.parse_arguments(['--create-config', '-c', 'custom.ini'])
        
        assert args.create_config is True
        assert args.config == 'custom.ini'
    
    @patch('main.ConfigurationManager')
    def test_load_configuration_success(self, mock_config_manager_class, app, mock_config):
        """Test successful configuration loading."""
        # Setup mocks
        mock_config_manager = Mock()
        mock_config_manager.load_config.return_value = mock_config
        mock_config_manager.config_path = Path("config/config.ini")
        mock_config_manager_class.return_value = mock_config_manager
        
        # Setup logger
        app.logger = Mock()
        
        # Test
        result = app.load_configuration("test_config.ini")
        
        assert result == mock_config
        assert app.config_manager == mock_config_manager
        assert app.configuration == mock_config
        mock_config_manager_class.assert_called_once_with("test_config.ini")
        mock_config_manager.load_config.assert_called_once()
    
    @patch('main.ConfigurationManager')
    def test_load_configuration_file_not_found(self, mock_config_manager_class, app):
        """Test configuration loading with file not found."""
        # Setup mocks
        mock_config_manager = Mock()
        mock_config_manager.load_config.side_effect = FileNotFoundError("Config not found")
        mock_config_manager_class.return_value = mock_config_manager
        
        # Setup logger
        app.logger = Mock()
        
        # Test - should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            app.load_configuration()
        
        assert exc_info.value.code == 1
        app.logger.error.assert_called()
    
    def test_apply_cli_overrides(self, app, mock_config):
        """Test applying CLI overrides to configuration."""
        app.configuration = mock_config
        app.logger = Mock()
        
        # Create mock args
        args = Mock()
        args.timeout = 30
        args.output_dir = "custom_output"
        args.continuous = True
        args.interval = 120
        args.verbose = True
        args.log_level = "DEBUG"
        args.quiet = False
        
        # Test
        app.apply_cli_overrides(args)
        
        # Verify overrides were applied
        assert mock_config.timeout == 30
        assert mock_config.output_dir == "custom_output"
        assert mock_config.scan_interval == 120
        assert mock_config.verbose is True
        assert mock_config.log_level == "DEBUG"
    
    def test_apply_cli_overrides_quiet_mode(self, app, mock_config):
        """Test applying CLI overrides with quiet mode."""
        app.configuration = mock_config
        app.logger = Mock()
        
        # Create mock args with quiet mode
        args = Mock()
        args.timeout = None
        args.output_dir = None
        args.continuous = False
        args.verbose = False
        args.log_level = "INFO"
        args.quiet = True
        
        # Test
        app.apply_cli_overrides(args)
        
        # Verify quiet mode override
        assert mock_config.log_level == "WARNING"
    
    @patch('main.MeasurementOrchestrator')
    def test_initialize_orchestrator(self, mock_orchestrator_class, app, mock_config):
        """Test orchestrator initialization."""
        app.configuration = mock_config
        app.logger = Mock()
        
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator
        
        # Test
        app.initialize_orchestrator()
        
        assert app.measurement_orchestrator == mock_orchestrator
        mock_orchestrator_class.assert_called_once_with(mock_config)
    
    def test_initialize_orchestrator_no_config(self, app):
        """Test orchestrator initialization without configuration."""
        app.configuration = None
        
        with pytest.raises(RuntimeError, match="Configuration must be loaded"):
            app.initialize_orchestrator()
    
    def test_create_measurement_sequence_all_tests(self, app, mock_orchestrator):
        """Test creating measurement sequence with all tests."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Mock default sequence
        mock_sequence = Mock()
        mock_orchestrator.create_default_sequence.return_value = mock_sequence
        
        # Create args with no specific tests
        args = Mock()
        args.tests = None
        args.timeout = None
        
        # Test
        result = app.create_measurement_sequence(args)
        
        assert result == mock_sequence
        mock_orchestrator.create_default_sequence.assert_called_once()
    
    def test_create_measurement_sequence_specific_tests(self, app, mock_orchestrator):
        """Test creating measurement sequence with specific tests."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Mock custom sequence
        mock_sequence = Mock()
        mock_orchestrator.create_custom_sequence.return_value = mock_sequence
        
        # Create args with specific tests
        args = Mock()
        args.tests = "ping,iperf_tcp"
        args.timeout = 30
        
        # Test
        result = app.create_measurement_sequence(args)
        
        assert result == mock_sequence
        
        # Verify custom sequence was called with correct arguments
        call_args = mock_orchestrator.create_custom_sequence.call_args
        enabled_measurements = call_args[1]['enabled_measurements']
        timeout_overrides = call_args[1]['timeout_overrides']
        
        assert MeasurementType.PING in enabled_measurements
        assert MeasurementType.IPERF_TCP in enabled_measurements
        assert MeasurementType.WIFI_INFO not in enabled_measurements
        assert timeout_overrides[MeasurementType.PING] == 30.0
    
    def test_create_measurement_sequence_invalid_test(self, app, mock_orchestrator):
        """Test creating measurement sequence with invalid test name."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Create args with invalid test
        args = Mock()
        args.tests = "invalid_test,ping"
        args.timeout = None
        
        # Test
        result = app.create_measurement_sequence(args)
        
        # Should log warning about invalid test
        app.logger.warning.assert_called()
        
        # Should still create sequence with valid tests
        mock_orchestrator.create_custom_sequence.assert_called()
    
    def test_validate_prerequisites_success(self, app, mock_orchestrator):
        """Test successful prerequisites validation."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        mock_orchestrator.validate_prerequisites.return_value = (True, [])
        
        # Test
        result = app.validate_prerequisites()
        
        assert result is True
        app.logger.info.assert_called_with("All prerequisites validated successfully")
    
    def test_validate_prerequisites_failure(self, app, mock_orchestrator):
        """Test failed prerequisites validation."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        issues = ["WiFi not connected", "iPerf server unavailable"]
        mock_orchestrator.validate_prerequisites.return_value = (False, issues)
        
        # Test
        result = app.validate_prerequisites()
        
        assert result is False
        app.logger.error.assert_called()
        
        # Verify all issues were logged
        error_calls = [call[0][0] for call in app.logger.error.call_args_list]
        assert any("Prerequisites validation failed" in msg for msg in error_calls)
        assert any("WiFi not connected" in msg for msg in error_calls)
        assert any("iPerf server unavailable" in msg for msg in error_calls)
    
    def test_validate_prerequisites_no_orchestrator(self, app):
        """Test prerequisites validation without orchestrator."""
        app.measurement_orchestrator = None
        
        result = app.validate_prerequisites()
        
        assert result is False
    
    def test_run_single_measurement_success(self, app, mock_orchestrator):
        """Test successful single measurement."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Create mock sequence and result
        mock_sequence = Mock()
        mock_result = Mock()
        mock_result.measurement_id = "test-id"
        mock_result.execution_time = 5.0
        mock_result.step_results = {MeasurementType.PING: Mock(value="completed")}
        mock_result.errors = []
        mock_result.warnings = []
        
        mock_orchestrator.execute_measurement_cycle.return_value = mock_result
        
        # Test
        result = app.run_single_measurement(mock_sequence)
        
        assert result is True
        assert app.state.measurement_count == 1
        assert app.state.last_measurement_time is not None
        
        mock_orchestrator.execute_measurement_cycle.assert_called_once_with(mock_sequence)
        app.logger.info.assert_called()
    
    def test_run_single_measurement_with_errors(self, app, mock_orchestrator):
        """Test single measurement with errors."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Create mock sequence and result with errors
        mock_sequence = Mock()
        mock_result = Mock()
        mock_result.measurement_id = "test-id"
        mock_result.execution_time = 5.0
        mock_result.step_results = {MeasurementType.PING: Mock(value="failed")}
        mock_result.errors = ["Ping failed", "Network error"]
        mock_result.warnings = ["High latency detected"]
        
        mock_orchestrator.execute_measurement_cycle.return_value = mock_result
        
        # Test
        result = app.run_single_measurement(mock_sequence)
        
        assert result is False
        assert app.state.measurement_count == 1
        
        # Verify errors and warnings were logged
        error_calls = [call[0][0] for call in app.logger.error.call_args_list]
        warning_calls = [call[0][0] for call in app.logger.warning.call_args_list]
        
        assert any("Ping failed" in msg for msg in error_calls)
        assert any("Network error" in msg for msg in error_calls)
        assert any("High latency detected" in msg for msg in warning_calls)
    
    def test_run_single_measurement_exception(self, app, mock_orchestrator):
        """Test single measurement with exception."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        app.error_handler = Mock()
        
        # Mock exception
        mock_orchestrator.execute_measurement_cycle.side_effect = Exception("Test error")
        
        # Test
        result = app.run_single_measurement(Mock())
        
        assert result is False
        app.logger.error.assert_called()
        app.error_handler.handle_generic_error.assert_called()
    
    def test_run_single_measurement_no_orchestrator(self, app):
        """Test single measurement without orchestrator."""
        app.measurement_orchestrator = None
        
        result = app.run_single_measurement(Mock())
        
        assert result is False
    
    @patch('time.sleep')
    def test_run_continuous_measurements_basic(self, mock_sleep, app, mock_orchestrator):
        """Test basic continuous measurements."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Mock successful measurement
        app.run_single_measurement = Mock(return_value=True)
        
        # Set up state to run only one iteration
        app.state.running = True
        
        def stop_after_one(*args):
            app.state.running = False
        
        app.run_single_measurement.side_effect = stop_after_one
        
        # Test
        app.run_continuous_measurements(Mock(), interval=60, max_measurements=1)
        
        assert app.state.start_time is not None
        assert app.state.measurement_count == 0  # run_single_measurement is mocked
        app.run_single_measurement.assert_called_once()
    
    @patch('time.sleep')
    def test_run_continuous_measurements_max_reached(self, mock_sleep, app, mock_orchestrator):
        """Test continuous measurements with max limit reached."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Mock successful measurement
        app.run_single_measurement = Mock(return_value=True)
        
        # Set initial measurement count to max
        app.state.measurement_count = 5
        app.state.running = True
        
        # Test
        app.run_continuous_measurements(Mock(), interval=60, max_measurements=5)
        
        app.logger.info.assert_called()
        # Should not call run_single_measurement since we've reached max
        app.run_single_measurement.assert_not_called()
    
    @patch('time.sleep')
    def test_run_continuous_measurements_keyboard_interrupt(self, mock_sleep, app, mock_orchestrator):
        """Test continuous measurements with keyboard interrupt."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Mock KeyboardInterrupt on first measurement
        app.run_single_measurement = Mock(side_effect=KeyboardInterrupt())
        app.state.running = True
        
        # Test
        app.run_continuous_measurements(Mock(), interval=60)
        
        app.logger.info.assert_called_with("Continuous measurements interrupted by user")
    
    @patch('time.sleep')
    def test_run_continuous_measurements_with_sleep(self, mock_sleep, app, mock_orchestrator):
        """Test continuous measurements with proper sleep timing."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Mock measurement that takes 2 seconds
        def mock_measurement(*args):
            time.sleep(2)  # This won't actually sleep due to mock
            app.state.running = False  # Stop after first measurement
            return True
        
        app.run_single_measurement = Mock(side_effect=mock_measurement)
        app.state.running = True
        
        # Mock time.time to simulate measurement duration
        with patch('time.time', side_effect=[0, 2, 2]):  # start, after measurement, sleep check
            app.run_continuous_measurements(Mock(), interval=60)
        
        # Should sleep for remaining time (60 - 2 = 58 seconds)
        # Sleep is called in chunks, so verify it was called
        mock_sleep.assert_called()
    
    def test_signal_handler_first_signal(self, app):
        """Test signal handler on first signal."""
        app.logger = Mock()
        app.state.shutdown_requested = False
        
        # Test SIGINT
        app._signal_handler(signal.SIGINT, None)
        
        assert app.state.shutdown_requested is True
        assert app.state.running is False
        app.logger.info.assert_called()
    
    def test_signal_handler_second_signal(self, app):
        """Test signal handler on second signal."""
        app.logger = Mock()
        app.state.shutdown_requested = True  # Already requested
        
        # Test second signal - should force exit
        with pytest.raises(SystemExit) as exc_info:
            app._signal_handler(signal.SIGINT, None)
        
        assert exc_info.value.code == 1
        app.logger.warning.assert_called()
    
    def test_print_summary(self, app):
        """Test print summary functionality."""
        app.logger = Mock()
        
        # Set up state with some data
        app.state.start_time = datetime.now()
        app.state.measurement_count = 5
        app.state.last_measurement_time = datetime.now()
        
        # Test
        app._print_summary()
        
        # Verify all expected log calls were made
        info_calls = [call[0][0] for call in app.logger.info.call_args_list]
        
        assert any("Total execution time" in msg for msg in info_calls)
        assert any("Total measurements completed: 5" in msg for msg in info_calls)
        assert any("Last measurement:" in msg for msg in info_calls)
    
    def test_cleanup_with_orchestrator(self, app, mock_orchestrator):
        """Test cleanup with orchestrator."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Test
        app.cleanup()
        
        mock_orchestrator.cleanup.assert_called_once()
        app.logger.info.assert_called_with("Application cleanup completed")
    
    def test_cleanup_with_orchestrator_exception(self, app, mock_orchestrator):
        """Test cleanup with orchestrator exception."""
        app.measurement_orchestrator = mock_orchestrator
        app.logger = Mock()
        
        # Mock cleanup exception
        mock_orchestrator.cleanup.side_effect = Exception("Cleanup failed")
        
        # Test
        app.cleanup()
        
        app.logger.warning.assert_called()
        app.logger.info.assert_called_with("Application cleanup completed")
    
    def test_cleanup_no_orchestrator(self, app):
        """Test cleanup without orchestrator."""
        app.measurement_orchestrator = None
        app.logger = Mock()
        
        # Test - should not raise exception
        app.cleanup()
        
        app.logger.info.assert_called_with("Application cleanup completed")
    
    def test_handle_create_config_success(self, app):
        """Test successful config creation."""
        args = Mock()
        args.config = "custom_config.ini"
        
        with patch('main.ConfigurationManager') as mock_config_manager_class:
            mock_config_manager = Mock()
            mock_config_manager_class.return_value = mock_config_manager
            
            # Test
            result = app._handle_create_config(args)
            
            assert result == 0
            mock_config_manager.create_default_config.assert_called_once_with("custom_config.ini")
    
    def test_handle_create_config_default_path(self, app):
        """Test config creation with default path."""
        args = Mock()
        args.config = None
        
        with patch('main.ConfigurationManager') as mock_config_manager_class:
            mock_config_manager = Mock()
            mock_config_manager_class.return_value = mock_config_manager
            
            # Test
            result = app._handle_create_config(args)
            
            assert result == 0
            mock_config_manager.create_default_config.assert_called_once_with("config/config.ini")
    
    def test_handle_create_config_failure(self, app):
        """Test config creation failure."""
        args = Mock()
        args.config = "test_config.ini"
        app.logger = Mock()
        
        with patch('main.ConfigurationManager') as mock_config_manager_class:
            mock_config_manager = Mock()
            mock_config_manager.create_default_config.side_effect = Exception("Creation failed")
            mock_config_manager_class.return_value = mock_config_manager
            
            # Test
            result = app._handle_create_config(args)
            
            assert result == 1
    
    @patch.object(MainApplication, 'parse_arguments')
    @patch.object(MainApplication, 'setup_logging')
    @patch.object(MainApplication, 'load_configuration')
    @patch.object(MainApplication, 'apply_cli_overrides')
    @patch.object(MainApplication, 'initialize_orchestrator')
    @patch.object(MainApplication, 'validate_prerequisites')
    @patch.object(MainApplication, 'create_measurement_sequence')
    @patch.object(MainApplication, 'run_single_measurement')
    @patch.object(MainApplication, 'cleanup')
    def test_run_single_measurement_success_integration(self, mock_cleanup, mock_run_single, 
                                                        mock_create_sequence, mock_validate,
                                                        mock_init_orchestrator, mock_apply_overrides,
                                                        mock_load_config, mock_setup_logging,
                                                        mock_parse_args, app):
        """Test successful single measurement run integration."""
        # Setup mocks
        mock_args = Mock()
        mock_args.create_config = False
        mock_args.validate_config = False
        mock_args.check_prerequisites = False
        mock_args.dry_run = False
        mock_args.continuous = False
        mock_args.log_level = "INFO"
        mock_args.log_file = None
        mock_args.verbose = False
        mock_args.quiet = False
        
        mock_parse_args.return_value = mock_args
        mock_validate.return_value = True
        mock_run_single.return_value = True
        
        app.logger = Mock()
        
        # Test
        result = app.run()
        
        assert result == 0
        mock_setup_logging.assert_called_once()
        mock_load_config.assert_called_once()
        mock_apply_overrides.assert_called_once()
        mock_init_orchestrator.assert_called_once()
        mock_validate.assert_called()
        mock_create_sequence.assert_called_once()
        mock_run_single.assert_called_once()
        mock_cleanup.assert_called_once()
    
    @patch.object(MainApplication, 'parse_arguments')
    @patch.object(MainApplication, 'setup_logging')
    @patch.object(MainApplication, '_handle_create_config')
    @patch.object(MainApplication, 'cleanup')
    def test_run_create_config_mode(self, mock_cleanup, mock_handle_create,
                                   mock_setup_logging, mock_parse_args, app):
        """Test run in create config mode."""
        # Setup mocks
        mock_args = Mock()
        mock_args.create_config = True
        mock_args.log_level = "INFO"
        mock_args.log_file = None
        mock_args.verbose = False
        mock_args.quiet = False
        
        mock_parse_args.return_value = mock_args
        mock_handle_create.return_value = 0
        
        app.logger = Mock()
        
        # Test
        result = app.run()
        
        assert result == 0
        mock_handle_create.assert_called_once()
        mock_cleanup.assert_called_once()
    
    @patch.object(MainApplication, 'parse_arguments')
    @patch.object(MainApplication, 'setup_logging')
    def test_run_keyboard_interrupt(self, mock_setup_logging, mock_parse_args, app):
        """Test run with KeyboardInterrupt."""
        # Setup mocks
        mock_parse_args.side_effect = KeyboardInterrupt()
        app.logger = Mock()
        
        # Test
        result = app.run()
        
        assert result == 0  # KeyboardInterrupt should return 0
    
    @patch.object(MainApplication, 'parse_arguments')
    @patch.object(MainApplication, 'setup_logging')
    def test_run_unexpected_exception(self, mock_setup_logging, mock_parse_args, app):
        """Test run with unexpected exception."""
        # Setup mocks
        mock_parse_args.side_effect = Exception("Unexpected error")
        app.logger = Mock()
        
        # Test
        result = app.run()
        
        assert result == 1
        app.logger.critical.assert_called()


class TestMainFunction:
    """Test main function."""
    
    @patch('main.MainApplication')
    def test_main_function(self, mock_app_class):
        """Test main function creates app and calls run."""
        mock_app = Mock()
        mock_app.run.return_value = 0
        mock_app_class.return_value = mock_app
        
        from main import main
        
        result = main()
        
        assert result == 0
        mock_app_class.assert_called_once()
        mock_app.run.assert_called_once()
    
    @patch('main.MainApplication')
    def test_main_function_error(self, mock_app_class):
        """Test main function with error return code."""
        mock_app = Mock()
        mock_app.run.return_value = 1
        mock_app_class.return_value = mock_app
        
        from main import main
        
        result = main()
        
        assert result == 1


if __name__ == "__main__":
    pytest.main([__file__])