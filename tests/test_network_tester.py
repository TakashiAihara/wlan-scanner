"""Comprehensive unit tests for NetworkTester class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import statistics
import socket
import errno

from src.network_tester import (
    NetworkTester, PingStatistics, IperfError, IperfServerUnavailableError, IperfConnectionError
)
from src.models import PingResult, IperfTcpResult, IperfUdpResult
from pythonping.executor import Response, ResponseList


class MockResponse:
    """Mock response object for pythonping."""
    
    def __init__(self, success: bool = True, time_elapsed_ms: float = 10.0):
        self.success = success
        self.time_elapsed_ms = time_elapsed_ms


class MockResponseList:
    """Mock response list for pythonping."""
    
    def __init__(self, responses):
        self.responses = responses
    
    def __iter__(self):
        return iter(self.responses)
    
    def __len__(self):
        return len(self.responses)


class MockIperfResult:
    """Mock iperf3 result object."""
    
    def __init__(self, error=None):
        self.error = error
        self.sum_sent = None
        self.sum_received = None


class MockIperfSumData:
    """Mock iperf3 sum data object."""
    
    def __init__(self, bytes=0, bits_per_second=0, retransmits=0, packets=0, 
                 lost_packets=0, lost_percent=0.0, jitter_ms=0.0):
        self.bytes = bytes
        self.bits_per_second = bits_per_second
        self.retransmits = retransmits
        self.packets = packets
        self.lost_packets = lost_packets
        self.lost_percent = lost_percent
        self.jitter_ms = jitter_ms


class MockIperfClient:
    """Mock iperf3 Client class."""
    
    def __init__(self):
        self.server_hostname = None
        self.port = None
        self.duration = None
        self.num_streams = None
        self.reverse = None
        self.protocol = None
        self.bandwidth = None
        self.blksize = None
        self.timeout = None
        self._result = None
    
    def run(self):
        if self._result:
            return self._result
        # Return a default successful result
        result = MockIperfResult()
        result.sum_sent = MockIperfSumData(bytes=1000000, bits_per_second=10000000)
        result.sum_received = MockIperfSumData(bytes=1000000, bits_per_second=10000000)
        return result


class TestNetworkTester(unittest.TestCase):
    """Test cases for NetworkTester class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = NetworkTester(timeout=5.0)
        self.target_ip = "8.8.8.8"
        
    def test_initialization(self):
        """Test NetworkTester initialization."""
        tester = NetworkTester(timeout=10.0)
        self.assertEqual(tester.timeout, 10.0)
        
        # Test default timeout
        default_tester = NetworkTester()
        self.assertEqual(default_tester.timeout, 10.0)
    
    def test_ping_parameter_validation(self):
        """Test ping parameter validation."""
        with self.assertRaises(ValueError):
            self.tester.ping(self.target_ip, count=-1)
            
        with self.assertRaises(ValueError):
            self.tester.ping(self.target_ip, count=0)
            
        with self.assertRaises(ValueError):
            self.tester.ping(self.target_ip, size=-1)
            
        with self.assertRaises(ValueError):
            self.tester.ping(self.target_ip, size=0)
            
        with self.assertRaises(ValueError):
            self.tester.ping(self.target_ip, interval=-1.0)
            
        with self.assertRaises(ValueError):
            self.tester.ping(self.target_ip, interval=0.0)
    
    @patch('src.network_tester.pythonping_ping')
    def test_ping_successful(self, mock_ping):
        """Test successful ping operation."""
        # Create mock responses - all successful
        mock_responses = [
            MockResponse(success=True, time_elapsed_ms=10.5),
            MockResponse(success=True, time_elapsed_ms=12.3),
            MockResponse(success=True, time_elapsed_ms=8.7),
            MockResponse(success=True, time_elapsed_ms=11.1)
        ]
        mock_ping.return_value = MockResponseList(mock_responses)
        
        result = self.tester.ping(self.target_ip, count=4, size=64, interval=1.0)
        
        # Verify ping was called with correct parameters
        mock_ping.assert_called_once_with(
            self.target_ip,
            count=4,
            size=64,
            interval=1.0,
            timeout=5.0
        )
        
        # Verify result
        self.assertIsInstance(result, PingResult)
        self.assertEqual(result.target_ip, self.target_ip)
        self.assertEqual(result.packets_sent, 4)
        self.assertEqual(result.packets_received, 4)
        self.assertEqual(result.packet_loss, 0.0)
        self.assertEqual(result.min_rtt, 8.7)
        self.assertEqual(result.max_rtt, 12.3)
        self.assertAlmostEqual(result.avg_rtt, 10.65, places=2)
        self.assertGreater(result.std_dev_rtt, 0)
    
    @patch('src.network_tester.pythonping_ping')
    def test_ping_partial_packet_loss(self, mock_ping):
        """Test ping with partial packet loss."""
        # Create mock responses - 2 successful, 2 failed
        mock_responses = [
            MockResponse(success=True, time_elapsed_ms=15.0),
            MockResponse(success=False, time_elapsed_ms=0.0),
            MockResponse(success=True, time_elapsed_ms=20.0),
            MockResponse(success=False, time_elapsed_ms=0.0)
        ]
        mock_ping.return_value = MockResponseList(mock_responses)
        
        result = self.tester.ping(self.target_ip, count=4)
        
        self.assertEqual(result.packets_sent, 4)
        self.assertEqual(result.packets_received, 2)
        self.assertEqual(result.packet_loss, 50.0)
        self.assertEqual(result.min_rtt, 15.0)
        self.assertEqual(result.max_rtt, 20.0)
        self.assertEqual(result.avg_rtt, 17.5)
    
    @patch('src.network_tester.pythonping_ping')
    def test_ping_complete_failure(self, mock_ping):
        """Test ping with complete failure (100% packet loss)."""
        # Create mock responses - all failed
        mock_responses = [
            MockResponse(success=False, time_elapsed_ms=0.0),
            MockResponse(success=False, time_elapsed_ms=0.0),
            MockResponse(success=False, time_elapsed_ms=0.0)
        ]
        mock_ping.return_value = MockResponseList(mock_responses)
        
        result = self.tester.ping(self.target_ip, count=3)
        
        self.assertEqual(result.packets_sent, 3)
        self.assertEqual(result.packets_received, 0)
        self.assertEqual(result.packet_loss, 100.0)
        self.assertEqual(result.min_rtt, 0.0)
        self.assertEqual(result.max_rtt, 0.0)
        self.assertEqual(result.avg_rtt, 0.0)
        self.assertEqual(result.std_dev_rtt, 0.0)
    
    @patch('src.network_tester.pythonping_ping')
    def test_ping_single_response(self, mock_ping):
        """Test ping with single response (std_dev should be 0)."""
        mock_responses = [MockResponse(success=True, time_elapsed_ms=15.5)]
        mock_ping.return_value = MockResponseList(mock_responses)
        
        result = self.tester.ping(self.target_ip, count=1)
        
        self.assertEqual(result.packets_received, 1)
        self.assertEqual(result.avg_rtt, 15.5)
        self.assertEqual(result.std_dev_rtt, 0.0)  # Single value has no std deviation
    
    @patch('src.network_tester.pythonping_ping')
    def test_ping_exception_handling(self, mock_ping):
        """Test ping exception handling."""
        mock_ping.side_effect = Exception("Network unreachable")
        
        result = self.tester.ping(self.target_ip, count=3)
        
        # Should return failed result instead of raising exception
        self.assertEqual(result.packets_sent, 3)
        self.assertEqual(result.packets_received, 0)
        self.assertEqual(result.packet_loss, 100.0)
        self.assertEqual(result.target_ip, self.target_ip)
    
    @patch('src.network_tester.pythonping_ping')
    def test_ping_custom_timeout(self, mock_ping):
        """Test ping with custom timeout parameter."""
        mock_responses = [MockResponse(success=True, time_elapsed_ms=10.0)]
        mock_ping.return_value = MockResponseList(mock_responses)
        
        self.tester.ping(self.target_ip, count=1, timeout=3.0)
        
        # Verify custom timeout was used
        mock_ping.assert_called_once_with(
            self.target_ip,
            count=1,
            size=32,
            interval=1.0,
            timeout=3.0
        )
    
    @patch.object(NetworkTester, 'ping')
    def test_ping_multiple_targets(self, mock_ping):
        """Test ping multiple targets."""
        # Mock ping results for different targets
        targets = ["8.8.8.8", "1.1.1.1", "192.168.1.1"]
        
        mock_results = [
            PingResult("8.8.8.8", 4, 4, 0.0, 10.0, 15.0, 12.5, 2.1, datetime.now()),
            PingResult("1.1.1.1", 4, 3, 25.0, 8.0, 20.0, 14.0, 6.0, datetime.now()),
            PingResult("192.168.1.1", 4, 0, 100.0, 0.0, 0.0, 0.0, 0.0, datetime.now())
        ]
        
        mock_ping.side_effect = mock_results
        
        results = self.tester.ping_multiple_targets(targets, count=4)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(mock_ping.call_count, 3)
        
        # Verify each target was pinged with correct parameters
        for i, target in enumerate(targets):
            mock_ping.assert_any_call(target, 4, 32, 1.0, None)
            self.assertEqual(results[i].target_ip, target)
    
    @patch.object(NetworkTester, 'ping')
    def test_ping_multiple_targets_with_exception(self, mock_ping):
        """Test ping multiple targets when one target raises exception."""
        targets = ["8.8.8.8", "invalid.host"]
        
        # First call succeeds, second raises exception
        mock_ping.side_effect = [
            PingResult("8.8.8.8", 4, 4, 0.0, 10.0, 15.0, 12.5, 2.1, datetime.now()),
            Exception("Host not found")
        ]
        
        results = self.tester.ping_multiple_targets(targets, count=4)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].target_ip, "8.8.8.8")
        self.assertEqual(results[0].packet_loss, 0.0)
        
        # Second result should be a failed result
        self.assertEqual(results[1].target_ip, "invalid.host")
        self.assertEqual(results[1].packet_loss, 100.0)
        self.assertEqual(results[1].packets_received, 0)
    
    @patch.object(NetworkTester, 'ping')
    def test_is_host_reachable_success(self, mock_ping):
        """Test is_host_reachable when host is reachable."""
        mock_ping.return_value = PingResult(
            self.target_ip, 3, 2, 33.3, 10.0, 15.0, 12.5, 3.5, datetime.now()
        )
        
        result = self.tester.is_host_reachable(self.target_ip)
        
        self.assertTrue(result)
        mock_ping.assert_called_once_with(self.target_ip, count=3, timeout=None)
    
    @patch.object(NetworkTester, 'ping')
    def test_is_host_reachable_failure(self, mock_ping):
        """Test is_host_reachable when host is unreachable."""
        mock_ping.return_value = PingResult(
            self.target_ip, 3, 0, 100.0, 0.0, 0.0, 0.0, 0.0, datetime.now()
        )
        
        result = self.tester.is_host_reachable(self.target_ip)
        
        self.assertFalse(result)
    
    @patch.object(NetworkTester, 'ping')
    def test_is_host_reachable_exception(self, mock_ping):
        """Test is_host_reachable when ping raises exception."""
        mock_ping.side_effect = Exception("Network error")
        
        result = self.tester.is_host_reachable(self.target_ip)
        
        self.assertFalse(result)
    
    def test_process_ping_results_calculations(self):
        """Test _process_ping_results statistics calculations."""
        mock_responses = [
            MockResponse(success=True, time_elapsed_ms=10.0),
            MockResponse(success=True, time_elapsed_ms=20.0),
            MockResponse(success=True, time_elapsed_ms=30.0),
            MockResponse(success=False, time_elapsed_ms=0.0)
        ]
        response_list = MockResponseList(mock_responses)
        
        result = self.tester._process_ping_results(self.target_ip, response_list, 4)
        
        self.assertEqual(result.packets_sent, 4)
        self.assertEqual(result.packets_received, 3)
        self.assertEqual(result.packet_loss, 25.0)
        self.assertEqual(result.min_rtt, 10.0)
        self.assertEqual(result.max_rtt, 30.0)
        self.assertEqual(result.avg_rtt, 20.0)
        
        # Calculate expected std dev manually
        rtts = [10.0, 20.0, 30.0]
        expected_std_dev = statistics.stdev(rtts)
        self.assertAlmostEqual(result.std_dev_rtt, expected_std_dev, places=2)


