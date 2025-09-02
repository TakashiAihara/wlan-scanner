"""Unit tests for error handling system."""

import unittest
import socket
import subprocess
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from src.error_handler import (
    ErrorHandler, ErrorType, ErrorSeverity, ErrorContext,
    WLANAnalyzerError, NetworkError, Win32ApiError, FileSystemError,
    ConfigurationError, MeasurementError, DataExportError,
    get_error_handler, set_error_handler
)


class TestErrorClasses(unittest.TestCase):
    """Test custom error classes."""

    def test_wlan_analyzer_error_creation(self):
        """Test WLANAnalyzerError creation with all parameters."""
        error = WLANAnalyzerError(
            message="Test error",
            error_type=ErrorType.NETWORK_ERROR,
            severity=ErrorSeverity.HIGH,
            component="test_component",
            operation="test_operation",
            additional_info={"key": "value"}
        )
        
        self.assertEqual(str(error), "Test error")
        self.assertEqual(error.error_type, ErrorType.NETWORK_ERROR)
        self.assertEqual(error.severity, ErrorSeverity.HIGH)
        self.assertEqual(error.component, "test_component")
        self.assertEqual(error.operation, "test_operation")
        self.assertEqual(error.additional_info["key"], "value")
        self.assertIsInstance(error.timestamp, datetime)

    def test_wlan_analyzer_error_to_dict(self):
        """Test error to dictionary conversion."""
        error = WLANAnalyzerError(
            message="Test error",
            error_type=ErrorType.NETWORK_ERROR,
            severity=ErrorSeverity.HIGH
        )
        
        error_dict = error.to_dict()
        
        self.assertEqual(error_dict['message'], "Test error")
        self.assertEqual(error_dict['error_type'], "network_error")
        self.assertEqual(error_dict['severity'], "high")
        self.assertIn('timestamp', error_dict)

    def test_network_error(self):
        """Test NetworkError automatic error type setting."""
        error = NetworkError("Network test error")
        self.assertEqual(error.error_type, ErrorType.NETWORK_ERROR)

    def test_win32_api_error(self):
        """Test Win32ApiError automatic error type setting."""
        error = Win32ApiError("Win32 test error")
        self.assertEqual(error.error_type, ErrorType.WIN32_API_ERROR)

    def test_file_system_error(self):
        """Test FileSystemError automatic error type setting."""
        error = FileSystemError("FileSystem test error")
        self.assertEqual(error.error_type, ErrorType.FILE_SYSTEM_ERROR)


