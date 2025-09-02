"""Unit tests for MeasurementOrchestrator."""

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from pathlib import Path

# Import the classes we're testing
from src.measurement_orchestrator import (
    MeasurementOrchestrator, MeasurementStep, MeasurementSequence, 
    MeasurementStatus, OrchestrationResult
)
from src.models import (
    Configuration, MeasurementResult, WiFiInfo, PingResult, 
    IperfTcpResult, IperfUdpResult, FileTransferResult, MeasurementType
)
from src.wifi_collector import WiFiInfoCollector
from src.network_tester import NetworkTester, IperfServerUnavailableError
from src.file_transfer_tester import FileTransferTester, FileTransferError
from src.data_export_manager import DataExportManager
from src.error_handler import ErrorHandler


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = Configuration()
    config.interface_name = "wlan0"
    config.target_ips = ["192.168.1.1", "8.8.8.8"]
    config.timeout = 10
    config.ping_count = 4
    config.ping_size = 32
    config.ping_interval = 1.0
    config.iperf_server = "192.168.1.100"
    config.iperf_port = 5201
    config.iperf_duration = 10
    config.iperf_parallel = 1
    config.iperf_udp_bandwidth = "10M"
    config.file_server = "192.168.1.100"
    config.file_size_mb = 10
    config.file_protocol = "SMB"
    config.output_dir = "test_data"
    return config


@pytest.fixture
def mock_wifi_collector():
    """Create a mock WiFi collector."""
    collector = Mock(spec=WiFiInfoCollector)
    collector.is_connected.return_value = True
    collector.collect_wifi_info.return_value = WiFiInfo(
        ssid="TestNetwork",
        rssi=-50,
        link_quality=80,
        tx_rate=150.0,
        rx_rate=150.0,
        channel=6,
        frequency=2.437,
        interface_name="wlan0",
        mac_address="00:11:22:33:44:55"
    )
    return collector


@pytest.fixture
def mock_network_tester():
    """Create a mock network tester."""
    tester = Mock(spec=NetworkTester)
    tester.is_host_reachable.return_value = True
    tester._check_iperf_server_availability.return_value = None
    tester.ping.return_value = PingResult(
        target_ip="192.168.1.1",
        packets_sent=4,
        packets_received=4,
        packet_loss=0.0,
        min_rtt=10.0,
        max_rtt=20.0,
        avg_rtt=15.0,
        std_dev_rtt=2.5
    )
    tester.iperf_tcp_bidirectional.return_value = IperfTcpResult(
        server_ip="192.168.1.100",
        server_port=5201,
        duration=10,
        bytes_sent=10000000,
        bytes_received=10000000,
        throughput_upload=8.0,
        throughput_download=8.5,
        retransmits=0
    )
    tester.iperf_udp_test.return_value = IperfUdpResult(
        server_ip="192.168.1.100",
        server_port=5201,
        duration=10,
        bytes_sent=10000000,
        packets_sent=7000,
        packets_lost=10,
        packet_loss=0.14,
        jitter=2.5,
        throughput=7.5
    )
    return tester


@pytest.fixture
def mock_file_transfer_tester():
    """Create a mock file transfer tester."""
    tester = Mock(spec=FileTransferTester)
    tester.cleanup.return_value = None
    tester.test_smb_transfer.return_value = FileTransferResult(
        server_address="192.168.1.100",
        file_size=10485760,
        transfer_time=5.2,
        transfer_speed=2.0,
        protocol="SMB",
        direction="download"
    )
    return tester


@pytest.fixture
def mock_data_export_manager():
    """Create a mock data export manager."""
    manager = Mock(spec=DataExportManager)
    manager.append_measurement.return_value = Path("test_data/measurements.csv")
    return manager


@pytest.fixture
def mock_error_handler():
    """Create a mock error handler."""
    handler = Mock(spec=ErrorHandler)
    handler.get_error_statistics.return_value = {
        'total_errors': 0,
        'errors_by_type': {},
        'recent_errors': 0,
        'history_size': 0
    }
    return handler


