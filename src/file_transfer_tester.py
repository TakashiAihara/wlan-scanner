"""File transfer performance testing utilities for SMB, FTP, and HTTP protocols."""

import os
import time
import tempfile
import logging
import statistics
from typing import Optional, List, Dict, Any, Tuple, Union
from pathlib import Path
from datetime import datetime
import ftplib
import http.client
import urllib.request
import urllib.parse
import socket

# Optional dependencies - import with graceful fallback
try:
    from smb.SMBConnection import SMBConnection
    from smb.base import SharedFile
    SMB_AVAILABLE = True
except ImportError:
    SMBConnection = None
    SharedFile = None
    SMB_AVAILABLE = False

from .models import FileTransferResult

logger = logging.getLogger(__name__)


class FileTransferError(Exception):
    """Base exception for file transfer related errors."""
    pass


class FileTransferConnectionError(FileTransferError):
    """Exception raised when connection to server fails."""
    pass


class FileTransferProtocolError(FileTransferError):
    """Exception raised when protocol-specific error occurs."""
    pass


class FileTransferTester:
    """
    File transfer performance tester supporting SMB, FTP, and HTTP protocols.
    
    This class creates test files of configurable sizes and measures transfer
    performance including speed, statistics, and handles errors gracefully.
    """
    
    def __init__(self, timeout: float = 30.0, temp_dir: Optional[str] = None):
        """
        Initialize FileTransferTester.
        
        Args:
            timeout: Default timeout for operations in seconds
            temp_dir: Custom temporary directory for test files
        """
        self.timeout = timeout
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self._created_files: List[str] = []
        self._test_data_cache: Dict[int, bytes] = {}
        
    def create_test_file(self, size_mb: float) -> str:
        """
        Create a test file of specified size.
        
        Args:
            size_mb: File size in megabytes
            
        Returns:
            str: Path to created test file
            
        Raises:
            FileTransferError: If file creation fails
        """
        try:
            size_bytes = int(size_mb * 1024 * 1024)
            
            # Generate test data if not cached
            if size_bytes not in self._test_data_cache:
                # Create repeating pattern for consistent data
                pattern = b'0123456789ABCDEF' * 64  # 1KB pattern
                chunks_needed = (size_bytes + len(pattern) - 1) // len(pattern)
                self._test_data_cache[size_bytes] = (pattern * chunks_needed)[:size_bytes]
            
            # Create temporary file
            fd, file_path = tempfile.mkstemp(
                suffix='.dat',
                prefix=f'test_{size_mb}MB_',
                dir=self.temp_dir
            )
            
            try:
                with os.fdopen(fd, 'wb') as f:
                    f.write(self._test_data_cache[size_bytes])
                    f.flush()
                    os.fsync(f.fileno())  # Ensure data is written to disk
                
                self._created_files.append(file_path)
                logger.debug(f"Created test file: {file_path} ({size_mb} MB)")
                return file_path
                
            except Exception:
                os.close(fd)  # Close if still open
                if os.path.exists(file_path):
                    os.unlink(file_path)
                raise
                
        except Exception as e:
            raise FileTransferError(f"Failed to create test file: {e}")
    
    def test_smb_transfer(
        self,
        server_address: str,
        share_name: str,
        file_size_mb: float,
        direction: str = "download",
        username: str = "",
        password: str = "",
        domain: str = "",
        port: int = 445,
        remote_file_path: str = "test_file.dat"
    ) -> FileTransferResult:
        """
        Test SMB file transfer performance.
        
        Args:
            server_address: SMB server address
            share_name: SMB share name
            file_size_mb: File size in megabytes
            direction: "upload" or "download"
            username: SMB username (empty for anonymous)
            password: SMB password
            domain: SMB domain
            port: SMB port (default 445)
            remote_file_path: Path within share for test file
            
        Returns:
            FileTransferResult: Transfer performance results
        """
        if not SMB_AVAILABLE:
            raise FileTransferError("SMB support not available. Install pysmb: pip install pysmb")
        
        local_file = None
        conn = None
        
        try:
            # Create test file for upload or prepare for download
            if direction.lower() == "upload":
                local_file = self.create_test_file(file_size_mb)
            elif direction.lower() == "download":
                local_file = tempfile.mktemp(
                    suffix='.dat',
                    prefix=f'download_{file_size_mb}MB_',
                    dir=self.temp_dir
                )
                self._created_files.append(local_file)
            else:
                raise ValueError(f"Invalid direction: {direction}. Must be 'upload' or 'download'")
            
            # Establish SMB connection
            conn = SMBConnection(
                username=username,
                password=password,
                my_name="client",
                remote_name="server",
                domain=domain,
                use_ntlm_v2=True
            )
            
            if not conn.connect(server_address, port, timeout=self.timeout):
                raise FileTransferConnectionError(f"Failed to connect to SMB server {server_address}:{port}")
            
            # Perform transfer and measure time
            start_time = time.perf_counter()
            
            if direction.lower() == "upload":
                with open(local_file, 'rb') as f:
                    conn.storeFile(share_name, remote_file_path, f)
                actual_size = os.path.getsize(local_file)
            else:  # download
                with open(local_file, 'wb') as f:
                    conn.retrieveFile(share_name, remote_file_path, f)
                actual_size = os.path.getsize(local_file)
            
            end_time = time.perf_counter()
            transfer_time = end_time - start_time
            transfer_speed = (actual_size / (1024 * 1024)) / transfer_time  # MB/s
            
            return FileTransferResult(
                server_address=server_address,
                file_size=actual_size,
                transfer_time=transfer_time,
                transfer_speed=transfer_speed,
                protocol="SMB",
                direction=direction.lower()
            )
            
        except Exception as e:
            if isinstance(e, (FileTransferError, FileTransferConnectionError)):
                raise
            raise FileTransferProtocolError(f"SMB transfer failed: {e}")
            
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    
    def test_ftp_transfer(
        self,
        server_address: str,
        file_size_mb: float,
        direction: str = "download",
        username: str = "anonymous",
        password: str = "anonymous@example.com",
        port: int = 21,
        remote_file_path: str = "test_file.dat",
        passive: bool = True
    ) -> FileTransferResult:
        """
        Test FTP file transfer performance.
        
        Args:
            server_address: FTP server address
            file_size_mb: File size in megabytes
            direction: "upload" or "download"
            username: FTP username
            password: FTP password
            port: FTP port (default 21)
            remote_file_path: Remote file path
            passive: Use passive mode
            
        Returns:
            FileTransferResult: Transfer performance results
        """
        local_file = None
        ftp = None
        
        try:
            # Create test file for upload or prepare for download
            if direction.lower() == "upload":
                local_file = self.create_test_file(file_size_mb)
            elif direction.lower() == "download":
                local_file = tempfile.mktemp(
                    suffix='.dat',
                    prefix=f'download_{file_size_mb}MB_',
                    dir=self.temp_dir
                )
                self._created_files.append(local_file)
            else:
                raise ValueError(f"Invalid direction: {direction}. Must be 'upload' or 'download'")
            
            # Establish FTP connection
            ftp = ftplib.FTP()
            ftp.connect(server_address, port, timeout=self.timeout)
            ftp.login(username, password)
            
            if passive:
                ftp.set_pasv(True)
            
            # Perform transfer and measure time
            start_time = time.perf_counter()
            
            if direction.lower() == "upload":
                with open(local_file, 'rb') as f:
                    ftp.storbinary(f'STOR {remote_file_path}', f)
                actual_size = os.path.getsize(local_file)
            else:  # download
                with open(local_file, 'wb') as f:
                    ftp.retrbinary(f'RETR {remote_file_path}', f.write)
                actual_size = os.path.getsize(local_file)
            
            end_time = time.perf_counter()
            transfer_time = end_time - start_time
            transfer_speed = (actual_size / (1024 * 1024)) / transfer_time  # MB/s
            
            return FileTransferResult(
                server_address=server_address,
                file_size=actual_size,
                transfer_time=transfer_time,
                transfer_speed=transfer_speed,
                protocol="FTP",
                direction=direction.lower()
            )
            
        except Exception as e:
            if isinstance(e, (FileTransferError, FileTransferConnectionError)):
                raise
            raise FileTransferProtocolError(f"FTP transfer failed: {e}")
            
        finally:
            if ftp:
                try:
                    ftp.quit()
                except Exception:
                    try:
                        ftp.close()
                    except Exception:
                        pass
    
    def test_http_transfer(
        self,
        server_address: str,
        file_size_mb: float,
        direction: str = "download",
        port: int = 80,
        remote_file_path: str = "/test_file.dat",
        upload_endpoint: str = "/upload",
        use_https: bool = False,
        headers: Optional[Dict[str, str]] = None
    ) -> FileTransferResult:
        """
        Test HTTP/HTTPS file transfer performance.
        
        Args:
            server_address: HTTP server address
            file_size_mb: File size in megabytes
            direction: "upload" or "download"
            port: HTTP port (default 80, 443 for HTTPS)
            remote_file_path: Remote file path for download
            upload_endpoint: Endpoint for upload
            use_https: Use HTTPS instead of HTTP
            headers: Additional HTTP headers
            
        Returns:
            FileTransferResult: Transfer performance results
        """
        local_file = None
        
        try:
            if headers is None:
                headers = {}
            
            # Adjust port for HTTPS if not explicitly set
            if use_https and port == 80:
                port = 443
            
            # Create test file for upload or prepare for download
            if direction.lower() == "upload":
                local_file = self.create_test_file(file_size_mb)
            elif direction.lower() == "download":
                local_file = tempfile.mktemp(
                    suffix='.dat',
                    prefix=f'download_{file_size_mb}MB_',
                    dir=self.temp_dir
                )
                self._created_files.append(local_file)
            else:
                raise ValueError(f"Invalid direction: {direction}. Must be 'upload' or 'download'")
            
            # Perform transfer and measure time
            start_time = time.perf_counter()
            
            if direction.lower() == "upload":
                # HTTP upload using POST with file data
                with open(local_file, 'rb') as f:
                    file_data = f.read()
                
                if use_https:
                    conn = http.client.HTTPSConnection(server_address, port, timeout=self.timeout)
                else:
                    conn = http.client.HTTPConnection(server_address, port, timeout=self.timeout)
                
                headers['Content-Type'] = 'application/octet-stream'
                headers['Content-Length'] = str(len(file_data))
                
                conn.request('POST', upload_endpoint, body=file_data, headers=headers)
                response = conn.getresponse()
                
                if response.status not in (200, 201, 202):
                    raise FileTransferProtocolError(f"HTTP upload failed with status {response.status}")
                
                actual_size = len(file_data)
                conn.close()
                
            else:  # download
                url = f"{'https' if use_https else 'http'}://{server_address}:{port}{remote_file_path}"
                
                request = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    with open(local_file, 'wb') as f:
                        f.write(response.read())
                
                actual_size = os.path.getsize(local_file)
            
            end_time = time.perf_counter()
            transfer_time = end_time - start_time
            transfer_speed = (actual_size / (1024 * 1024)) / transfer_time  # MB/s
            
            protocol = "HTTPS" if use_https else "HTTP"
            
            return FileTransferResult(
                server_address=server_address,
                file_size=actual_size,
                transfer_time=transfer_time,
                transfer_speed=transfer_speed,
                protocol=protocol,
                direction=direction.lower()
            )
            
        except Exception as e:
            if isinstance(e, (FileTransferError, FileTransferConnectionError)):
                raise
            raise FileTransferProtocolError(f"HTTP transfer failed: {e}")
    
    def run_multiple_transfers(
        self,
        transfer_func: callable,
        iterations: int = 3,
        **kwargs
    ) -> Tuple[List[FileTransferResult], Dict[str, float]]:
        """
        Run multiple transfer tests and calculate statistics.
        
        Args:
            transfer_func: Transfer function to call (test_smb_transfer, etc.)
            iterations: Number of iterations to run
            **kwargs: Arguments to pass to transfer function
            
        Returns:
            Tuple of (results_list, statistics_dict)
        """
        if iterations < 1:
            raise ValueError("Iterations must be at least 1")
        
        results = []
        errors = []
        
        for i in range(iterations):
            try:
                logger.debug(f"Running transfer iteration {i + 1}/{iterations}")
                result = transfer_func(**kwargs)
                results.append(result)
            except Exception as e:
                errors.append(str(e))
                logger.warning(f"Transfer iteration {i + 1} failed: {e}")
        
        if not results:
            raise FileTransferError(f"All {iterations} transfer attempts failed. Errors: {errors}")
        
        # Calculate statistics
        speeds = [r.transfer_speed for r in results]
        times = [r.transfer_time for r in results]
        
        stats = {
            'iterations_completed': len(results),
            'iterations_failed': len(errors),
            'avg_speed_mb_s': statistics.mean(speeds),
            'min_speed_mb_s': min(speeds),
            'max_speed_mb_s': max(speeds),
            'std_dev_speed_mb_s': statistics.stdev(speeds) if len(speeds) > 1 else 0.0,
            'avg_time_s': statistics.mean(times),
            'min_time_s': min(times),
            'max_time_s': max(times),
            'speed_variation_percent': ((max(speeds) - min(speeds)) / statistics.mean(speeds) * 100) if speeds else 0.0
        }
        
        return results, stats
    
    def cleanup(self) -> None:
        """Clean up all created test files."""
        cleaned_count = 0
        errors = []
        
        for file_path in self._created_files[:]:  # Create a copy to iterate
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
                    cleaned_count += 1
                self._created_files.remove(file_path)
            except Exception as e:
                errors.append(f"Failed to delete {file_path}: {e}")
        
        # Clear cache
        self._test_data_cache.clear()
        
        if errors:
            logger.warning(f"Cleanup completed with errors: {errors}")
        else:
            logger.debug(f"Cleanup completed successfully, removed {cleaned_count} files")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        self.cleanup()