class TestErrorHandler(unittest.TestCase):
    """Test ErrorHandler class."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = ErrorHandler("test_logger")

    def test_initialization(self):
        """Test ErrorHandler initialization."""
        self.assertIsNotNone(self.handler.logger)
        self.assertEqual(len(self.handler.error_counts), len(ErrorType))
        self.assertEqual(len(self.handler.error_history), 0)
        self.assertEqual(self.handler.max_history_size, 1000)

    def test_handle_network_timeout_error(self):
        """Test handling network timeout errors."""
        timeout_error = socket.timeout("Connection timed out")
        
        result = self.handler.handle_network_error(
            timeout_error, 
            component="ping", 
            operation="ping_test"
        )
        
        self.assertIsInstance(result, NetworkError)
        self.assertEqual(result.severity, ErrorSeverity.LOW)
        self.assertEqual(result.component, "ping")
        self.assertEqual(result.operation, "ping_test")
        self.assertIn("timeout", str(result).lower())

    def test_handle_network_dns_error(self):
        """Test handling DNS resolution errors."""
        dns_error = socket.gaierror("Name resolution failed")
        
        result = self.handler.handle_network_error(
            dns_error,
            component="network_tester",
            operation="ping"
        )
        
        self.assertIsInstance(result, NetworkError)
        self.assertEqual(result.severity, ErrorSeverity.MEDIUM)
        self.assertIn("DNS resolution failed", str(result))

    def test_handle_network_connection_refused(self):
        """Test handling connection refused errors."""
        conn_error = ConnectionRefusedError("Connection refused")
        
        result = self.handler.handle_network_error(
            conn_error,
            component="iperf",
            operation="tcp_test"
        )
        
        self.assertIsInstance(result, NetworkError)
        self.assertEqual(result.severity, ErrorSeverity.MEDIUM)
        self.assertIn("Connection refused", str(result))

    def test_handle_win32_api_error(self):
        """Test handling Win32 API errors."""
        api_error = Exception("Invalid handle")
        
        result = self.handler.handle_win32_api_error(
            api_error,
            component="wifi_collector",
            operation="get_interface_info"
        )
        
        self.assertIsInstance(result, Win32ApiError)
        self.assertEqual(result.component, "wifi_collector")
        self.assertEqual(result.operation, "get_interface_info")

    def test_handle_win32_api_permission_error(self):
        """Test handling Win32 API permission errors."""
        permission_error = Exception("Access denied")
        
        result = self.handler.handle_win32_api_error(
            permission_error,
            component="wifi_collector",
            operation="scan"
        )
        
        self.assertIsInstance(result, Win32ApiError)
        self.assertEqual(result.severity, ErrorSeverity.HIGH)
        self.assertIn("access denied", str(result).lower())

    def test_handle_file_not_found_error(self):
        """Test handling file not found errors."""
        file_error = FileNotFoundError("Config file not found")
        
        result = self.handler.handle_file_system_error(
            file_error,
            component="config_manager",
            operation="load_config"
        )
        
        self.assertIsInstance(result, FileSystemError)
        self.assertEqual(result.severity, ErrorSeverity.LOW)

    def test_handle_permission_error(self):
        """Test handling permission errors."""
        perm_error = PermissionError("Permission denied")
        
        result = self.handler.handle_file_system_error(
            perm_error,
            component="data_export",
            operation="write_csv"
        )
        
        self.assertIsInstance(result, FileSystemError)
        self.assertEqual(result.severity, ErrorSeverity.HIGH)

    def test_handle_disk_full_error(self):
        """Test handling disk full errors."""
        # Create OSError with errno 28 (No space left on device)
        disk_error = OSError(28, "No space left on device")
        
        result = self.handler.handle_file_system_error(
            disk_error,
            component="data_export",
            operation="write_file"
        )
        
        self.assertIsInstance(result, FileSystemError)
        self.assertEqual(result.severity, ErrorSeverity.CRITICAL)

    def test_handle_subprocess_called_process_error(self):
        """Test handling subprocess CalledProcessError."""
        process_error = subprocess.CalledProcessError(1, ["test", "command"])
        
        result = self.handler.handle_subprocess_error(
            process_error,
            component="network_tester",
            operation="iperf"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.error_type, ErrorType.SYSTEM_ERROR)
        self.assertEqual(result.additional_info['return_code'], 1)

    def test_handle_subprocess_timeout_error(self):
        """Test handling subprocess timeout errors."""
        timeout_error = subprocess.TimeoutExpired(["test"], 30)
        
        result = self.handler.handle_subprocess_error(
            timeout_error,
            component="network_tester",
            operation="ping"
        )
        
        self.assertIsNotNone(result)
        self.assertIn("timeout", str(result).lower())

    def test_handle_subprocess_command_not_found(self):
        """Test handling command not found errors."""
        cmd_error = subprocess.CalledProcessError(127, ["nonexistent_command"])
        
        result = self.handler.handle_subprocess_error(
            cmd_error,
            component="wifi_collector",
            operation="scan"
        )
        
        self.assertIsNotNone(result)
        self.assertEqual(result.severity, ErrorSeverity.HIGH)
        self.assertIn("Command not found", str(result))

    def test_error_counting(self):
        """Test error counting functionality."""
        # Initially no errors
        self.assertEqual(self.handler.error_counts[ErrorType.NETWORK_ERROR], 0)
        
        # Add some errors
        self.handler.handle_network_error(socket.timeout(), "test", "test")
        self.handler.handle_network_error(ConnectionError(), "test", "test")
        
        # Check counts
        self.assertEqual(self.handler.error_counts[ErrorType.NETWORK_ERROR], 2)

    def test_error_history(self):
        """Test error history tracking."""
        # Initially empty
        self.assertEqual(len(self.handler.error_history), 0)
        
        # Add error
        self.handler.handle_network_error(socket.timeout(), "test", "test")
        
        # Check history
        self.assertEqual(len(self.handler.error_history), 1)
        context = self.handler.error_history[0]
        self.assertEqual(context.error_type, ErrorType.NETWORK_ERROR)
        self.assertEqual(context.component, "test")

    def test_error_history_size_limit(self):
        """Test error history size limiting."""
        # Set small limit for testing
        self.handler.max_history_size = 5
        
        # Add more errors than limit
        for i in range(10):
            self.handler.handle_network_error(socket.timeout(), f"test_{i}", "test")
        
        # Check history size is limited
        self.assertEqual(len(self.handler.error_history), 5)
        
        # Check that latest errors are kept
        self.assertEqual(self.handler.error_history[-1].component, "test_9")

    def test_get_error_statistics(self):
        """Test error statistics generation."""
        # Add some errors
        self.handler.handle_network_error(socket.timeout(), "test", "test")
        self.handler.handle_file_system_error(FileNotFoundError(), "test", "test")
        
        stats = self.handler.get_error_statistics()
        
        self.assertEqual(stats['total_errors'], 2)
        self.assertEqual(stats['errors_by_type']['network_error'], 1)
        self.assertEqual(stats['errors_by_type']['file_system_error'], 1)
        self.assertIn('latest_error', stats)

    def test_clear_error_history(self):
        """Test clearing error history."""
        # Add some errors
        self.handler.handle_network_error(socket.timeout(), "test", "test")
        self.handler.handle_file_system_error(FileNotFoundError(), "test", "test")
        
        # Clear history
        self.handler.clear_error_history()
        
        # Check everything is cleared
        self.assertEqual(len(self.handler.error_history), 0)
        self.assertEqual(sum(self.handler.error_counts.values()), 0)

    def test_register_error_callback(self):
        """Test registering error callbacks."""
        callback_called = []
        
        def test_callback(error):
            callback_called.append(error)
        
        self.handler.register_error_callback(ErrorType.NETWORK_ERROR, test_callback)
        
        # Trigger error
        self.handler.handle_network_error(socket.timeout(), "test", "test")
        
        # Check callback was called
        self.assertEqual(len(callback_called), 1)
        self.assertIsInstance(callback_called[0], NetworkError)

    def test_error_callback_exception_handling(self):
        """Test that callback exceptions don't break error handling."""
        def failing_callback(error):
            raise Exception("Callback failed")
        
        self.handler.register_error_callback(ErrorType.NETWORK_ERROR, failing_callback)
        
        # This should not raise an exception
        result = self.handler.handle_network_error(socket.timeout(), "test", "test")
        
        self.assertIsInstance(result, NetworkError)

    def test_error_context_manager(self):
        """Test error context manager."""
        # Test successful operation
        with self.handler.error_context("test_component", "test_operation"):
            pass  # No error
        
        # Test with socket error
        with self.assertRaises(socket.timeout):
            with self.handler.error_context("test_component", "test_operation"):
                raise socket.timeout("Test timeout")
        
        # Check error was recorded
        self.assertEqual(self.handler.error_counts[ErrorType.NETWORK_ERROR], 1)

    def test_log_error_summary_no_errors(self):
        """Test logging error summary with no errors."""
        with patch.object(self.handler.logger, 'info') as mock_log:
            self.handler.log_error_summary()
            mock_log.assert_called_with("No errors recorded")

    def test_log_error_summary_with_errors(self):
        """Test logging error summary with errors."""
        self.handler.handle_network_error(socket.timeout(), "test", "test")
        
        with patch.object(self.handler.logger, 'info') as mock_log:
            self.handler.log_error_summary()
            
            # Check that summary was logged
            calls = [call.args[0] for call in mock_log.call_args_list]
            self.assertTrue(any("Error Summary: 1 total errors" in call for call in calls))
            self.assertTrue(any("network_error: 1" in call for call in calls))