class TestIperfFunctionality(unittest.TestCase):
    """Test cases for iPerf3 functionality in NetworkTester."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = NetworkTester(timeout=5.0)
        self.server_ip = "192.168.1.100"
        self.server_port = 5201
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_tcp_upload_successful(self, mock_socket, mock_iperf_client):
        """Test successful iPerf3 TCP upload."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client and result
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        # Create successful TCP result
        result = MockIperfResult()
        result.sum_sent = MockIperfSumData(bytes=10000000, bits_per_second=80000000, retransmits=5)
        result.sum_received = MockIperfSumData(bytes=0, bits_per_second=0, retransmits=0)
        mock_client._result = result
        
        # Run test
        tcp_result = self.tester.iperf_tcp_upload(self.server_ip, self.server_port, duration=10)
        
        # Verify client configuration
        self.assertEqual(mock_client.server_hostname, self.server_ip)
        self.assertEqual(mock_client.port, self.server_port)
        self.assertEqual(mock_client.duration, 10)
        self.assertEqual(mock_client.protocol, 'tcp')
        self.assertFalse(mock_client.reverse)
        
        # Verify result
        self.assertIsInstance(tcp_result, IperfTcpResult)
        self.assertEqual(tcp_result.server_ip, self.server_ip)
        self.assertEqual(tcp_result.server_port, self.server_port)
        self.assertEqual(tcp_result.duration, 10)
        self.assertEqual(tcp_result.bytes_sent, 10000000)
        self.assertAlmostEqual(tcp_result.throughput_upload, 80.0, places=1)  # 80 Mbps
        self.assertEqual(tcp_result.throughput_download, 0.0)
        self.assertEqual(tcp_result.retransmits, 5)
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_tcp_download_successful(self, mock_socket, mock_iperf_client):
        """Test successful iPerf3 TCP download."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client and result
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        # Create successful TCP download result
        result = MockIperfResult()
        result.sum_sent = MockIperfSumData(bytes=15000000, bits_per_second=120000000, retransmits=3)
        result.sum_received = MockIperfSumData(bytes=0, bits_per_second=0, retransmits=0)
        mock_client._result = result
        
        # Run test
        tcp_result = self.tester.iperf_tcp_download(self.server_ip, self.server_port, duration=5)
        
        # Verify client configuration for reverse mode
        self.assertEqual(mock_client.server_hostname, self.server_ip)
        self.assertEqual(mock_client.port, self.server_port)
        self.assertEqual(mock_client.duration, 5)
        self.assertEqual(mock_client.protocol, 'tcp')
        self.assertTrue(mock_client.reverse)  # Download mode
        
        # Verify result - in download mode, sent data represents downloaded data
        self.assertIsInstance(tcp_result, IperfTcpResult)
        self.assertEqual(tcp_result.throughput_upload, 0.0)
        self.assertAlmostEqual(tcp_result.throughput_download, 120.0, places=1)  # 120 Mbps
        self.assertEqual(tcp_result.retransmits, 3)
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_udp_test_successful(self, mock_socket, mock_iperf_client):
        """Test successful iPerf3 UDP test."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client and result
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        # Create successful UDP result
        result = MockIperfResult()
        result.sum_sent = MockIperfSumData(
            bytes=5000000, bits_per_second=50000000, packets=5000
        )
        result.sum_received = MockIperfSumData(
            lost_packets=100, lost_percent=2.0, jitter_ms=1.5
        )
        mock_client._result = result
        
        # Run test
        udp_result = self.tester.iperf_udp_test(
            self.server_ip, self.server_port, duration=10, bandwidth="50M"
        )
        
        # Verify client configuration
        self.assertEqual(mock_client.server_hostname, self.server_ip)
        self.assertEqual(mock_client.port, self.server_port)
        self.assertEqual(mock_client.duration, 10)
        self.assertEqual(mock_client.protocol, 'udp')
        self.assertEqual(mock_client.bandwidth, "50M")
        
        # Verify result
        self.assertIsInstance(udp_result, IperfUdpResult)
        self.assertEqual(udp_result.server_ip, self.server_ip)
        self.assertEqual(udp_result.server_port, self.server_port)
        self.assertEqual(udp_result.duration, 10)
        self.assertEqual(udp_result.bytes_sent, 5000000)
        self.assertEqual(udp_result.packets_sent, 5000)
        self.assertEqual(udp_result.packets_lost, 100)
        self.assertEqual(udp_result.packet_loss, 2.0)
        self.assertEqual(udp_result.jitter, 1.5)
        self.assertAlmostEqual(udp_result.throughput, 50.0, places=1)  # 50 Mbps
    
    def test_iperf_tcp_upload_parameter_validation(self):
        """Test parameter validation for TCP upload."""
        with self.assertRaises(ValueError):
            self.tester.iperf_tcp_upload(self.server_ip, duration=-1)
        
        with self.assertRaises(ValueError):
            self.tester.iperf_tcp_upload(self.server_ip, parallel=0)
        
        with self.assertRaises(ValueError):
            self.tester.iperf_tcp_upload(self.server_ip, server_port=0)
        
        with self.assertRaises(ValueError):
            self.tester.iperf_tcp_upload(self.server_ip, server_port=70000)
    
    def test_iperf_udp_test_parameter_validation(self):
        """Test parameter validation for UDP test."""
        with self.assertRaises(ValueError):
            self.tester.iperf_udp_test(self.server_ip, duration=0)
        
        with self.assertRaises(ValueError):
            self.tester.iperf_udp_test(self.server_ip, server_port=-1)
        
        with self.assertRaises(ValueError):
            self.tester.iperf_udp_test(self.server_ip, packet_len=0)
    
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_server_unavailable_error(self, mock_socket):
        """Test server unavailability detection."""
        # Mock socket connection failure
        mock_socket.side_effect = ConnectionRefusedError("Connection refused")
        
        with self.assertRaises(IperfServerUnavailableError):
            self.tester._check_iperf_server_availability(self.server_ip, self.server_port, 5.0)
    
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_server_timeout_error(self, mock_socket):
        """Test server timeout detection."""
        # Mock socket timeout
        mock_socket.side_effect = socket.timeout("Connection timeout")
        
        with self.assertRaises(IperfServerUnavailableError):
            self.tester._check_iperf_server_availability(self.server_ip, self.server_port, 5.0)
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_test_with_error_result(self, mock_socket, mock_iperf_client):
        """Test handling of iperf3 result with error."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client with error result
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        result = MockIperfResult(error="Test failed")
        mock_client._result = result
        
        with self.assertRaises(IperfConnectionError):
            self.tester.iperf_tcp_upload(self.server_ip)
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_client_exception_handling(self, mock_socket, mock_iperf_client):
        """Test exception handling in iperf3 client."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client to raise exception
        mock_iperf_client.side_effect = Exception("Client creation failed")
        
        with self.assertRaises(IperfConnectionError):
            self.tester.iperf_tcp_upload(self.server_ip)
    
    @patch.object(NetworkTester, 'iperf_tcp_upload')
    @patch.object(NetworkTester, 'iperf_tcp_download')
    def test_iperf_tcp_bidirectional(self, mock_download, mock_upload):
        """Test bidirectional TCP test."""
        # Mock upload and download results
        upload_result = IperfTcpResult(
            server_ip=self.server_ip,
            server_port=self.server_port,
            duration=10,
            bytes_sent=5000000,
            bytes_received=0,
            throughput_upload=50.0,
            throughput_download=0.0,
            retransmits=2,
            timestamp=datetime.now()
        )
        
        download_result = IperfTcpResult(
            server_ip=self.server_ip,
            server_port=self.server_port,
            duration=10,
            bytes_sent=0,
            bytes_received=8000000,
            throughput_upload=0.0,
            throughput_download=80.0,
            retransmits=1,
            timestamp=datetime.now()
        )
        
        mock_upload.return_value = upload_result
        mock_download.return_value = download_result
        
        # Run bidirectional test
        result = self.tester.iperf_tcp_bidirectional(self.server_ip, duration=10)
        
        # Verify both methods were called
        mock_upload.assert_called_once_with(self.server_ip, self.server_port, 10, 1, None)
        mock_download.assert_called_once_with(self.server_ip, self.server_port, 10, 1, None)
        
        # Verify combined result
        self.assertIsInstance(result, IperfTcpResult)
        self.assertEqual(result.throughput_upload, 50.0)
        self.assertEqual(result.throughput_download, 80.0)
        self.assertEqual(result.retransmits, 3)  # Combined retransmits
        self.assertEqual(result.bytes_sent, 5000000)
        self.assertEqual(result.bytes_received, 8000000)
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_result_parsing_with_missing_attributes(self, mock_socket, mock_iperf_client):
        """Test parsing of iperf3 result with missing attributes."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client and result with minimal data
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        # Create result with missing attributes
        result = MockIperfResult()
        result.sum_sent = None
        result.sum_received = None
        mock_client._result = result
        
        # Run test
        tcp_result = self.tester.iperf_tcp_upload(self.server_ip)
        
        # Should handle missing attributes gracefully
        self.assertEqual(tcp_result.bytes_sent, 0)
        self.assertEqual(tcp_result.bytes_received, 0)
        self.assertEqual(tcp_result.throughput_upload, 0.0)
        self.assertEqual(tcp_result.retransmits, 0)
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection') 
    def test_iperf_result_parsing_exception(self, mock_socket, mock_iperf_client):
        """Test handling of parsing exceptions."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client that returns problematic result
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        # Create a result that will cause parsing issues
        result = MockIperfResult()
        # Add a sum_sent that will cause getattr to fail
        result.sum_sent = object()  # Object without expected attributes
        mock_client._result = result
        
        # Should not raise exception, but return zero values
        tcp_result = self.tester.iperf_tcp_upload(self.server_ip)
        
        self.assertEqual(tcp_result.bytes_sent, 0)
        self.assertEqual(tcp_result.throughput_upload, 0.0)

    @patch.object(NetworkTester, 'iperf_tcp_upload')
    def test_iperf_tcp_bidirectional_upload_failure(self, mock_upload):
        """Test bidirectional test when upload fails."""
        # Mock upload failure
        mock_upload.side_effect = IperfServerUnavailableError("Server unavailable")
        
        with self.assertRaises(IperfServerUnavailableError):
            self.tester.iperf_tcp_bidirectional(self.server_ip)
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_tcp_custom_timeout_setting(self, mock_socket, mock_iperf_client):
        """Test custom timeout setting in iperf3 client."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        result = MockIperfResult()
        result.sum_sent = MockIperfSumData(bytes=1000000, bits_per_second=10000000)
        result.sum_received = MockIperfSumData()
        mock_client._result = result
        
        # Run test with custom timeout
        self.tester.iperf_tcp_upload(self.server_ip, timeout=3.0)
        
        # Verify timeout was set in milliseconds
        self.assertEqual(mock_client.timeout, 3000)  # 3.0 seconds * 1000
    
    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_udp_custom_settings(self, mock_socket, mock_iperf_client):
        """Test UDP test with custom packet length and bandwidth."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        result = MockIperfResult()
        result.sum_sent = MockIperfSumData(bytes=2000000, bits_per_second=20000000, packets=1500)
        result.sum_received = MockIperfSumData(jitter_ms=2.5)
        mock_client._result = result
        
        # Run test with custom settings
        udp_result = self.tester.iperf_udp_test(
            self.server_ip, 
            bandwidth="20M", 
            packet_len=1400, 
            duration=15
        )
        
        # Verify client settings
        self.assertEqual(mock_client.bandwidth, "20M")
        self.assertEqual(mock_client.blksize, 1400)
        self.assertEqual(mock_client.duration, 15)
        
        # Verify result
        self.assertEqual(udp_result.duration, 15)
        self.assertAlmostEqual(udp_result.throughput, 20.0, places=1)
        self.assertEqual(udp_result.jitter, 2.5)

    @patch('src.network_tester.iperf3.Client')
    @patch('src.network_tester.socket.create_connection')
    def test_iperf_tcp_parallel_streams(self, mock_socket, mock_iperf_client):
        """Test TCP test with multiple parallel streams."""
        # Mock socket connection check
        mock_socket.return_value.close.return_value = None
        
        # Mock iperf3 client
        mock_client = MockIperfClient()
        mock_iperf_client.return_value = mock_client
        
        result = MockIperfResult()
        result.sum_sent = MockIperfSumData(bytes=20000000, bits_per_second=160000000, retransmits=10)
        result.sum_received = MockIperfSumData()
        mock_client._result = result
        
        # Run test with parallel streams
        tcp_result = self.tester.iperf_tcp_upload(self.server_ip, parallel=4)
        
        # Verify parallel streams setting
        self.assertEqual(mock_client.num_streams, 4)
        
        # Verify result
        self.assertAlmostEqual(tcp_result.throughput_upload, 160.0, places=1)
        self.assertEqual(tcp_result.retransmits, 10)

    def test_iperf_error_classes_inheritance(self):
        """Test that iperf error classes inherit correctly."""
        # Test inheritance
        self.assertTrue(issubclass(IperfServerUnavailableError, IperfError))
        self.assertTrue(issubclass(IperfConnectionError, IperfError))
        self.assertTrue(issubclass(IperfError, Exception))
        
        # Test instantiation
        server_error = IperfServerUnavailableError("Server down")
        connection_error = IperfConnectionError("Connection failed")
        
        self.assertIsInstance(server_error, IperfError)
        self.assertIsInstance(connection_error, IperfError)
        
        self.assertEqual(str(server_error), "Server down")
        self.assertEqual(str(connection_error), "Connection failed")