@pytest.fixture
def orchestrator(mock_config, mock_error_handler, mock_wifi_collector, 
                mock_network_tester, mock_file_transfer_tester, mock_data_export_manager):
    """Create a MeasurementOrchestrator instance with mocked dependencies."""
    return MeasurementOrchestrator(
        config=mock_config,
        error_handler=mock_error_handler,
        wifi_collector=mock_wifi_collector,
        network_tester=mock_network_tester,
        file_transfer_tester=mock_file_transfer_tester,
        data_export_manager=mock_data_export_manager
    )


class TestMeasurementOrchestrator:
    """Test cases for MeasurementOrchestrator."""

    def test_initialization(self, mock_config):
        """Test orchestrator initialization."""
        orchestrator = MeasurementOrchestrator(mock_config)
        
        assert orchestrator.config == mock_config
        assert orchestrator.wifi_collector is not None
        assert orchestrator.network_tester is not None
        assert orchestrator.file_transfer_tester is not None
        assert orchestrator.data_export_manager is not None
        assert orchestrator.error_handler is not None
        assert orchestrator._current_measurement_id is None

    def test_create_default_sequence(self, orchestrator):
        """Test default measurement sequence creation."""
        sequence = orchestrator.create_default_sequence()
        
        assert isinstance(sequence, MeasurementSequence)
        assert len(sequence.steps) == 5
        assert sequence.validate_prerequisites is True
        assert sequence.continue_on_failure is True
        assert sequence.export_results is True
        assert sequence.cleanup_on_exit is True
        
        # Check all measurement types are included
        measurement_types = [step.measurement_type for step in sequence.steps]
        expected_types = [
            MeasurementType.WIFI_INFO,
            MeasurementType.PING,
            MeasurementType.IPERF_TCP,
            MeasurementType.IPERF_UDP,
            MeasurementType.FILE_TRANSFER
        ]
        
        for expected_type in expected_types:
            assert expected_type in measurement_types

    def test_validate_prerequisites_success(self, orchestrator):
        """Test successful prerequisite validation."""
        is_valid, issues = orchestrator.validate_prerequisites()
        
        assert is_valid is True
        assert len(issues) == 0

    def test_validate_prerequisites_wifi_not_connected(self, orchestrator, mock_wifi_collector):
        """Test prerequisite validation with WiFi not connected."""
        mock_wifi_collector.is_connected.return_value = False
        
        is_valid, issues = orchestrator.validate_prerequisites()
        
        assert is_valid is False
        assert len(issues) >= 1
        assert any("WiFi interface is not connected" in issue for issue in issues)

    def test_validate_prerequisites_target_unreachable(self, orchestrator, mock_network_tester):
        """Test prerequisite validation with unreachable target."""
        mock_network_tester.is_host_reachable.return_value = False
        
        is_valid, issues = orchestrator.validate_prerequisites()
        
        assert is_valid is False
        assert len(issues) >= 1
        assert any("not reachable" in issue for issue in issues)

    def test_validate_prerequisites_iperf_server_unavailable(self, orchestrator, mock_network_tester):
        """Test prerequisite validation with iPerf server unavailable."""
        mock_network_tester._check_iperf_server_availability.side_effect = IperfServerUnavailableError("Server unavailable")
        
        is_valid, issues = orchestrator.validate_prerequisites()
        
        assert is_valid is False
        assert len(issues) >= 1
        assert any("iPerf3 server unavailable" in issue for issue in issues)

    def test_execute_measurement_cycle_success(self, orchestrator):
        """Test successful measurement cycle execution."""
        # Create a simple sequence with just WiFi info
        sequence = MeasurementSequence(
            steps=[
                MeasurementStep(
                    measurement_type=MeasurementType.WIFI_INFO,
                    enabled=True,
                    timeout=10.0
                )
            ],
            validate_prerequisites=True,
            continue_on_failure=True,
            export_results=True,
            cleanup_on_exit=True
        )
        
        result = orchestrator.execute_measurement_cycle(sequence)
        
        assert isinstance(result, OrchestrationResult)
        assert result.measurement_id is not None
        assert result.measurement_result.wifi_info is not None
        assert result.step_results[MeasurementType.WIFI_INFO] == MeasurementStatus.COMPLETED
        assert result.execution_time > 0
        assert len(result.errors) == 0

    def test_execute_measurement_cycle_with_custom_id(self, orchestrator):
        """Test measurement cycle with custom measurement ID."""
        custom_id = "test-measurement-123"
        sequence = MeasurementSequence(
            steps=[
                MeasurementStep(
                    measurement_type=MeasurementType.WIFI_INFO,
                    enabled=True
                )
            ]
        )
        
        result = orchestrator.execute_measurement_cycle(sequence, measurement_id=custom_id)
        
        assert result.measurement_id == custom_id
        assert result.measurement_result.measurement_id == custom_id

    def test_execute_measurement_cycle_prerequisite_failure_no_continue(self, orchestrator, mock_wifi_collector):
        """Test measurement cycle with prerequisite failure and no continue on failure."""
        mock_wifi_collector.is_connected.return_value = False
        
        sequence = MeasurementSequence(
            steps=[
                MeasurementStep(
                    measurement_type=MeasurementType.WIFI_INFO,
                    enabled=True
                )
            ],
            validate_prerequisites=True,
            continue_on_failure=False
        )
        
        result = orchestrator.execute_measurement_cycle(sequence)
        
        assert len(result.errors) > 0
        assert len(result.step_results) == 0  # No steps executed

    def test_execute_measurement_cycle_step_failure_with_skip(self, orchestrator, mock_wifi_collector):
        """Test measurement cycle with step failure but skip on error."""
        mock_wifi_collector.collect_wifi_info.side_effect = Exception("WiFi collection failed")
        
        sequence = MeasurementSequence(
            steps=[
                MeasurementStep(
                    measurement_type=MeasurementType.WIFI_INFO,
                    enabled=True,
                    skip_on_error=True,
                    retry_attempts=1
                )
            ],
            validate_prerequisites=False,
            continue_on_failure=True
        )
        
        result = orchestrator.execute_measurement_cycle(sequence)
        
        assert result.step_results[MeasurementType.WIFI_INFO] == MeasurementStatus.FAILED
        assert len(result.errors) > 0

    def test_execute_measurement_cycle_with_retry(self, orchestrator, mock_wifi_collector):
        """Test measurement cycle with retry on failure."""
        # First call fails, second succeeds
        mock_wifi_collector.collect_wifi_info.side_effect = [
            Exception("First attempt fails"), 
            WiFiInfo(
                ssid="TestNetwork",
                rssi=-50,
                link_quality=80,
                tx_rate=150.0,
                rx_rate=150.0,
                channel=6,
                frequency=2.437,
                interface_name="wlan0",
                mac_address="00:11:22:33:44:55"
            )
        ]
        
        sequence = MeasurementSequence(
            steps=[
                MeasurementStep(
                    measurement_type=MeasurementType.WIFI_INFO,
                    enabled=True,
                    retry_attempts=2
                )
            ],
            validate_prerequisites=False
        )
        
        result = orchestrator.execute_measurement_cycle(sequence)
        
        assert result.step_results[MeasurementType.WIFI_INFO] == MeasurementStatus.COMPLETED
        assert result.measurement_result.wifi_info is not None

    def test_execute_measurement_step_wifi_info(self, orchestrator):
        """Test WiFi info measurement step execution."""
        step = MeasurementStep(measurement_type=MeasurementType.WIFI_INFO)
        
        result = orchestrator._execute_measurement_step(step)
        
        assert isinstance(result, WiFiInfo)
        assert result.ssid == "TestNetwork"

    def test_execute_measurement_step_ping(self, orchestrator):
        """Test ping measurement step execution."""
        step = MeasurementStep(
            measurement_type=MeasurementType.PING,
            parameters={
                'targets': ['192.168.1.1'],
                'count': 4,
                'size': 32,
                'interval': 1.0
            }
        )
        
        result = orchestrator._execute_measurement_step(step)
        
        assert isinstance(result, PingResult)
        assert result.target_ip == "192.168.1.1"

    def test_execute_measurement_step_iperf_tcp(self, orchestrator):
        """Test iPerf TCP measurement step execution."""
        step = MeasurementStep(
            measurement_type=MeasurementType.IPERF_TCP,
            parameters={
                'server_ip': '192.168.1.100',
                'server_port': 5201,
                'duration': 10,
                'parallel': 1
            }
        )
        
        result = orchestrator._execute_measurement_step(step)
        
        assert isinstance(result, IperfTcpResult)
        assert result.server_ip == "192.168.1.100"

    def test_execute_measurement_step_iperf_udp(self, orchestrator):
        """Test iPerf UDP measurement step execution."""
        step = MeasurementStep(
            measurement_type=MeasurementType.IPERF_UDP,
            parameters={
                'server_ip': '192.168.1.100',
                'server_port': 5201,
                'duration': 10,
                'bandwidth': '10M'
            }
        )
        
        result = orchestrator._execute_measurement_step(step)
        
        assert isinstance(result, IperfUdpResult)
        assert result.server_ip == "192.168.1.100"

    def test_execute_measurement_step_file_transfer_smb(self, orchestrator):
        """Test SMB file transfer measurement step execution."""
        step = MeasurementStep(
            measurement_type=MeasurementType.FILE_TRANSFER,
            parameters={
                'server_address': '192.168.1.100',
                'file_size_mb': 10,
                'protocol': 'smb',
                'direction': 'download',
                'share_name': 'test_share'
            }
        )
        
        result = orchestrator._execute_measurement_step(step)
        
        assert isinstance(result, FileTransferResult)
        assert result.server_address == "192.168.1.100"
        assert result.protocol == "SMB"

    def test_execute_measurement_step_invalid_type(self, orchestrator):
        """Test execution with invalid measurement type."""
        step = MeasurementStep(measurement_type="invalid_type")
        
        with pytest.raises(ValueError, match="Unknown measurement type"):
            orchestrator._execute_measurement_step(step)

    def test_update_measurement_result(self, orchestrator):
        """Test measurement result updating."""
        measurement_result = MeasurementResult(measurement_id="test-123")
        
        wifi_info = WiFiInfo(
            ssid="TestNetwork",
            rssi=-50,
            link_quality=80,
            tx_rate=150.0,
            rx_rate=150.0,
            channel=6,
            frequency=2.437,
            interface_name="wlan0",
            mac_address="00:11:22:33:44:55"
        )
        
        orchestrator._update_measurement_result(
            measurement_result, 
            MeasurementType.WIFI_INFO, 
            wifi_info
        )
        
        assert measurement_result.wifi_info == wifi_info

    def test_register_callback(self, orchestrator):
        """Test callback registration."""
        callback_called = False
        
        def test_callback(*args, **kwargs):
            nonlocal callback_called
            callback_called = True
        
        orchestrator.register_callback('before_measurement', test_callback)
        
        # Execute callbacks should call our test callback
        orchestrator._execute_callbacks('before_measurement')
        
        assert callback_called is True

    def test_register_callback_invalid_event(self, orchestrator):
        """Test callback registration with invalid event."""
        def test_callback():
            pass
        
        with pytest.raises(ValueError, match="Unknown event"):
            orchestrator.register_callback('invalid_event', test_callback)

    def test_get_supported_protocols(self, orchestrator):
        """Test getting supported protocols."""
        protocols = orchestrator.get_supported_protocols()
        
        assert isinstance(protocols, list)
        assert 'http' in protocols
        assert 'https' in protocols
        assert 'ftp' in protocols
        # SMB support depends on pysmb availability

    def test_create_custom_sequence(self, orchestrator):
        """Test creating custom measurement sequence."""
        enabled_measurements = {MeasurementType.WIFI_INFO, MeasurementType.PING}
        timeout_overrides = {MeasurementType.PING: 30.0}
        parameter_overrides = {
            MeasurementType.PING: {'count': 10}
        }
        
        sequence = orchestrator.create_custom_sequence(
            enabled_measurements=enabled_measurements,
            timeout_overrides=timeout_overrides,
            parameter_overrides=parameter_overrides
        )
        
        assert len(sequence.steps) == 2
        
        ping_step = next(
            step for step in sequence.steps 
            if step.measurement_type == MeasurementType.PING
        )
        assert ping_step.timeout == 30.0
        assert ping_step.parameters['count'] == 10

    def test_get_measurement_status(self, orchestrator):
        """Test getting measurement status."""
        status = orchestrator.get_measurement_status()
        
        assert isinstance(status, dict)
        assert 'current_measurement_id' in status
        assert 'step_results' in status
        assert 'error_statistics' in status
        assert 'supported_protocols' in status
        assert 'wifi_connected' in status

    def test_cleanup(self, orchestrator, mock_file_transfer_tester):
        """Test orchestrator cleanup."""
        orchestrator.cleanup()
        
        mock_file_transfer_tester.cleanup.assert_called_once()

    def test_cleanup_with_exception(self, orchestrator, mock_file_transfer_tester):
        """Test orchestrator cleanup with exception."""
        mock_file_transfer_tester.cleanup.side_effect = Exception("Cleanup failed")
        
        # Should not raise exception
        orchestrator.cleanup()
        
        mock_file_transfer_tester.cleanup.assert_called_once()

    def test_full_measurement_cycle_integration(self, orchestrator):
        """Test full measurement cycle with all components."""
        sequence = orchestrator.create_default_sequence()
        
        result = orchestrator.execute_measurement_cycle(sequence)
        
        assert isinstance(result, OrchestrationResult)
        assert result.measurement_result.wifi_info is not None
        assert result.measurement_result.ping_result is not None
        assert result.measurement_result.iperf_tcp_result is not None
        assert result.measurement_result.iperf_udp_result is not None
        assert result.measurement_result.file_transfer_result is not None
        
        # Check all steps completed
        for measurement_type in [
            MeasurementType.WIFI_INFO,
            MeasurementType.PING,
            MeasurementType.IPERF_TCP,
            MeasurementType.IPERF_UDP,
            MeasurementType.FILE_TRANSFER
        ]:
            assert result.step_results[measurement_type] == MeasurementStatus.COMPLETED

    def test_measurement_with_export_failure(self, orchestrator, mock_data_export_manager):
        """Test measurement cycle with export failure."""
        mock_data_export_manager.append_measurement.side_effect = Exception("Export failed")
        
        sequence = MeasurementSequence(
            steps=[
                MeasurementStep(
                    measurement_type=MeasurementType.WIFI_INFO,
                    enabled=True
                )
            ],
            export_results=True
        )
        
        result = orchestrator.execute_measurement_cycle(sequence)
        
        assert len(result.errors) > 0
        assert any("export" in error.lower() for error in result.errors)

    def test_measurement_with_disabled_step(self, orchestrator):
        """Test measurement cycle with disabled step."""
        sequence = MeasurementSequence(
            steps=[
                MeasurementStep(
                    measurement_type=MeasurementType.WIFI_INFO,
                    enabled=False
                )
            ]
        )
        
        result = orchestrator.execute_measurement_cycle(sequence)
        
        assert result.step_results[MeasurementType.WIFI_INFO] == MeasurementStatus.SKIPPED

    def test_callback_execution_during_cycle(self, orchestrator):
        """Test that callbacks are executed during measurement cycle."""
        before_called = False
        after_called = False
        step_before_called = False
        step_after_called = False
        
        def before_callback(*args):
            nonlocal before_called
            before_called = True
        
        def after_callback(*args):
            nonlocal after_called
            after_called = True
        
        def step_before_callback(*args):
            nonlocal step_before_called
            step_before_called = True
        
        def step_after_callback(*args):
            nonlocal step_after_called
            step_after_called = True
        
        orchestrator.register_callback('before_measurement', before_callback)
        orchestrator.register_callback('after_measurement', after_callback)
        orchestrator.register_callback('before_step', step_before_callback)
        orchestrator.register_callback('after_step', step_after_callback)
        
        sequence = MeasurementSequence(
            steps=[
                MeasurementStep(
                    measurement_type=MeasurementType.WIFI_INFO,
                    enabled=True
                )
            ]
        )
        
        orchestrator.execute_measurement_cycle(sequence)
        
        assert before_called is True
        assert after_called is True
        assert step_before_called is True
        assert step_after_called is True


