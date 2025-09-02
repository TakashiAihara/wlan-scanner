"""Measurement orchestrator for comprehensive network performance testing."""

import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, Set
from enum import Enum
from dataclasses import dataclass, field

from .models import (
    MeasurementResult, WiFiInfo, PingResult, IperfTcpResult, 
    IperfUdpResult, FileTransferResult, Configuration, MeasurementType
)
from .wifi_collector import WiFiInfoCollector
from .network_tester import NetworkTester, IperfServerUnavailableError, IperfConnectionError
from .file_transfer_tester import FileTransferTester, FileTransferError, FileTransferConnectionError
from .data_export_manager import DataExportManager
from .error_handler import ErrorHandler, ErrorType, ErrorSeverity, get_error_handler


class MeasurementStatus(Enum):
    """Status of individual measurements."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class MeasurementStep:
    """Individual measurement step configuration."""
    measurement_type: MeasurementType
    enabled: bool = True
    timeout: Optional[float] = None
    skip_on_error: bool = False
    retry_attempts: int = 1
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class MeasurementSequence:
    """Configuration for a measurement sequence."""
    steps: List[MeasurementStep] = field(default_factory=list)
    validate_prerequisites: bool = True
    continue_on_failure: bool = False
    export_results: bool = True
    cleanup_on_exit: bool = True


@dataclass
class OrchestrationResult:
    """Result of orchestrated measurement sequence."""
    measurement_id: str
    measurement_result: MeasurementResult
    step_results: Dict[MeasurementType, MeasurementStatus]
    execution_time: float
    errors: List[str]
    warnings: List[str]


class MeasurementOrchestrator:
    """
    Orchestrates comprehensive network performance measurements.
    
    This class coordinates WiFi information collection, network testing (ping, iPerf3),
    file transfer testing, and data export operations. It provides prerequisite validation,
    error handling, configurable measurement sequences, and comprehensive logging.
    """

    def __init__(self, 
                 config: Configuration,
                 error_handler: Optional[ErrorHandler] = None,
                 wifi_collector: Optional[WiFiInfoCollector] = None,
                 network_tester: Optional[NetworkTester] = None,
                 file_transfer_tester: Optional[FileTransferTester] = None,
                 data_export_manager: Optional[DataExportManager] = None):
        """
        Initialize the measurement orchestrator.
        
        Args:
            config: Application configuration
            error_handler: Error handler instance (creates default if None)
            wifi_collector: WiFi info collector (creates default if None)
            network_tester: Network tester instance (creates default if None)
            file_transfer_tester: File transfer tester (creates default if None)
            data_export_manager: Data export manager (creates default if None)
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.error_handler = error_handler or get_error_handler()
        
        # Initialize components
        self.wifi_collector = wifi_collector or WiFiInfoCollector(config.interface_name)
        self.network_tester = network_tester or NetworkTester(timeout=config.timeout)
        self.file_transfer_tester = file_transfer_tester or FileTransferTester(timeout=config.timeout)
        self.data_export_manager = data_export_manager or DataExportManager(config.output_dir)
        
        # State tracking
        self._current_measurement_id: Optional[str] = None
        self._step_results: Dict[MeasurementType, MeasurementStatus] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            'before_measurement': [],
            'after_measurement': [],
            'before_step': [],
            'after_step': [],
            'on_error': []
        }
        
    def create_default_sequence(self) -> MeasurementSequence:
        """
        Create a default measurement sequence with all available tests.
        
        Returns:
            MeasurementSequence with default configuration
        """
        steps = [
            MeasurementStep(
                measurement_type=MeasurementType.WIFI_INFO,
                enabled=True,
                timeout=10.0,
                skip_on_error=False,
                retry_attempts=2
            ),
            MeasurementStep(
                measurement_type=MeasurementType.PING,
                enabled=True,
                timeout=30.0,
                skip_on_error=True,
                retry_attempts=1,
                parameters={
                    'targets': self.config.target_ips,
                    'count': self.config.ping_count,
                    'size': self.config.ping_size,
                    'interval': self.config.ping_interval
                }
            ),
            MeasurementStep(
                measurement_type=MeasurementType.IPERF_TCP,
                enabled=True,
                timeout=self.config.iperf_duration + 30,
                skip_on_error=True,
                retry_attempts=1,
                parameters={
                    'server_ip': self.config.iperf_server,
                    'server_port': self.config.iperf_port,
                    'duration': self.config.iperf_duration,
                    'parallel': self.config.iperf_parallel
                }
            ),
            MeasurementStep(
                measurement_type=MeasurementType.IPERF_UDP,
                enabled=True,
                timeout=self.config.iperf_duration + 30,
                skip_on_error=True,
                retry_attempts=1,
                parameters={
                    'server_ip': self.config.iperf_server,
                    'server_port': self.config.iperf_port,
                    'duration': self.config.iperf_duration,
                    'bandwidth': self.config.iperf_udp_bandwidth
                }
            ),
            MeasurementStep(
                measurement_type=MeasurementType.FILE_TRANSFER,
                enabled=True,
                timeout=300.0,  # 5 minutes for file transfer
                skip_on_error=True,
                retry_attempts=1,
                parameters={
                    'server_address': self.config.file_server,
                    'file_size_mb': self.config.file_size_mb,
                    'protocol': self.config.file_protocol.lower(),
                    'direction': 'download'
                }
            )
        ]
        
        return MeasurementSequence(
            steps=steps,
            validate_prerequisites=True,
            continue_on_failure=True,
            export_results=True,
            cleanup_on_exit=True
        )
    
    def validate_prerequisites(self) -> tuple[bool, List[str]]:
        """
        Validate prerequisites for measurement execution.
        
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        try:
            # Check WiFi connectivity
            if not self.wifi_collector.is_connected():
                issues.append("WiFi interface is not connected")
            
            # Check primary target connectivity
            if self.config.target_ips:
                primary_target = self.config.target_ips[0]
                if not self.network_tester.is_host_reachable(primary_target, count=2, timeout=5):
                    issues.append(f"Primary target {primary_target} is not reachable")
            
            # Check iPerf3 server availability
            try:
                self.network_tester._check_iperf_server_availability(
                    self.config.iperf_server,
                    self.config.iperf_port,
                    timeout=5.0
                )
            except IperfServerUnavailableError as e:
                issues.append(f"iPerf3 server unavailable: {e}")
            
            # Validate configuration
            try:
                self.config.validate()
            except ValueError as e:
                issues.append(f"Configuration validation failed: {e}")
                
        except Exception as e:
            self.error_handler.handle_generic_error(
                e, ErrorType.MEASUREMENT_ERROR, 
                "measurement_orchestrator", "validate_prerequisites"
            )
            issues.append(f"Unexpected error during validation: {e}")
        
        return len(issues) == 0, issues
    
    def execute_measurement_cycle(self, 
                                  sequence: Optional[MeasurementSequence] = None,
                                  measurement_id: Optional[str] = None) -> OrchestrationResult:
        """
        Execute a complete measurement cycle.
        
        Args:
            sequence: Measurement sequence configuration (uses default if None)
            measurement_id: Custom measurement ID (generates if None)
            
        Returns:
            OrchestrationResult with measurement data and execution details
        """
        if sequence is None:
            sequence = self.create_default_sequence()
        
        if measurement_id is None:
            measurement_id = str(uuid.uuid4())
        
        start_time = datetime.now()
        self._current_measurement_id = measurement_id
        self._step_results = {}
        
        # Initialize measurement result
        measurement_result = MeasurementResult(
            measurement_id=measurement_id,
            timestamp=start_time
        )
        
        errors = []
        warnings = []
        
        self.logger.info(f"Starting measurement cycle {measurement_id}")
        
        # Execute callbacks
        self._execute_callbacks('before_measurement', measurement_id)
        
        try:
            # Validate prerequisites if required
            if sequence.validate_prerequisites:
                is_valid, issues = self.validate_prerequisites()
                if not is_valid:
                    error_msg = f"Prerequisites validation failed: {issues}"
                    self.logger.error(error_msg)
                    errors.extend(issues)
                    
                    if not sequence.continue_on_failure:
                        return OrchestrationResult(
                            measurement_id=measurement_id,
                            measurement_result=measurement_result,
                            step_results=self._step_results,
                            execution_time=0.0,
                            errors=errors,
                            warnings=warnings
                        )
                    else:
                        warnings.extend(issues)
            
            # Execute measurement steps
            for step in sequence.steps:
                if not step.enabled:
                    self._step_results[step.measurement_type] = MeasurementStatus.SKIPPED
                    continue
                
                self.logger.info(f"Executing {step.measurement_type.value} measurement")
                self._step_results[step.measurement_type] = MeasurementStatus.IN_PROGRESS
                
                # Execute callbacks
                self._execute_callbacks('before_step', measurement_id, step.measurement_type)
                
                step_success = False
                step_error = None
                
                for attempt in range(step.retry_attempts):
                    try:
                        if attempt > 0:
                            self.logger.info(f"Retrying {step.measurement_type.value} (attempt {attempt + 1})")
                        
                        result = self._execute_measurement_step(step)
                        self._update_measurement_result(measurement_result, step.measurement_type, result)
                        self._step_results[step.measurement_type] = MeasurementStatus.COMPLETED
                        step_success = True
                        break
                        
                    except Exception as e:
                        step_error = str(e)
                        self.logger.warning(f"{step.measurement_type.value} attempt {attempt + 1} failed: {e}")
                        
                        if attempt == step.retry_attempts - 1:  # Last attempt
                            self._step_results[step.measurement_type] = MeasurementStatus.FAILED
                            error_msg = f"{step.measurement_type.value} failed after {step.retry_attempts} attempts: {step_error}"
                            errors.append(error_msg)
                            measurement_result.add_error(error_msg)
                            
                            # Handle error through error handler
                            self.error_handler.handle_generic_error(
                                e, ErrorType.MEASUREMENT_ERROR,
                                "measurement_orchestrator", f"execute_{step.measurement_type.value}"
                            )
                            
                            # Execute error callbacks
                            self._execute_callbacks('on_error', measurement_id, step.measurement_type, e)
                
                # Execute callbacks
                self._execute_callbacks('after_step', measurement_id, step.measurement_type, step_success)
                
                # Check if we should continue on failure
                if not step_success and not step.skip_on_error and not sequence.continue_on_failure:
                    self.logger.error(f"Stopping measurement cycle due to {step.measurement_type.value} failure")
                    break
            
            # Export results if requested
            if sequence.export_results:
                try:
                    self.data_export_manager.append_measurement(measurement_result)
                    self.logger.info(f"Measurement {measurement_id} exported successfully")
                except Exception as e:
                    error_msg = f"Failed to export measurement results: {e}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)
                    
                    self.error_handler.handle_file_system_error(
                        e, "measurement_orchestrator", "export_results"
                    )
        
        finally:
            # Cleanup if requested
            if sequence.cleanup_on_exit:
                try:
                    self.file_transfer_tester.cleanup()
                except Exception as e:
                    warning_msg = f"Cleanup failed: {e}"
                    warnings.append(warning_msg)
                    self.logger.warning(warning_msg)
            
            # Execute callbacks
            self._execute_callbacks('after_measurement', measurement_id)
            
            self._current_measurement_id = None
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        self.logger.info(f"Measurement cycle {measurement_id} completed in {execution_time:.2f}s")
        
        return OrchestrationResult(
            measurement_id=measurement_id,
            measurement_result=measurement_result,
            step_results=self._step_results.copy(),
            execution_time=execution_time,
            errors=errors,
            warnings=warnings
        )
    
    def _execute_measurement_step(self, step: MeasurementStep) -> Any:
        """
        Execute an individual measurement step.
        
        Args:
            step: Measurement step configuration
            
        Returns:
            Measurement result object
        """
        measurement_type = step.measurement_type
        params = step.parameters.copy()
        timeout = step.timeout
        
        if measurement_type == MeasurementType.WIFI_INFO:
            return self.wifi_collector.collect_wifi_info()
            
        elif measurement_type == MeasurementType.PING:
            targets = params.get('targets', self.config.target_ips)
            count = params.get('count', self.config.ping_count)
            size = params.get('size', self.config.ping_size)
            interval = params.get('interval', self.config.ping_interval)
            
            # For multiple targets, use the first one or aggregate results
            if isinstance(targets, list) and targets:
                return self.network_tester.ping(
                    target=targets[0],
                    count=count,
                    size=size,
                    interval=interval,
                    timeout=timeout
                )
            else:
                raise ValueError("No valid targets specified for ping test")
                
        elif measurement_type == MeasurementType.IPERF_TCP:
            server_ip = params.get('server_ip', self.config.iperf_server)
            server_port = params.get('server_port', self.config.iperf_port)
            duration = params.get('duration', self.config.iperf_duration)
            parallel = params.get('parallel', self.config.iperf_parallel)
            
            return self.network_tester.iperf_tcp_bidirectional(
                server_ip=server_ip,
                server_port=server_port,
                duration=duration,
                parallel=parallel,
                timeout=timeout
            )
            
        elif measurement_type == MeasurementType.IPERF_UDP:
            server_ip = params.get('server_ip', self.config.iperf_server)
            server_port = params.get('server_port', self.config.iperf_port)
            duration = params.get('duration', self.config.iperf_duration)
            bandwidth = params.get('bandwidth', self.config.iperf_udp_bandwidth)
            
            return self.network_tester.iperf_udp_test(
                server_ip=server_ip,
                server_port=server_port,
                duration=duration,
                bandwidth=bandwidth,
                timeout=timeout
            )
            
        elif measurement_type == MeasurementType.FILE_TRANSFER:
            server_address = params.get('server_address', self.config.file_server)
            file_size_mb = params.get('file_size_mb', self.config.file_size_mb)
            protocol = params.get('protocol', self.config.file_protocol.lower())
            direction = params.get('direction', 'download')
            
            if protocol == 'smb':
                return self.file_transfer_tester.test_smb_transfer(
                    server_address=server_address,
                    share_name=params.get('share_name', 'share'),
                    file_size_mb=file_size_mb,
                    direction=direction,
                    username=params.get('username', ''),
                    password=params.get('password', ''),
                    domain=params.get('domain', ''),
                    port=params.get('port', 445)
                )
            elif protocol == 'ftp':
                return self.file_transfer_tester.test_ftp_transfer(
                    server_address=server_address,
                    file_size_mb=file_size_mb,
                    direction=direction,
                    username=params.get('username', 'anonymous'),
                    password=params.get('password', 'anonymous@example.com'),
                    port=params.get('port', 21)
                )
            elif protocol in ['http', 'https']:
                return self.file_transfer_tester.test_http_transfer(
                    server_address=server_address,
                    file_size_mb=file_size_mb,
                    direction=direction,
                    port=params.get('port', 80 if protocol == 'http' else 443),
                    use_https=(protocol == 'https')
                )
            else:
                raise ValueError(f"Unsupported file transfer protocol: {protocol}")
        
        else:
            raise ValueError(f"Unknown measurement type: {measurement_type}")
    
    def _update_measurement_result(self, 
                                   measurement_result: MeasurementResult, 
                                   measurement_type: MeasurementType,
                                   result: Any) -> None:
        """
        Update measurement result object with step result.
        
        Args:
            measurement_result: MeasurementResult to update
            measurement_type: Type of measurement
            result: Result object from measurement step
        """
        if result is None:
            return
            
        if measurement_type == MeasurementType.WIFI_INFO:
            measurement_result.wifi_info = result
        elif measurement_type == MeasurementType.PING:
            measurement_result.ping_result = result
        elif measurement_type == MeasurementType.IPERF_TCP:
            measurement_result.iperf_tcp_result = result
        elif measurement_type == MeasurementType.IPERF_UDP:
            measurement_result.iperf_udp_result = result
        elif measurement_type == MeasurementType.FILE_TRANSFER:
            measurement_result.file_transfer_result = result
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """
        Register a callback for measurement events.
        
        Args:
            event: Event name ('before_measurement', 'after_measurement', 
                   'before_step', 'after_step', 'on_error')
            callback: Callback function
        """
        if event not in self._callbacks:
            raise ValueError(f"Unknown event: {event}")
        
        self._callbacks[event].append(callback)
        self.logger.debug(f"Registered callback for event: {event}")
    
    def _execute_callbacks(self, event: str, *args, **kwargs) -> None:
        """
        Execute callbacks for a specific event.
        
        Args:
            event: Event name
            *args: Arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks
        """
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self.logger.warning(f"Callback execution failed for {event}: {e}")
    
    def get_supported_protocols(self) -> List[str]:
        """
        Get list of supported file transfer protocols.
        
        Returns:
            List of supported protocol names
        """
        protocols = ['http', 'https', 'ftp']
        
        # Check if SMB is available
        try:
            from smb.SMBConnection import SMBConnection
            protocols.append('smb')
        except ImportError:
            pass
        
        return protocols
    
    def create_custom_sequence(self, enabled_measurements: Set[MeasurementType],
                               timeout_overrides: Optional[Dict[MeasurementType, float]] = None,
                               parameter_overrides: Optional[Dict[MeasurementType, Dict[str, Any]]] = None) -> MeasurementSequence:
        """
        Create a custom measurement sequence with specified tests.
        
        Args:
            enabled_measurements: Set of measurement types to enable
            timeout_overrides: Custom timeouts for specific measurements
            parameter_overrides: Custom parameters for specific measurements
            
        Returns:
            Custom MeasurementSequence
        """
        default_sequence = self.create_default_sequence()
        custom_steps = []
        
        for step in default_sequence.steps:
            if step.measurement_type in enabled_measurements:
                # Create a copy of the step
                custom_step = MeasurementStep(
                    measurement_type=step.measurement_type,
                    enabled=True,
                    timeout=step.timeout,
                    skip_on_error=step.skip_on_error,
                    retry_attempts=step.retry_attempts,
                    parameters=step.parameters.copy()
                )
                
                # Apply overrides
                if timeout_overrides and step.measurement_type in timeout_overrides:
                    custom_step.timeout = timeout_overrides[step.measurement_type]
                
                if parameter_overrides and step.measurement_type in parameter_overrides:
                    custom_step.parameters.update(parameter_overrides[step.measurement_type])
                
                custom_steps.append(custom_step)
        
        return MeasurementSequence(
            steps=custom_steps,
            validate_prerequisites=True,
            continue_on_failure=True,
            export_results=True,
            cleanup_on_exit=True
        )
    
    def get_measurement_status(self) -> Dict[str, Any]:
        """
        Get current measurement orchestrator status.
        
        Returns:
            Dictionary with status information
        """
        return {
            'current_measurement_id': self._current_measurement_id,
            'step_results': {mt.value: status.value for mt, status in self._step_results.items()},
            'error_statistics': self.error_handler.get_error_statistics(),
            'supported_protocols': self.get_supported_protocols(),
            'wifi_connected': self.wifi_collector.is_connected()
        }
    
    def cleanup(self) -> None:
        """Clean up resources used by the orchestrator."""
        try:
            self.file_transfer_tester.cleanup()
        except Exception as e:
            self.logger.warning(f"Cleanup failed: {e}")
        
        self.logger.info("MeasurementOrchestrator cleanup completed")