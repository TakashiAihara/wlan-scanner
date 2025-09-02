"""Network testing utilities for ping and network diagnostics."""

import statistics
from typing import List, Optional
from pythonping import ping as pythonping_ping
from pythonping.executor import Response, ResponseList
from datetime import datetime
import logging

from .models import PingResult

logger = logging.getLogger(__name__)


class NetworkTester:
    """Network testing class with ping functionality."""
    
    def __init__(self, timeout: float = 10.0):
        """
        Initialize NetworkTester.
        
        Args:
            timeout: Default timeout for network operations in seconds
        """
        self.timeout = timeout
    
    def ping(
        self,
        target: str,
        count: int = 4,
        size: int = 32,
        interval: float = 1.0,
        timeout: Optional[float] = None
    ) -> PingResult:
        """
        Perform ping test to target host.
        
        Args:
            target: Target IP address or hostname
            count: Number of ping packets to send
            size: Size of ping packets in bytes
            interval: Interval between ping packets in seconds
            timeout: Timeout for individual ping in seconds
            
        Returns:
            PingResult with ping statistics
            
        Raises:
            ValueError: If invalid parameters are provided
        """
        if count <= 0:
            raise ValueError("Count must be positive")
        if size <= 0:
            raise ValueError("Size must be positive")
        if interval <= 0:
            raise ValueError("Interval must be positive")
        
        ping_timeout = timeout if timeout is not None else self.timeout
        
        logger.info(f"Starting ping test to {target} (count={count}, size={size}, interval={interval})")
        
        try:
            # Perform ping using pythonping
            response_list: ResponseList = pythonping_ping(
                target,
                count=count,
                size=size,
                interval=interval,
                timeout=ping_timeout
            )
            
            return self._process_ping_results(target, response_list, count)
            
        except Exception as e:
            logger.error(f"Ping to {target} failed: {e}")
            # Return result indicating complete failure
            return PingResult(
                target_ip=target,
                packets_sent=count,
                packets_received=0,
                packet_loss=100.0,
                min_rtt=0.0,
                max_rtt=0.0,
                avg_rtt=0.0,
                std_dev_rtt=0.0,
                timestamp=datetime.now()
            )
    
    def _process_ping_results(self, target: str, response_list: ResponseList, expected_count: int) -> PingResult:
        """
        Process ping results and calculate statistics.
        
        Args:
            target: Target IP address
            response_list: ResponseList from pythonping
            expected_count: Expected number of ping packets
            
        Returns:
            PingResult with calculated statistics
        """
        # Extract successful response times
        rtts: List[float] = []
        packets_received = 0
        
        for response in response_list:
            if response.success:
                rtts.append(response.time_elapsed_ms)
                packets_received += 1
        
        packets_sent = expected_count
        packet_loss = ((packets_sent - packets_received) / packets_sent) * 100 if packets_sent > 0 else 100.0
        
        # Calculate statistics
        if rtts:
            min_rtt = min(rtts)
            max_rtt = max(rtts)
            avg_rtt = statistics.mean(rtts)
            std_dev_rtt = statistics.stdev(rtts) if len(rtts) > 1 else 0.0
        else:
            min_rtt = max_rtt = avg_rtt = std_dev_rtt = 0.0
        
        logger.info(
            f"Ping to {target} completed: {packets_received}/{packets_sent} packets, "
            f"{packet_loss:.1f}% loss, avg RTT: {avg_rtt:.2f}ms"
        )
        
        return PingResult(
            target_ip=target,
            packets_sent=packets_sent,
            packets_received=packets_received,
            packet_loss=packet_loss,
            min_rtt=min_rtt,
            max_rtt=max_rtt,
            avg_rtt=avg_rtt,
            std_dev_rtt=std_dev_rtt,
            timestamp=datetime.now()
        )
    
    def ping_multiple_targets(
        self,
        targets: List[str],
        count: int = 4,
        size: int = 32,
        interval: float = 1.0,
        timeout: Optional[float] = None
    ) -> List[PingResult]:
        """
        Perform ping tests to multiple targets.
        
        Args:
            targets: List of target IP addresses or hostnames
            count: Number of ping packets to send per target
            size: Size of ping packets in bytes
            interval: Interval between ping packets in seconds
            timeout: Timeout for individual ping in seconds
            
        Returns:
            List of PingResult objects, one per target
        """
        results = []
        
        for target in targets:
            try:
                result = self.ping(target, count, size, interval, timeout)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to ping {target}: {e}")
                # Add failed result
                results.append(PingResult(
                    target_ip=target,
                    packets_sent=count,
                    packets_received=0,
                    packet_loss=100.0,
                    min_rtt=0.0,
                    max_rtt=0.0,
                    avg_rtt=0.0,
                    std_dev_rtt=0.0,
                    timestamp=datetime.now()
                ))
        
        return results
    
    def is_host_reachable(
        self,
        target: str,
        count: int = 3,
        timeout: Optional[float] = None
    ) -> bool:
        """
        Check if host is reachable with a simple ping test.
        
        Args:
            target: Target IP address or hostname
            count: Number of ping packets to send
            timeout: Timeout for individual ping in seconds
            
        Returns:
            True if host is reachable (at least one ping succeeds), False otherwise
        """
        try:
            result = self.ping(target, count=count, timeout=timeout)
            return result.packets_received > 0
        except Exception:
            return False


class PingStatistics:
    """Utility class for calculating ping statistics from multiple results."""
    
    @staticmethod
    def calculate_aggregate_stats(results: List[PingResult]) -> dict:
        """
        Calculate aggregate statistics from multiple ping results.
        
        Args:
            results: List of PingResult objects
            
        Returns:
            Dictionary containing aggregate statistics
        """
        if not results:
            return {}
        
        # Filter out results with no successful pings
        valid_results = [r for r in results if r.packets_received > 0]
        
        if not valid_results:
            return {
                "total_targets": len(results),
                "reachable_targets": 0,
                "unreachable_targets": len(results),
                "overall_success_rate": 0.0,
                "avg_packet_loss": 100.0,
                "avg_rtt": 0.0,
                "min_rtt_overall": 0.0,
                "max_rtt_overall": 0.0
            }
        
        # Calculate aggregate statistics
        total_packets_sent = sum(r.packets_sent for r in results)
        total_packets_received = sum(r.packets_received for r in results)
        overall_packet_loss = ((total_packets_sent - total_packets_received) / total_packets_sent * 100) if total_packets_sent > 0 else 100.0
        
        avg_rtts = [r.avg_rtt for r in valid_results if r.avg_rtt > 0]
        min_rtts = [r.min_rtt for r in valid_results if r.min_rtt > 0]
        max_rtts = [r.max_rtt for r in valid_results if r.max_rtt > 0]
        
        return {
            "total_targets": len(results),
            "reachable_targets": len(valid_results),
            "unreachable_targets": len(results) - len(valid_results),
            "overall_success_rate": (total_packets_received / total_packets_sent * 100) if total_packets_sent > 0 else 0.0,
            "avg_packet_loss": overall_packet_loss,
            "avg_rtt": statistics.mean(avg_rtts) if avg_rtts else 0.0,
            "min_rtt_overall": min(min_rtts) if min_rtts else 0.0,
            "max_rtt_overall": max(max_rtts) if max_rtts else 0.0,
            "rtt_std_dev": statistics.stdev(avg_rtts) if len(avg_rtts) > 1 else 0.0
        }