class TestMeasurementStep:
    """Test cases for MeasurementStep."""

    def test_measurement_step_creation(self):
        """Test MeasurementStep creation."""
        step = MeasurementStep(
            measurement_type=MeasurementType.PING,
            enabled=True,
            timeout=30.0,
            skip_on_error=True,
            retry_attempts=3,
            parameters={'count': 10}
        )
        
        assert step.measurement_type == MeasurementType.PING
        assert step.enabled is True
        assert step.timeout == 30.0
        assert step.skip_on_error is True
        assert step.retry_attempts == 3
        assert step.parameters['count'] == 10

    def test_measurement_step_defaults(self):
        """Test MeasurementStep default values."""
        step = MeasurementStep(measurement_type=MeasurementType.WIFI_INFO)
        
        assert step.enabled is True
        assert step.timeout is None
        assert step.skip_on_error is False
        assert step.retry_attempts == 1
        assert step.parameters == {}


class TestMeasurementSequence:
    """Test cases for MeasurementSequence."""

    def test_measurement_sequence_creation(self):
        """Test MeasurementSequence creation."""
        steps = [
            MeasurementStep(measurement_type=MeasurementType.WIFI_INFO),
            MeasurementStep(measurement_type=MeasurementType.PING)
        ]
        
        sequence = MeasurementSequence(
            steps=steps,
            validate_prerequisites=False,
            continue_on_failure=False,
            export_results=False,
            cleanup_on_exit=False
        )
        
        assert len(sequence.steps) == 2
        assert sequence.validate_prerequisites is False
        assert sequence.continue_on_failure is False
        assert sequence.export_results is False
        assert sequence.cleanup_on_exit is False

    def test_measurement_sequence_defaults(self):
        """Test MeasurementSequence default values."""
        sequence = MeasurementSequence()
        
        assert sequence.steps == []
        assert sequence.validate_prerequisites is True
        assert sequence.continue_on_failure is False
        assert sequence.export_results is True
        assert sequence.cleanup_on_exit is True


class TestOrchestrationResult:
    """Test cases for OrchestrationResult."""

    def test_orchestration_result_creation(self):
        """Test OrchestrationResult creation."""
        measurement_result = MeasurementResult(measurement_id="test-123")
        step_results = {MeasurementType.WIFI_INFO: MeasurementStatus.COMPLETED}
        
        result = OrchestrationResult(
            measurement_id="test-123",
            measurement_result=measurement_result,
            step_results=step_results,
            execution_time=45.2,
            errors=["Error 1"],
            warnings=["Warning 1"]
        )
        
        assert result.measurement_id == "test-123"
        assert result.measurement_result == measurement_result
        assert result.step_results == step_results
        assert result.execution_time == 45.2
        assert result.errors == ["Error 1"]
        assert result.warnings == ["Warning 1"]


if __name__ == "__main__":
    pytest.main([__file__])