class TestGlobalErrorHandler(unittest.TestCase):
    """Test global error handler functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset global handler
        import src.error_handler
        src.error_handler._global_error_handler = None

    def test_get_error_handler_creates_instance(self):
        """Test that get_error_handler creates instance if none exists."""
        handler = get_error_handler()
        self.assertIsInstance(handler, ErrorHandler)

    def test_get_error_handler_returns_same_instance(self):
        """Test that get_error_handler returns the same instance."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        self.assertIs(handler1, handler2)

    def test_set_error_handler(self):
        """Test setting custom error handler."""
        custom_handler = ErrorHandler("custom")
        set_error_handler(custom_handler)
        
        retrieved_handler = get_error_handler()
        self.assertIs(retrieved_handler, custom_handler)


class TestErrorContext(unittest.TestCase):
    """Test ErrorContext data class."""

    def test_error_context_creation(self):
        """Test ErrorContext creation."""
        timestamp = datetime.now()
        context = ErrorContext(
            error_type=ErrorType.NETWORK_ERROR,
            severity=ErrorSeverity.HIGH,
            component="test",
            operation="test_op",
            timestamp=timestamp,
            additional_info={"test": "value"}
        )
        
        self.assertEqual(context.error_type, ErrorType.NETWORK_ERROR)
        self.assertEqual(context.severity, ErrorSeverity.HIGH)
        self.assertEqual(context.component, "test")
        self.assertEqual(context.operation, "test_op")
        self.assertEqual(context.timestamp, timestamp)
        self.assertEqual(context.additional_info["test"], "value")


