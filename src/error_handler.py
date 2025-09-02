"""Centralized error handling system for wireless LAN analyzer."""

import logging
import sys
import traceback
import os
import socket
import subprocess
from typing import Optional, Dict, Any, Callable, Union, List, Type
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from contextlib import contextmanager


class ErrorType(Enum):
    """Error type categories."""
    NETWORK_ERROR = "network_error"
    WIN32_API_ERROR = "win32_api_error"
    FILE_SYSTEM_ERROR = "file_system_error"
    CONFIG_ERROR = "config_error"
    MEASUREMENT_ERROR = "measurement_error"
    DATA_EXPORT_ERROR = "data_export_error"
    SYSTEM_ERROR = "system_error"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Context information for errors."""
    error_type: ErrorType
    severity: ErrorSeverity
    component: str
    operation: str
    timestamp: datetime
    additional_info: Dict[str, Any]


class WLANAnalyzerError(Exception):
    """Base exception class for WLAN analyzer errors."""

    def __init__(self, message: str, error_type: ErrorType = ErrorType.SYSTEM_ERROR,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM, component: str = "unknown",
                 operation: str = "unknown", additional_info: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_type = error_type
        self.severity = severity
        self.component = component
        self.operation = operation
        self.timestamp = datetime.now()
        self.additional_info = additional_info or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            'message': str(self),
            'error_type': self.error_type.value,
            'severity': self.severity.value,
            'component': self.component,
            'operation': self.operation,
            'timestamp': self.timestamp.isoformat(),
            'additional_info': self.additional_info
        }


class NetworkError(WLANAnalyzerError):
    """Network-related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.NETWORK_ERROR, **kwargs)


class Win32ApiError(WLANAnalyzerError):
    """Win32 API-related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.WIN32_API_ERROR, **kwargs)


class FileSystemError(WLANAnalyzerError):
    """File system-related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.FILE_SYSTEM_ERROR, **kwargs)


class ConfigurationError(WLANAnalyzerError):
    """Configuration-related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.CONFIG_ERROR, **kwargs)


class MeasurementError(WLANAnalyzerError):
    """Measurement-related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.MEASUREMENT_ERROR, **kwargs)


