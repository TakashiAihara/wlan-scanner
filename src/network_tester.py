"""Network testing utilities for ping and network diagnostics."""

import statistics
from typing import List, Optional, Union
from pythonping import ping as pythonping_ping
from pythonping.executor import Response, ResponseList
from datetime import datetime
import logging
import iperf3
import socket
import errno

from .models import PingResult, IperfTcpResult, IperfUdpResult

logger = logging.getLogger(__name__)


class IperfError(Exception):
    """Base exception for iPerf3 related errors."""
    pass


class IperfServerUnavailableError(IperfError):
    """Exception raised when iPerf3 server is unavailable."""
    pass


class IperfConnectionError(IperfError):
    """Exception raised when iPerf3 connection fails."""
    pass


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

    def iperf_tcp_upload(
        self,
        server_ip: str,
        server_port: int = 5201,
        duration: int = 10,
        parallel: int = 1,
        timeout: Optional[float] = None
    ) -> IperfTcpResult:
        """
        Perform TCP upload throughput test using iPerf3.
        
        Args:
            server_ip: iPerf3 server IP address
            server_port: iPerf3 server port
            duration: Test duration in seconds
            parallel: Number of parallel connections
            timeout: Connection timeout in seconds
            
        Returns:
            IperfTcpResult with upload throughput data
            
        Raises:
            IperfServerUnavailableError: If server is unreachable
            IperfConnectionError: If connection fails
            ValueError: If invalid parameters are provided
        """
        if duration <= 0:
            raise ValueError("Duration must be positive")
        if parallel <= 0:
            raise ValueError("Parallel connections must be positive")
        if server_port <= 0 or server_port > 65535:
            raise ValueError("Port must be between 1 and 65535")
        
        test_timeout = timeout if timeout is not None else self.timeout
        
        logger.info(f"Starting iPerf3 TCP upload test to {server_ip}:{server_port} "
                   f"(duration={duration}s, parallel={parallel})")
        
        try:
            client = iperf3.Client()
            client.server_hostname = server_ip
            client.port = server_port
            client.duration = duration
            client.num_streams = parallel
            client.reverse = False  # Upload (client -> server)
            
            # Skip server availability check to avoid connection conflicts
            
            # Run the test
            result = client.run()
            
            if result.error:
                raise IperfConnectionError(f"iPerf3 test failed: {result.error}")
            
            return self._parse_iperf_tcp_result(server_ip, server_port, duration, result, 'upload')
            
        except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError) as e:
            logger.error(f"iPerf3 TCP upload to {server_ip}:{server_port} failed: {e}")
            if isinstance(e, (ConnectionRefusedError, OSError)) and e.errno in [errno.ECONNREFUSED, errno.EHOSTUNREACH]:
                raise IperfServerUnavailableError(f"iPerf3 server {server_ip}:{server_port} is unavailable")
            else:
                raise IperfConnectionError(f"Failed to connect to iPerf3 server: {e}")
        except Exception as e:
            logger.error(f"iPerf3 TCP upload test failed: {e}")
            raise IperfConnectionError(f"iPerf3 test failed: {e}")

    def iperf_tcp_download(
        self,
        server_ip: str,
        server_port: int = 5201,
        duration: int = 10,
        parallel: int = 1,
        timeout: Optional[float] = None
    ) -> IperfTcpResult:
        """
        Perform TCP download throughput test using iPerf3.
        
        Args:
            server_ip: iPerf3 server IP address
            server_port: iPerf3 server port
            duration: Test duration in seconds
            parallel: Number of parallel connections
            timeout: Connection timeout in seconds
            
        Returns:
            IperfTcpResult with download throughput data
            
        Raises:
            IperfServerUnavailableError: If server is unreachable
            IperfConnectionError: If connection fails
            ValueError: If invalid parameters are provided
        """
        if duration <= 0:
            raise ValueError("Duration must be positive")
        if parallel <= 0:
            raise ValueError("Parallel connections must be positive")
        if server_port <= 0 or server_port > 65535:
            raise ValueError("Port must be between 1 and 65535")
        
        test_timeout = timeout if timeout is not None else self.timeout
        
        logger.info(f"Starting iPerf3 TCP download test to {server_ip}:{server_port} "
                   f"(duration={duration}s, parallel={parallel})")
        
        try:
            client = iperf3.Client()
            client.server_hostname = server_ip
            client.port = server_port
            client.duration = duration
            client.num_streams = parallel
            client.reverse = True  # Download (server -> client)
            
            # Skip server availability check to avoid connection conflicts
            
            # Run the test
            result = client.run()
            
            if result.error:
                raise IperfConnectionError(f"iPerf3 test failed: {result.error}")
            
            return self._parse_iperf_tcp_result(server_ip, server_port, duration, result, 'download')
            
        except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError) as e:
            logger.error(f"iPerf3 TCP download to {server_ip}:{server_port} failed: {e}")
            if isinstance(e, (ConnectionRefusedError, OSError)) and e.errno in [errno.ECONNREFUSED, errno.EHOSTUNREACH]:
                raise IperfServerUnavailableError(f"iPerf3 server {server_ip}:{server_port} is unavailable")
            else:
                raise IperfConnectionError(f"Failed to connect to iPerf3 server: {e}")
        except Exception as e:
            logger.error(f"iPerf3 TCP download test failed: {e}")
            raise IperfConnectionError(f"iPerf3 test failed: {e}")

    def iperf_tcp_bidirectional(
        self,
        server_ip: str,
        server_port: int = 5201,
        duration: int = 10,
        parallel: int = 1,
        timeout: Optional[float] = None
    ) -> IperfTcpResult:
        """
        Perform bidirectional TCP throughput test using iPerf3.
        
        Args:
            server_ip: iPerf3 server IP address
            server_port: iPerf3 server port
            duration: Test duration in seconds
            parallel: Number of parallel connections
            timeout: Connection timeout in seconds
            
        Returns:
            IperfTcpResult with both upload and download throughput data
            
        Raises:
            IperfServerUnavailableError: If server is unreachable
            IperfConnectionError: If connection fails
            ValueError: If invalid parameters are provided
        """
        logger.info(f"Starting bidirectional iPerf3 TCP test to {server_ip}:{server_port}")
        
        try:
            upload_result = self.iperf_tcp_upload(server_ip, server_port, duration, parallel, timeout)
            download_result = self.iperf_tcp_download(server_ip, server_port, duration, parallel, timeout)
            
            # Combine results
            return IperfTcpResult(
                server_ip=server_ip,
                server_port=server_port,
                duration=duration,
                bytes_sent=upload_result.bytes_sent + download_result.bytes_sent,
                bytes_received=upload_result.bytes_received + download_result.bytes_received,
                throughput_upload=upload_result.throughput_upload,
                throughput_download=download_result.throughput_download,
                retransmits=upload_result.retransmits + download_result.retransmits,
                timestamp=datetime.now()
            )
            
        except (IperfServerUnavailableError, IperfConnectionError):
            raise
        except Exception as e:
            logger.error(f"Bidirectional iPerf3 TCP test failed: {e}")
            raise IperfConnectionError(f"Bidirectional test failed: {e}")

    def iperf_udp_test(
        self,
        server_ip: str,
        server_port: int = 5201,
        duration: int = 10,
        bandwidth: str = "10M",
        packet_len: int = 1460,
        timeout: Optional[float] = None
    ) -> IperfUdpResult:
        """
        Perform UDP throughput and loss test using iPerf3.
        
        Args:
            server_ip: iPerf3 server IP address
            server_port: iPerf3 server port
            duration: Test duration in seconds
            bandwidth: Target bandwidth (e.g., "10M", "1G")
            packet_len: UDP packet length in bytes
            timeout: Connection timeout in seconds
            
        Returns:
            IperfUdpResult with UDP throughput, loss, and jitter data
            
        Raises:
            IperfServerUnavailableError: If server is unreachable
            IperfConnectionError: If connection fails
            ValueError: If invalid parameters are provided
        """
        if duration <= 0:
            raise ValueError("Duration must be positive")
        if server_port <= 0 or server_port > 65535:
            raise ValueError("Port must be between 1 and 65535")
        if packet_len <= 0:
            raise ValueError("Packet length must be positive")
        
        test_timeout = timeout if timeout is not None else self.timeout
        
        logger.info(f"Starting iPerf3 UDP test to {server_ip}:{server_port} "
                   f"(duration={duration}s, bandwidth={bandwidth}, packet_len={packet_len})")
        
        try:
            client = iperf3.Client()
            client.server_hostname = server_ip
            client.port = server_port
            client.duration = duration
            client.protocol = 'udp'
            client.bandwidth = bandwidth
            client.blksize = packet_len
            
            # Skip server availability check to avoid connection conflicts
            
            # Run the test
            result = client.run()
            
            if result.error:
                raise IperfConnectionError(f"iPerf3 UDP test failed: {result.error}")
            
            return self._parse_iperf_udp_result(server_ip, server_port, duration, result)
            
        except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError) as e:
            logger.error(f"iPerf3 UDP test to {server_ip}:{server_port} failed: {e}")
            if isinstance(e, (ConnectionRefusedError, OSError)) and e.errno in [errno.ECONNREFUSED, errno.EHOSTUNREACH]:
                raise IperfServerUnavailableError(f"iPerf3 server {server_ip}:{server_port} is unavailable")
            else:
                raise IperfConnectionError(f"Failed to connect to iPerf3 server: {e}")
        except Exception as e:
            logger.error(f"iPerf3 UDP test failed: {e}")
            raise IperfConnectionError(f"iPerf3 UDP test failed: {e}")

    def _check_iperf_server_availability(self, server_ip: str, server_port: int, timeout: float) -> None:
        """
        Check if iPerf3 server is available by attempting a socket connection.
        
        Args:
            server_ip: iPerf3 server IP address
            server_port: iPerf3 server port
            timeout: Connection timeout in seconds
            
        Raises:
            IperfServerUnavailableError: If server is not reachable
        """
        try:
            sock = socket.create_connection((server_ip, server_port), timeout=timeout)
            sock.close()
        except (socket.timeout, socket.gaierror, ConnectionRefusedError, OSError) as e:
            logger.error(f"iPerf3 server availability check failed: {e}")
            raise IperfServerUnavailableError(
                f"iPerf3 server {server_ip}:{server_port} is unavailable: {e}"
            )

    def _parse_iperf_tcp_result(
        self,
        server_ip: str,
        server_port: int,
        duration: float,
        result,
        direction: str
    ) -> IperfTcpResult:
        """
        Parse iPerf3 TCP test result and create IperfTcpResult object.
        
        Args:
            server_ip: iPerf3 server IP address
            server_port: iPerf3 server port
            duration: Test duration in seconds
            result: iPerf3 result object
            direction: Test direction ('upload', 'download', or 'bidirectional')
            
        Returns:
            IperfTcpResult with parsed data
        """
        try:
            # Get data directly from result
            bytes_sent = getattr(result, 'sent_bytes', 0)
            bytes_received = getattr(result, 'received_bytes', 0)
            throughput_sent_bps = getattr(result, 'sent_bps', 0)
            throughput_received_bps = getattr(result, 'received_bps', 0)
            total_retransmits = getattr(result, 'retransmits', 0)

            # Convert bits per second to Mbps and set based on direction
            if direction == 'upload':
                throughput_upload = throughput_sent_bps / 1_000_000
                throughput_download = 0.0
            elif direction == 'download':
                throughput_upload = 0.0
                throughput_download = throughput_sent_bps / 1_000_000  # In reverse mode, sent is actually download
            else:  # bidirectional
                throughput_upload = throughput_sent_bps / 1_000_000
                throughput_download = throughput_received_bps / 1_000_000

            logger.info(f"iPerf3 TCP {direction} completed: "
                       f"Upload: {throughput_upload:.2f} Mbps, "
                       f"Download: {throughput_download:.2f} Mbps, "
                       f"Retransmits: {total_retransmits}")

            return IperfTcpResult(
                server_ip=server_ip,
                server_port=server_port,
                duration=duration,
                bytes_sent=bytes_sent,
                bytes_received=bytes_received,
                throughput_upload=throughput_upload,
                throughput_download=throughput_download,
                retransmits=total_retransmits,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Failed to parse iPerf3 TCP result: {e}")
            # Return a result with zero values if parsing fails
            return IperfTcpResult(
                server_ip=server_ip,
                server_port=server_port,
                duration=duration,
                bytes_sent=0,
                bytes_received=0,
                throughput_upload=0.0,
                throughput_download=0.0,
                retransmits=0,
                timestamp=datetime.now()
            )

    def _parse_iperf_udp_result(
        self,
        server_ip: str,
        server_port: int,
        duration: float,
        result
    ) -> IperfUdpResult:
        """
        Parse iPerf3 UDP test result and create IperfUdpResult object.
        
        Args:
            server_ip: iPerf3 server IP address
            server_port: iPerf3 server port
            duration: Test duration in seconds
            result: iPerf3 result object
            
        Returns:
            IperfUdpResult with parsed data
        """
        try:
            # Get sent data
            if hasattr(result, 'sum_sent') and result.sum_sent:
                bytes_sent = getattr(result.sum_sent, 'bytes', 0)
                packets_sent = getattr(result.sum_sent, 'packets', 0)
                throughput_bps = getattr(result.sum_sent, 'bits_per_second', 0)
            else:
                bytes_sent = 0
                packets_sent = 0
                throughput_bps = 0

            # Get received data (server-side statistics)
            if hasattr(result, 'sum_received') and result.sum_received:
                packets_lost = getattr(result.sum_received, 'lost_packets', 0)
                packet_loss_percent = getattr(result.sum_received, 'lost_percent', 0.0)
                jitter_ms = getattr(result.sum_received, 'jitter_ms', 0.0)
            else:
                packets_lost = 0
                packet_loss_percent = 0.0
                jitter_ms = 0.0

            # Convert bits per second to Mbps
            throughput_mbps = throughput_bps / 1_000_000

            logger.info(f"iPerf3 UDP completed: "
                       f"Throughput: {throughput_mbps:.2f} Mbps, "
                       f"Packet Loss: {packet_loss_percent:.2f}%, "
                       f"Jitter: {jitter_ms:.2f} ms")

            return IperfUdpResult(
                server_ip=server_ip,
                server_port=server_port,
                duration=duration,
                bytes_sent=bytes_sent,
                packets_sent=packets_sent,
                packets_lost=packets_lost,
                packet_loss=packet_loss_percent,
                jitter=jitter_ms,
                throughput=throughput_mbps,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Failed to parse iPerf3 UDP result: {e}")
            # Return a result with zero values if parsing fails
            return IperfUdpResult(
                server_ip=server_ip,
                server_port=server_port,
                duration=duration,
                bytes_sent=0,
                packets_sent=0,
                packets_lost=0,
                packet_loss=0.0,
                jitter=0.0,
                throughput=0.0,
                timestamp=datetime.now()
            )


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