class TestErrorHandlerIntegration(unittest.TestCase):
    """Integration tests for error handler."""

    def setUp(self):
        """Set up test fixtures."""
        self.handler = ErrorHandler("integration_test")

    def test_multiple_error_types(self):
        """Test handling multiple different error types."""
        # Network error
        self.handler.handle_network_error(socket.timeout(), "net", "ping")
        
        # File system error
        self.handler.handle_file_system_error(FileNotFoundError(), "fs", "read")
        
        # Win32 API error
        self.handler.handle_win32_api_error(Exception("API error"), "wifi", "scan")
        
        # Check all errors were recorded
        stats = self.handler.get_error_statistics()
        self.assertEqual(stats['total_errors'], 3)
        self.assertEqual(stats['errors_by_type']['network_error'], 1)
        self.assertEqual(stats['errors_by_type']['file_system_error'], 1)
        self.assertEqual(stats['errors_by_type']['win32_api_error'], 1)

    def test_error_callback_integration(self):
        """Test error callback integration with multiple error types."""
        network_errors = []
        file_errors = []
        
        def network_callback(error):
            network_errors.append(error)
        
        def file_callback(error):
            file_errors.append(error)
        
        self.handler.register_error_callback(ErrorType.NETWORK_ERROR, network_callback)
        self.handler.register_error_callback(ErrorType.FILE_SYSTEM_ERROR, file_callback)
        
        # Trigger different error types
        self.handler.handle_network_error(socket.timeout(), "net", "test")
        self.handler.handle_file_system_error(FileNotFoundError(), "fs", "test")
        self.handler.handle_network_error(ConnectionError(), "net", "test2")
        
        # Check callbacks were called correctly
        self.assertEqual(len(network_errors), 2)
        self.assertEqual(len(file_errors), 1)
        self.assertIsInstance(network_errors[0], NetworkError)
        self.assertIsInstance(file_errors[0], FileSystemError)

    def test_recent_errors_calculation(self):
        """Test recent errors calculation."""
        # Add old error (simulate by manually setting timestamp)
        old_error = NetworkError("Old error")
        old_error.timestamp = datetime.now() - timedelta(hours=2)
        
        context = ErrorContext(
            error_type=old_error.error_type,
            severity=old_error.severity,
            component=old_error.component,
            operation=old_error.operation,
            timestamp=old_error.timestamp,
            additional_info=old_error.additional_info
        )
        self.handler.error_history.append(context)
        self.handler.error_counts[ErrorType.NETWORK_ERROR] += 1
        
        # Add recent error
        self.handler.handle_network_error(socket.timeout(), "test", "test")
        
        stats = self.handler.get_error_statistics()
        self.assertEqual(stats['total_errors'], 2)
        self.assertEqual(stats['recent_errors'], 1)  # Only recent error counts


if __name__ == '__main__':
    unittest.main()