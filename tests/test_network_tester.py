"""Comprehensive unit tests for NetworkTester class."""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import statistics

from src.network_tester import NetworkTester, PingStatistics
from src.models import PingResult
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