class TestPingStatistics(unittest.TestCase):
    """Test cases for PingStatistics utility class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.results = [
            PingResult("8.8.8.8", 4, 4, 0.0, 10.0, 15.0, 12.5, 2.1, datetime.now()),
            PingResult("1.1.1.1", 4, 3, 25.0, 8.0, 20.0, 14.0, 6.0, datetime.now()),
            PingResult("192.168.1.1", 4, 0, 100.0, 0.0, 0.0, 0.0, 0.0, datetime.now()),
            PingResult("192.168.1.254", 4, 2, 50.0, 5.0, 25.0, 15.0, 14.1, datetime.now())
        ]
    
    def test_calculate_aggregate_stats_normal(self):
        """Test aggregate statistics calculation with normal results."""
        stats = PingStatistics.calculate_aggregate_stats(self.results)
        
        self.assertEqual(stats["total_targets"], 4)
        self.assertEqual(stats["reachable_targets"], 3)  # 3 targets with packets_received > 0
        self.assertEqual(stats["unreachable_targets"], 1)
        
        # Calculate expected overall success rate
        total_sent = sum(r.packets_sent for r in self.results)  # 16
        total_received = sum(r.packets_received for r in self.results)  # 9
        expected_success_rate = (total_received / total_sent) * 100  # 56.25%
        
        self.assertAlmostEqual(stats["overall_success_rate"], expected_success_rate, places=2)
        self.assertAlmostEqual(stats["avg_packet_loss"], 43.75, places=2)  # 100 - 56.25
        
        # Verify RTT statistics (only from successful results)
        valid_results = [r for r in self.results if r.packets_received > 0]
        avg_rtts = [r.avg_rtt for r in valid_results]  # [12.5, 14.0, 15.0]
        expected_avg_rtt = statistics.mean(avg_rtts)  # 13.833...
        
        self.assertAlmostEqual(stats["avg_rtt"], expected_avg_rtt, places=2)
        self.assertEqual(stats["min_rtt_overall"], 5.0)  # min of all min_rtts
        self.assertEqual(stats["max_rtt_overall"], 25.0)  # max of all max_rtts
    
    def test_calculate_aggregate_stats_empty_list(self):
        """Test aggregate statistics with empty results list."""
        stats = PingStatistics.calculate_aggregate_stats([])
        
        self.assertEqual(stats, {})
    
    def test_calculate_aggregate_stats_all_failed(self):
        """Test aggregate statistics when all pings failed."""
        failed_results = [
            PingResult("192.168.1.1", 4, 0, 100.0, 0.0, 0.0, 0.0, 0.0, datetime.now()),
            PingResult("192.168.1.2", 3, 0, 100.0, 0.0, 0.0, 0.0, 0.0, datetime.now())
        ]
        
        stats = PingStatistics.calculate_aggregate_stats(failed_results)
        
        self.assertEqual(stats["total_targets"], 2)
        self.assertEqual(stats["reachable_targets"], 0)
        self.assertEqual(stats["unreachable_targets"], 2)
        self.assertEqual(stats["overall_success_rate"], 0.0)
        self.assertEqual(stats["avg_packet_loss"], 100.0)
        self.assertEqual(stats["avg_rtt"], 0.0)
        self.assertEqual(stats["min_rtt_overall"], 0.0)
        self.assertEqual(stats["max_rtt_overall"], 0.0)
    
    def test_calculate_aggregate_stats_single_result(self):
        """Test aggregate statistics with single result."""
        single_result = [self.results[0]]  # Only the successful 8.8.8.8 result
        
        stats = PingStatistics.calculate_aggregate_stats(single_result)
        
        self.assertEqual(stats["total_targets"], 1)
        self.assertEqual(stats["reachable_targets"], 1)
        self.assertEqual(stats["unreachable_targets"], 0)
        self.assertEqual(stats["overall_success_rate"], 100.0)  # 4/4 packets
        self.assertEqual(stats["avg_packet_loss"], 0.0)
        self.assertEqual(stats["avg_rtt"], 12.5)
        self.assertEqual(stats["min_rtt_overall"], 10.0)
        self.assertEqual(stats["max_rtt_overall"], 15.0)
        self.assertEqual(stats["rtt_std_dev"], 0.0)  # Single result has no std dev


if __name__ == "__main__":
    unittest.main()