class DataExportError(WLANAnalyzerError):
    """Data export-related errors."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, error_type=ErrorType.DATA_EXPORT_ERROR, **kwargs)


class ErrorHandler:
    """Centralized error handling system."""

    def __init__(self, logger_name: str = "wlan_analyzer"):
        """Initialize error handler.
        
        Args:
            logger_name: Name of the logger to use.
        """
        self.logger = logging.getLogger(logger_name)
        self.error_counts: Dict[ErrorType, int] = {error_type: 0 for error_type in ErrorType}
        self.error_history: List[ErrorContext] = []
        self.max_history_size = 1000
        self._error_callbacks: Dict[ErrorType, List[Callable]] = {}

    def handle_network_error(self, exception: Exception, component: str = "network",
                           operation: str = "unknown", **kwargs) -> Optional[NetworkError]:
        """Handle network-related errors.
        
        Args:
            exception: The original exception.
            component: Component where error occurred.
            operation: Operation being performed.
            **kwargs: Additional context information.
            
        Returns:
            NetworkError instance or None if handled.
        """
        severity = ErrorSeverity.MEDIUM
        additional_info = kwargs.copy()
        additional_info['original_exception'] = str(exception)
        additional_info['exception_type'] = type(exception).__name__
        
        # Determine severity based on exception type
        if isinstance(exception, (socket.timeout, TimeoutError)):
            severity = ErrorSeverity.LOW
            message = f"Network timeout in {component} during {operation}: {exception}"
        elif isinstance(exception, socket.gaierror):
            severity = ErrorSeverity.MEDIUM
            message = f"DNS resolution failed in {component} during {operation}: {exception}"
        elif isinstance(exception, ConnectionRefusedError):
            severity = ErrorSeverity.MEDIUM
            message = f"Connection refused in {component} during {operation}: {exception}"
        elif isinstance(exception, (ConnectionResetError, BrokenPipeError)):
            severity = ErrorSeverity.MEDIUM
            message = f"Connection lost in {component} during {operation}: {exception}"
        else:
            severity = ErrorSeverity.HIGH
            message = f"Network error in {component} during {operation}: {exception}"
        
        error = NetworkError(
            message=message,
            severity=severity,
            component=component,
            operation=operation,
            additional_info=additional_info
        )
        
        self._record_error(error)
        self.logger.error(message)
        
        if severity.value in ["high", "critical"]:
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        return error

    def handle_win32_api_error(self, exception: Exception, component: str = "win32_api",
                              operation: str = "unknown", **kwargs) -> Optional[Win32ApiError]:
        """Handle Win32 API-related errors.
        
        Args:
            exception: The original exception.
            component: Component where error occurred.
            operation: Operation being performed.
            **kwargs: Additional context information.
            
        Returns:
            Win32ApiError instance or None if handled.
        """
        severity = ErrorSeverity.MEDIUM
        additional_info = kwargs.copy()
        additional_info['original_exception'] = str(exception)
        additional_info['exception_type'] = type(exception).__name__
        
        # Check if it's a permission error
        if "access" in str(exception).lower() or "permission" in str(exception).lower():
            severity = ErrorSeverity.HIGH
            message = f"Win32 API access denied in {component} during {operation}: {exception}"
        else:
            message = f"Win32 API error in {component} during {operation}: {exception}"
        
        error = Win32ApiError(
            message=message,
            severity=severity,
            component=component,
            operation=operation,
            additional_info=additional_info
        )
        
        self._record_error(error)
        self.logger.error(message)
        
        if severity.value in ["high", "critical"]:
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        return error

    def handle_file_system_error(self, exception: Exception, component: str = "filesystem",
                                operation: str = "unknown", **kwargs) -> Optional[FileSystemError]:
        """Handle file system-related errors.
        
        Args:
            exception: The original exception.
            component: Component where error occurred.
            operation: Operation being performed.
            **kwargs: Additional context information.
            
        Returns:
            FileSystemError instance or None if handled.
        """
        severity = ErrorSeverity.MEDIUM
        additional_info = kwargs.copy()
        additional_info['original_exception'] = str(exception)
        additional_info['exception_type'] = type(exception).__name__
        
        # Determine severity and message based on exception type
        if isinstance(exception, FileNotFoundError):
            severity = ErrorSeverity.LOW
            message = f"File not found in {component} during {operation}: {exception}"
        elif isinstance(exception, PermissionError):
            severity = ErrorSeverity.HIGH
            message = f"Permission denied in {component} during {operation}: {exception}"
        elif isinstance(exception, OSError):
            if exception.errno == 28:  # No space left on device
                severity = ErrorSeverity.CRITICAL
                message = f"Disk space full in {component} during {operation}: {exception}"
            else:
                severity = ErrorSeverity.MEDIUM
                message = f"OS error in {component} during {operation}: {exception}"
        else:
            message = f"File system error in {component} during {operation}: {exception}"
        
        error = FileSystemError(
            message=message,
            severity=severity,
            component=component,
            operation=operation,
            additional_info=additional_info
        )
        
        self._record_error(error)
        self.logger.error(message)
        
        if severity.value in ["high", "critical"]:
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        return error

    def handle_subprocess_error(self, exception: Exception, component: str = "subprocess",
                               operation: str = "unknown", **kwargs) -> Optional[WLANAnalyzerError]:
        """Handle subprocess-related errors.
        
        Args:
            exception: The original exception.
            component: Component where error occurred.
            operation: Operation being performed.
            **kwargs: Additional context information.
            
        Returns:
            WLANAnalyzerError instance or None if handled.
        """
        severity = ErrorSeverity.MEDIUM
        additional_info = kwargs.copy()
        additional_info['original_exception'] = str(exception)
        additional_info['exception_type'] = type(exception).__name__
        
        if isinstance(exception, subprocess.CalledProcessError):
            additional_info['return_code'] = exception.returncode
            additional_info['cmd'] = exception.cmd
            additional_info['output'] = getattr(exception, 'output', None)
            additional_info['stderr'] = getattr(exception, 'stderr', None)
            
            if exception.returncode == 127:  # Command not found
                severity = ErrorSeverity.HIGH
                message = f"Command not found in {component} during {operation}: {exception.cmd}"
            else:
                message = f"Subprocess failed in {component} during {operation}: {exception}"
        elif isinstance(exception, subprocess.TimeoutExpired):
            severity = ErrorSeverity.MEDIUM
            message = f"Subprocess timeout in {component} during {operation}: {exception}"
        else:
            message = f"Subprocess error in {component} during {operation}: {exception}"
        
        error = WLANAnalyzerError(
            message=message,
            error_type=ErrorType.SYSTEM_ERROR,
            severity=severity,
            component=component,
            operation=operation,
            additional_info=additional_info
        )
        
        self._record_error(error)
        self.logger.error(message)
        
        return error

    def handle_generic_error(self, exception: Exception, error_type: ErrorType,
                           component: str = "unknown", operation: str = "unknown",
                           severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                           **kwargs) -> WLANAnalyzerError:
        """Handle generic errors.
        
        Args:
            exception: The original exception.
            error_type: Type of error.
            component: Component where error occurred.
            operation: Operation being performed.
            severity: Error severity.
            **kwargs: Additional context information.
            
        Returns:
            WLANAnalyzerError instance.
        """
        additional_info = kwargs.copy()
        additional_info['original_exception'] = str(exception)
        additional_info['exception_type'] = type(exception).__name__
        
        message = f"{error_type.value.replace('_', ' ').title()} in {component} during {operation}: {exception}"
        
        error = WLANAnalyzerError(
            message=message,
            error_type=error_type,
            severity=severity,
            component=component,
            operation=operation,
            additional_info=additional_info
        )
        
        self._record_error(error)
        self.logger.error(message)
        
        if severity.value in ["high", "critical"]:
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
        return error

    def _record_error(self, error: WLANAnalyzerError) -> None:
        """Record error in history and update counters.
        
        Args:
            error: Error to record.
        """
        # Update counter
        self.error_counts[error.error_type] += 1
        
        # Add to history
        context = ErrorContext(
            error_type=error.error_type,
            severity=error.severity,
            component=error.component,
            operation=error.operation,
            timestamp=error.timestamp,
            additional_info=error.additional_info
        )
        
        self.error_history.append(context)
        
        # Maintain history size limit
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]
        
        # Call registered callbacks
        for callback in self._error_callbacks.get(error.error_type, []):
            try:
                callback(error)
            except Exception as e:
                self.logger.warning(f"Error callback failed: {e}")

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics.
        
        Returns:
            Dictionary with error statistics.
        """
        total_errors = sum(self.error_counts.values())
        
        stats = {
            'total_errors': total_errors,
            'errors_by_type': {et.value: count for et, count in self.error_counts.items()},
            'recent_errors': len([e for e in self.error_history 
                                if (datetime.now() - e.timestamp).seconds < 3600]),
            'history_size': len(self.error_history)
        }
        
        if self.error_history:
            latest_error = max(self.error_history, key=lambda x: x.timestamp)
            stats['latest_error'] = {
                'type': latest_error.error_type.value,
                'severity': latest_error.severity.value,
                'component': latest_error.component,
                'operation': latest_error.operation,
                'timestamp': latest_error.timestamp.isoformat()
            }
        
        return stats

    def clear_error_history(self) -> None:
        """Clear error history and reset counters."""
        self.error_history.clear()
        self.error_counts = {error_type: 0 for error_type in ErrorType}

    def register_error_callback(self, error_type: ErrorType, callback: Callable) -> None:
        """Register callback for specific error type.
        
        Args:
            error_type: Error type to monitor.
            callback: Callback function to call when error occurs.
        """
        if error_type not in self._error_callbacks:
            self._error_callbacks[error_type] = []
        self._error_callbacks[error_type].append(callback)

    @contextmanager
    def error_context(self, component: str, operation: str):
        """Context manager for handling errors in a specific context.
        
        Args:
            component: Component name.
            operation: Operation name.
        """
        try:
            yield
        except socket.error as e:
            self.handle_network_error(e, component, operation)
            raise
        except OSError as e:
            self.handle_file_system_error(e, component, operation)
            raise
        except subprocess.SubprocessError as e:
            self.handle_subprocess_error(e, component, operation)
            raise
        except Exception as e:
            self.handle_generic_error(e, ErrorType.SYSTEM_ERROR, component, operation)
            raise

    def log_error_summary(self) -> None:
        """Log a summary of errors."""
        stats = self.get_error_statistics()
        
        if stats['total_errors'] == 0:
            self.logger.info("No errors recorded")
            return
        
        self.logger.info(f"Error Summary: {stats['total_errors']} total errors")
        
        for error_type, count in stats['errors_by_type'].items():
            if count > 0:
                self.logger.info(f"  {error_type}: {count}")
        
        self.logger.info(f"Recent errors (last hour): {stats['recent_errors']}")
        
        if 'latest_error' in stats:
            latest = stats['latest_error']
            self.logger.info(f"Latest error: {latest['type']} in {latest['component']} "
                           f"({latest['severity']}) at {latest['timestamp']}")


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance.
    
    Returns:
        Global ErrorHandler instance.
    """
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ErrorHandler()
    return _global_error_handler


def set_error_handler(handler: ErrorHandler) -> None:
    """Set the global error handler instance.
    
    Args:
        handler: ErrorHandler instance to set as global.
    """
    global _global_error_handler
    _global_error_handler = handler