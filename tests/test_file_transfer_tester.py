"""Comprehensive unit tests for FileTransferTester with mocking."""

import unittest
from unittest.mock import Mock, patch, mock_open, MagicMock, call
import tempfile
import os
from datetime import datetime
from io import BytesIO

from src.file_transfer_tester import (
    FileTransferTester, FileTransferError, FileTransferConnectionError,
    FileTransferProtocolError, SMB_AVAILABLE
)
from src.models import FileTransferResult


class TestFileTransferTester(unittest.TestCase):
    """Test FileTransferTester basic functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = FileTransferTester(timeout=30.0)
    
    def tearDown(self):
        """Clean up after tests."""
        self.tester.cleanup()
    
    def test_init_default(self):
        """Test default initialization."""
        tester = FileTransferTester()
        self.assertEqual(tester.timeout, 30.0)
        self.assertEqual(tester.temp_dir, tempfile.gettempdir())
        self.assertEqual(tester._created_files, [])
        self.assertEqual(tester._test_data_cache, {})
    
    def test_init_custom(self):
        """Test custom initialization."""
        custom_dir = "/tmp/custom"
        tester = FileTransferTester(timeout=60.0, temp_dir=custom_dir)
        self.assertEqual(tester.timeout, 60.0)
        self.assertEqual(tester.temp_dir, custom_dir)
    
    @patch('tempfile.mkstemp')
    @patch('os.fdopen')
    @patch('os.fsync')
    def test_create_test_file_success(self, mock_fsync, mock_fdopen, mock_mkstemp):
        """Test successful test file creation."""
        # Setup mocks
        mock_fd = 5
        mock_path = "/tmp/test_1.0MB_abc123.dat"
        mock_mkstemp.return_value = (mock_fd, mock_path)
        
        mock_file = mock_open()
        mock_fdopen.return_value = mock_file.return_value
        
        # Test
        result_path = self.tester.create_test_file(1.0)
        
        # Verify
        self.assertEqual(result_path, mock_path)
        self.assertIn(mock_path, self.tester._created_files)
        mock_mkstemp.assert_called_once()
        mock_fdopen.assert_called_once_with(mock_fd, 'wb')
        mock_file.return_value.write.assert_called_once()
        mock_file.return_value.flush.assert_called_once()
        mock_fsync.assert_called_once()
    
    @patch('tempfile.mkstemp')
    @patch('os.fdopen')
    def test_create_test_file_write_error(self, mock_fdopen, mock_mkstemp):
        """Test file creation with write error."""
        # Setup mocks
        mock_fd = 5
        mock_path = "/tmp/test_1.0MB_abc123.dat"
        mock_mkstemp.return_value = (mock_fd, mock_path)
        
        mock_file = mock_open()
        mock_file.return_value.write.side_effect = IOError("Write failed")
        mock_fdopen.return_value = mock_file.return_value
        
        with patch('os.close') as mock_close, \
             patch('os.path.exists', return_value=True), \
             patch('os.unlink') as mock_unlink:
            
            # Test
            with self.assertRaises(FileTransferError):
                self.tester.create_test_file(1.0)
            
            # Verify cleanup
            mock_close.assert_called_once_with(mock_fd)
            mock_unlink.assert_called_once_with(mock_path)
    
    @patch('tempfile.mkstemp')
    def test_create_test_file_mkstemp_error(self, mock_mkstemp):
        """Test file creation with mkstemp error."""
        mock_mkstemp.side_effect = OSError("Cannot create temp file")
        
        with self.assertRaises(FileTransferError) as cm:
            self.tester.create_test_file(1.0)
        
        self.assertIn("Failed to create test file", str(cm.exception))
    
    def test_create_test_file_caching(self):
        """Test that test data is cached properly."""
        size_bytes = int(1.0 * 1024 * 1024)
        
        with patch('tempfile.mkstemp') as mock_mkstemp, \
             patch('os.fdopen') as mock_fdopen, \
             patch('os.fsync'):
            
            mock_mkstemp.side_effect = [(5, "/tmp/file1.dat"), (6, "/tmp/file2.dat")]
            mock_fdopen.return_value = mock_open().return_value
            
            # Create first file
            self.tester.create_test_file(1.0)
            self.assertIn(size_bytes, self.tester._test_data_cache)
            
            # Create second file of same size
            self.tester.create_test_file(1.0)
            
            # Verify cache was used (same data object)
            self.assertEqual(len(self.tester._test_data_cache), 1)


class TestSMBTransfer(unittest.TestCase):
    """Test SMB transfer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = FileTransferTester()
    
    def tearDown(self):
        """Clean up after tests."""
        self.tester.cleanup()
    
    def test_smb_unavailable(self):
        """Test SMB transfer when pysmb is not available."""
        # Temporarily set SMB_AVAILABLE to False
        original_smb_available = SMB_AVAILABLE
        try:
            import src.file_transfer_tester
            src.file_transfer_tester.SMB_AVAILABLE = False
            
            with self.assertRaises(FileTransferError) as cm:
                self.tester.test_smb_transfer(
                    server_address="192.168.1.100",
                    share_name="test_share",
                    file_size_mb=1.0
                )
            
            self.assertIn("SMB support not available", str(cm.exception))
            self.assertIn("Install pysmb", str(cm.exception))
        finally:
            # Restore original state
            src.file_transfer_tester.SMB_AVAILABLE = original_smb_available
    
    @unittest.skipUnless(SMB_AVAILABLE, "pysmb not available")
    @patch('src.file_transfer_tester.SMBConnection')
    @patch('src.file_transfer_tester.FileTransferTester.create_test_file')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test_data')
    @patch('os.path.getsize')
    @patch('time.perf_counter')
    def test_smb_upload_success(self, mock_time, mock_getsize, mock_file, 
                               mock_create_file, mock_smb_conn_class):
        """Test successful SMB upload."""
        # Setup mocks
        mock_create_file.return_value = "/tmp/test_file.dat"
        mock_getsize.return_value = 1048576  # 1MB
        mock_time.side_effect = [0.0, 10.0]  # 10 second transfer
        
        mock_conn = Mock()
        mock_conn.connect.return_value = True
        mock_smb_conn_class.return_value = mock_conn
        
        # Test
        result = self.tester.test_smb_transfer(
            server_address="192.168.1.100",
            share_name="test_share",
            file_size_mb=1.0,
            direction="upload",
            username="testuser",
            password="testpass"
        )
        
        # Verify result
        self.assertIsInstance(result, FileTransferResult)
        self.assertEqual(result.server_address, "192.168.1.100")
        self.assertEqual(result.file_size, 1048576)
        self.assertEqual(result.transfer_time, 10.0)
        self.assertEqual(result.transfer_speed, 0.1)  # 1MB / 10s = 0.1 MB/s
        self.assertEqual(result.protocol, "SMB")
        self.assertEqual(result.direction, "upload")
        
        # Verify SMB operations
        mock_conn.connect.assert_called_once_with("192.168.1.100", 445, timeout=30.0)
        mock_conn.storeFile.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @unittest.skipUnless(SMB_AVAILABLE, "pysmb not available")
    @patch('src.file_transfer_tester.SMBConnection')
    @patch('tempfile.mktemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.getsize')
    @patch('time.perf_counter')
    def test_smb_download_success(self, mock_time, mock_getsize, mock_file,
                                 mock_mktemp, mock_smb_conn_class):
        """Test successful SMB download."""
        # Setup mocks
        mock_mktemp.return_value = "/tmp/download_file.dat"
        mock_getsize.return_value = 2097152  # 2MB
        mock_time.side_effect = [0.0, 5.0]  # 5 second transfer
        
        mock_conn = Mock()
        mock_conn.connect.return_value = True
        mock_smb_conn_class.return_value = mock_conn
        
        # Test
        result = self.tester.test_smb_transfer(
            server_address="192.168.1.100",
            share_name="test_share",
            file_size_mb=2.0,
            direction="download"
        )
        
        # Verify result
        self.assertEqual(result.transfer_speed, 0.4)  # 2MB / 5s = 0.4 MB/s
        self.assertEqual(result.direction, "download")
        
        # Verify SMB operations
        mock_conn.retrieveFile.assert_called_once()
    
    @unittest.skipUnless(SMB_AVAILABLE, "pysmb not available")
    @patch('src.file_transfer_tester.SMBConnection')
    def test_smb_connection_failed(self, mock_smb_conn_class):
        """Test SMB connection failure."""
        mock_conn = Mock()
        mock_conn.connect.return_value = False
        mock_smb_conn_class.return_value = mock_conn
        
        with self.assertRaises(FileTransferConnectionError) as cm:
            self.tester.test_smb_transfer(
                server_address="192.168.1.100",
                share_name="test_share",
                file_size_mb=1.0
            )
        
        self.assertIn("Failed to connect to SMB server", str(cm.exception))
    
    def test_smb_invalid_direction(self):
        """Test SMB transfer with invalid direction."""
        if not SMB_AVAILABLE:
            # Test that we get the SMB unavailable error instead
            with self.assertRaises(FileTransferError) as cm:
                self.tester.test_smb_transfer(
                    server_address="192.168.1.100",
                    share_name="test_share",
                    file_size_mb=1.0,
                    direction="invalid"
                )
            self.assertIn("SMB support not available", str(cm.exception))
        else:
            # Test invalid direction when SMB is available
            with self.assertRaises(ValueError) as cm:
                self.tester.test_smb_transfer(
                    server_address="192.168.1.100",
                    share_name="test_share",
                    file_size_mb=1.0,
                    direction="invalid"
                )
            self.assertIn("Invalid direction", str(cm.exception))
    
    @unittest.skipUnless(SMB_AVAILABLE, "pysmb not available")
    @patch('src.file_transfer_tester.SMBConnection')
    @patch('src.file_transfer_tester.FileTransferTester.create_test_file')
    def test_smb_protocol_error(self, mock_create_file, mock_smb_conn_class):
        """Test SMB protocol error handling."""
        mock_create_file.return_value = "/tmp/test_file.dat"
        
        mock_conn = Mock()
        mock_conn.connect.return_value = True
        mock_conn.storeFile.side_effect = Exception("SMB store failed")
        mock_smb_conn_class.return_value = mock_conn
        
        with patch('builtins.open', mock_open()):
            with self.assertRaises(FileTransferProtocolError) as cm:
                self.tester.test_smb_transfer(
                    server_address="192.168.1.100",
                    share_name="test_share",
                    file_size_mb=1.0,
                    direction="upload"
                )
        
        self.assertIn("SMB transfer failed", str(cm.exception))


class TestFTPTransfer(unittest.TestCase):
    """Test FTP transfer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = FileTransferTester()
    
    def tearDown(self):
        """Clean up after tests."""
        self.tester.cleanup()
    
    @patch('src.file_transfer_tester.ftplib.FTP')
    @patch('src.file_transfer_tester.FileTransferTester.create_test_file')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test_data')
    @patch('os.path.getsize')
    @patch('time.perf_counter')
    def test_ftp_upload_success(self, mock_time, mock_getsize, mock_file,
                               mock_create_file, mock_ftp_class):
        """Test successful FTP upload."""
        # Setup mocks
        mock_create_file.return_value = "/tmp/test_file.dat"
        mock_getsize.return_value = 524288  # 0.5MB
        mock_time.side_effect = [0.0, 2.0]  # 2 second transfer
        
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        # Test
        result = self.tester.test_ftp_transfer(
            server_address="ftp.example.com",
            file_size_mb=0.5,
            direction="upload",
            username="ftpuser",
            password="ftppass"
        )
        
        # Verify result
        self.assertIsInstance(result, FileTransferResult)
        self.assertEqual(result.server_address, "ftp.example.com")
        self.assertEqual(result.file_size, 524288)
        self.assertEqual(result.transfer_time, 2.0)
        self.assertEqual(result.transfer_speed, 0.25)  # 0.5MB / 2s = 0.25 MB/s
        self.assertEqual(result.protocol, "FTP")
        self.assertEqual(result.direction, "upload")
        
        # Verify FTP operations
        mock_ftp.connect.assert_called_once_with("ftp.example.com", 21, timeout=30.0)
        mock_ftp.login.assert_called_once_with("ftpuser", "ftppass")
        mock_ftp.set_pasv.assert_called_once_with(True)
        mock_ftp.storbinary.assert_called_once()
        mock_ftp.quit.assert_called_once()
    
    @patch('src.file_transfer_tester.ftplib.FTP')
    @patch('tempfile.mktemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.getsize')
    @patch('time.perf_counter')
    def test_ftp_download_success(self, mock_time, mock_getsize, mock_file,
                                 mock_mktemp, mock_ftp_class):
        """Test successful FTP download."""
        # Setup mocks
        mock_mktemp.return_value = "/tmp/download_file.dat"
        mock_getsize.return_value = 1048576  # 1MB
        mock_time.side_effect = [0.0, 4.0]  # 4 second transfer
        
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
        
        # Test
        result = self.tester.test_ftp_transfer(
            server_address="ftp.example.com",
            file_size_mb=1.0,
            direction="download",
            passive=False
        )
        
        # Verify result
        self.assertEqual(result.transfer_speed, 0.25)  # 1MB / 4s = 0.25 MB/s
        self.assertEqual(result.direction, "download")
        
        # Verify FTP operations
        mock_ftp.set_pasv.assert_not_called()  # Should not call set_pasv for non-passive mode
        mock_ftp.retrbinary.assert_called_once()
    
    @patch('src.file_transfer_tester.ftplib.FTP')
    def test_ftp_connection_error(self, mock_ftp_class):
        """Test FTP connection error."""
        mock_ftp = Mock()
        mock_ftp.connect.side_effect = Exception("Connection refused")
        mock_ftp_class.return_value = mock_ftp
        
        with self.assertRaises(FileTransferProtocolError) as cm:
            self.tester.test_ftp_transfer(
                server_address="ftp.example.com",
                file_size_mb=1.0
            )
        
        self.assertIn("FTP transfer failed", str(cm.exception))


class TestHTTPTransfer(unittest.TestCase):
    """Test HTTP transfer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = FileTransferTester()
    
    def tearDown(self):
        """Clean up after tests."""
        self.tester.cleanup()
    
    @patch('src.file_transfer_tester.http.client.HTTPConnection')
    @patch('src.file_transfer_tester.FileTransferTester.create_test_file')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test_data' * 1000)
    @patch('time.perf_counter')
    def test_http_upload_success(self, mock_time, mock_file, mock_create_file, mock_http_class):
        """Test successful HTTP upload."""
        # Setup mocks
        mock_create_file.return_value = "/tmp/test_file.dat"
        mock_time.side_effect = [0.0, 3.0]  # 3 second transfer
        
        mock_conn = Mock()
        mock_response = Mock()
        mock_response.status = 200
        mock_conn.getresponse.return_value = mock_response
        mock_http_class.return_value = mock_conn
        
        # Test
        result = self.tester.test_http_transfer(
            server_address="web.example.com",
            file_size_mb=1.0,
            direction="upload",
            port=8080,
            upload_endpoint="/api/upload"
        )
        
        # Verify result
        self.assertIsInstance(result, FileTransferResult)
        self.assertEqual(result.server_address, "web.example.com")
        self.assertEqual(result.protocol, "HTTP")
        self.assertEqual(result.direction, "upload")
        self.assertEqual(result.transfer_time, 3.0)
        
        # Verify HTTP operations
        mock_http_class.assert_called_once_with("web.example.com", 8080, timeout=30.0)
        mock_conn.request.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('src.file_transfer_tester.http.client.HTTPSConnection')
    @patch('src.file_transfer_tester.FileTransferTester.create_test_file')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test_data' * 1000)
    @patch('time.perf_counter')
    def test_https_upload_success(self, mock_time, mock_file, mock_create_file, mock_https_class):
        """Test successful HTTPS upload."""
        # Setup mocks
        mock_create_file.return_value = "/tmp/test_file.dat"
        mock_time.side_effect = [0.0, 2.0]
        
        mock_conn = Mock()
        mock_response = Mock()
        mock_response.status = 201
        mock_conn.getresponse.return_value = mock_response
        mock_https_class.return_value = mock_conn
        
        # Test
        result = self.tester.test_http_transfer(
            server_address="secure.example.com",
            file_size_mb=0.5,
            direction="upload",
            use_https=True
        )
        
        # Verify HTTPS was used
        self.assertEqual(result.protocol, "HTTPS")
        mock_https_class.assert_called_once_with("secure.example.com", 443, timeout=30.0)
    
    @patch('src.file_transfer_tester.urllib.request.urlopen')
    @patch('tempfile.mktemp')
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.getsize')
    @patch('time.perf_counter')
    def test_http_download_success(self, mock_time, mock_getsize, mock_file,
                                  mock_mktemp, mock_urlopen):
        """Test successful HTTP download."""
        # Setup mocks
        mock_mktemp.return_value = "/tmp/download_file.dat"
        mock_getsize.return_value = 2097152  # 2MB
        mock_time.side_effect = [0.0, 8.0]  # 8 second transfer
        
        mock_response = Mock()
        mock_response.read.return_value = b'downloaded_data'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Test
        result = self.tester.test_http_transfer(
            server_address="web.example.com",
            file_size_mb=2.0,
            direction="download",
            remote_file_path="/files/testfile.dat"
        )
        
        # Verify result
        self.assertEqual(result.transfer_speed, 0.25)  # 2MB / 8s = 0.25 MB/s
        self.assertEqual(result.direction, "download")
        
        # Verify URL was correct
        call_args = mock_urlopen.call_args[0][0]  # First positional argument (Request object)
        self.assertEqual(call_args.full_url, "http://web.example.com:80/files/testfile.dat")
    
    @patch('src.file_transfer_tester.http.client.HTTPConnection')
    @patch('src.file_transfer_tester.FileTransferTester.create_test_file')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test_data')
    def test_http_upload_error_status(self, mock_file, mock_create_file, mock_http_class):
        """Test HTTP upload with error status."""
        mock_create_file.return_value = "/tmp/test_file.dat"
        
        mock_conn = Mock()
        mock_response = Mock()
        mock_response.status = 500  # Server error
        mock_conn.getresponse.return_value = mock_response
        mock_http_class.return_value = mock_conn
        
        with patch('time.perf_counter', side_effect=[0.0, 1.0]):
            with self.assertRaises(FileTransferProtocolError) as cm:
                self.tester.test_http_transfer(
                    server_address="web.example.com",
                    file_size_mb=1.0,
                    direction="upload"
                )
        
        self.assertIn("HTTP upload failed with status 500", str(cm.exception))


class TestMultipleTransfers(unittest.TestCase):
    """Test multiple transfer execution and statistics."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = FileTransferTester()
    
    def tearDown(self):
        """Clean up after tests."""
        self.tester.cleanup()
    
    def test_run_multiple_transfers_success(self):
        """Test successful multiple transfers with statistics."""
        # Mock transfer function that returns different speeds
        def mock_transfer(**kwargs):
            speeds = [10.0, 12.0, 8.0]  # MB/s
            times = [1.0, 0.83, 1.25]  # seconds
            
            # Use call count to return different results
            call_count = getattr(mock_transfer, 'call_count', 0)
            mock_transfer.call_count = call_count + 1
            
            return FileTransferResult(
                server_address="test.server",
                file_size=10485760,  # 10MB
                transfer_time=times[call_count],
                transfer_speed=speeds[call_count],
                protocol="TEST",
                direction="download"
            )
        
        # Test
        results, stats = self.tester.run_multiple_transfers(
            transfer_func=mock_transfer,
            iterations=3,
            test_arg="value"
        )
        
        # Verify results
        self.assertEqual(len(results), 3)
        self.assertIsInstance(stats, dict)
        
        # Verify statistics
        self.assertEqual(stats['iterations_completed'], 3)
        self.assertEqual(stats['iterations_failed'], 0)
        self.assertEqual(stats['avg_speed_mb_s'], 10.0)  # (10+12+8)/3
        self.assertEqual(stats['min_speed_mb_s'], 8.0)
        self.assertEqual(stats['max_speed_mb_s'], 12.0)
        self.assertEqual(stats['speed_variation_percent'], 40.0)  # (12-8)/10*100
        self.assertGreater(stats['std_dev_speed_mb_s'], 0)
    
    def test_run_multiple_transfers_partial_failure(self):
        """Test multiple transfers with some failures."""
        call_count = 0
        
        def mock_transfer(**kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count == 2:  # Second call fails
                raise Exception("Network error")
            
            return FileTransferResult(
                server_address="test.server",
                file_size=1048576,
                transfer_time=1.0,
                transfer_speed=1.0,
                protocol="TEST",
                direction="upload"
            )
        
        # Test
        results, stats = self.tester.run_multiple_transfers(
            transfer_func=mock_transfer,
            iterations=3
        )
        
        # Verify results
        self.assertEqual(len(results), 2)  # 2 successful, 1 failed
        self.assertEqual(stats['iterations_completed'], 2)
        self.assertEqual(stats['iterations_failed'], 1)
    
    def test_run_multiple_transfers_all_failures(self):
        """Test multiple transfers with all failures."""
        def mock_transfer(**kwargs):
            raise Exception("All transfers fail")
        
        # Test
        with self.assertRaises(FileTransferError) as cm:
            self.tester.run_multiple_transfers(
                transfer_func=mock_transfer,
                iterations=3
            )
        
        self.assertIn("All 3 transfer attempts failed", str(cm.exception))
    
    def test_run_multiple_transfers_invalid_iterations(self):
        """Test multiple transfers with invalid iterations count."""
        def mock_transfer(**kwargs):
            return Mock()
        
        with self.assertRaises(ValueError) as cm:
            self.tester.run_multiple_transfers(
                transfer_func=mock_transfer,
                iterations=0
            )
        
        self.assertIn("Iterations must be at least 1", str(cm.exception))
    
    def test_statistics_single_result(self):
        """Test statistics calculation with single result."""
        def mock_transfer(**kwargs):
            return FileTransferResult(
                server_address="test.server",
                file_size=1048576,
                transfer_time=2.0,
                transfer_speed=5.0,
                protocol="TEST",
                direction="download"
            )
        
        results, stats = self.tester.run_multiple_transfers(
            transfer_func=mock_transfer,
            iterations=1
        )
        
        # With single result, std deviation should be 0
        self.assertEqual(stats['std_dev_speed_mb_s'], 0.0)
        self.assertEqual(stats['speed_variation_percent'], 0.0)


class TestCleanupAndContextManager(unittest.TestCase):
    """Test cleanup functionality and context manager."""
    
    def test_cleanup_success(self):
        """Test successful cleanup."""
        tester = FileTransferTester()
        
        # Add some fake files to cleanup list
        fake_files = ["/tmp/file1.dat", "/tmp/file2.dat"]
        tester._created_files = fake_files.copy()
        tester._test_data_cache = {1048576: b'test_data'}
        
        with patch('os.path.exists', return_value=True), \
             patch('os.unlink') as mock_unlink:
            
            tester.cleanup()
            
            # Verify files were removed
            self.assertEqual(mock_unlink.call_count, 2)
            mock_unlink.assert_has_calls([call("/tmp/file1.dat"), call("/tmp/file2.dat")])
            self.assertEqual(tester._created_files, [])
            self.assertEqual(tester._test_data_cache, {})
    
    def test_cleanup_with_errors(self):
        """Test cleanup with some file removal errors."""
        tester = FileTransferTester()
        
        # Add files to cleanup list
        fake_files = ["/tmp/file1.dat", "/tmp/file2.dat", "/tmp/file3.dat"]
        tester._created_files = fake_files.copy()
        
        def mock_unlink(path):
            if path == "/tmp/file2.dat":
                raise OSError("Permission denied")
        
        with patch('os.path.exists', return_value=True), \
             patch('os.unlink', side_effect=mock_unlink), \
             patch('src.file_transfer_tester.logger') as mock_logger:
            
            tester.cleanup()
            
            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            self.assertIn("Cleanup completed with errors", 
                         mock_logger.warning.call_args[0][0])
    
    def test_cleanup_nonexistent_files(self):
        """Test cleanup with files that no longer exist."""
        tester = FileTransferTester()
        
        tester._created_files = ["/tmp/nonexistent.dat"]
        
        with patch('os.path.exists', return_value=False), \
             patch('os.unlink') as mock_unlink:
            
            tester.cleanup()
            
            # unlink should not be called for nonexistent files
            mock_unlink.assert_not_called()
            self.assertEqual(tester._created_files, [])
    
    def test_context_manager(self):
        """Test context manager functionality."""
        with patch.object(FileTransferTester, 'cleanup') as mock_cleanup:
            with FileTransferTester() as tester:
                self.assertIsInstance(tester, FileTransferTester)
            
            # Cleanup should be called on exit
            mock_cleanup.assert_called_once()
    
    def test_context_manager_with_exception(self):
        """Test context manager cleanup on exception."""
        with patch.object(FileTransferTester, 'cleanup') as mock_cleanup:
            try:
                with FileTransferTester() as tester:
                    raise ValueError("Test exception")
            except ValueError:
                pass
            
            # Cleanup should still be called
            mock_cleanup.assert_called_once()


class TestIntegrationScenarios(unittest.TestCase):
    """Integration-style tests for realistic scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tester = FileTransferTester()
    
    def tearDown(self):
        """Clean up after tests."""
        self.tester.cleanup()
    
    @unittest.skipUnless(SMB_AVAILABLE, "pysmb not available for integration test")
    @patch('src.file_transfer_tester.SMBConnection')
    @patch('src.file_transfer_tester.ftplib.FTP')
    @patch('src.file_transfer_tester.urllib.request.urlopen')
    def test_protocol_comparison_scenario(self, mock_urlopen, mock_ftp_class, mock_smb_class):
        """Test comparing different protocols in a realistic scenario."""
        # Setup mocks for all protocols
        self._setup_smb_mock(mock_smb_class)
        self._setup_ftp_mock(mock_ftp_class)
        self._setup_http_mock(mock_urlopen)
        
        # Test all protocols
        protocols_results = []
        
        with patch('time.perf_counter', side_effect=self._mock_timing), \
             patch('os.path.getsize', return_value=10485760), \
             patch('tempfile.mktemp', return_value="/tmp/test.dat"):
            
            # SMB test
            smb_result = self.tester.test_smb_transfer(
                server_address="192.168.1.100",
                share_name="test",
                file_size_mb=10.0,
                direction="download"
            )
            protocols_results.append(('SMB', smb_result))
            
            # FTP test  
            ftp_result = self.tester.test_ftp_transfer(
                server_address="192.168.1.100",
                file_size_mb=10.0,
                direction="download"
            )
            protocols_results.append(('FTP', ftp_result))
            
            # HTTP test
            http_result = self.tester.test_http_transfer(
                server_address="192.168.1.100",
                file_size_mb=10.0,
                direction="download"
            )
            protocols_results.append(('HTTP', http_result))
        
        # Verify all protocols returned results
        self.assertEqual(len(protocols_results), 3)
        
        # Verify each protocol has unique characteristics
        protocols = [name for name, _ in protocols_results]
        self.assertIn('SMB', protocols)
        self.assertIn('FTP', protocols)
        self.assertIn('HTTP', protocols)
        
        # All should have same file size and direction
        for name, result in protocols_results:
            self.assertEqual(result.file_size, 10485760)
            self.assertEqual(result.direction, 'download')
            self.assertGreater(result.transfer_speed, 0)
    
    def _setup_smb_mock(self, mock_smb_class):
        """Setup SMB connection mock."""
        mock_conn = Mock()
        mock_conn.connect.return_value = True
        mock_smb_class.return_value = mock_conn
    
    def _setup_ftp_mock(self, mock_ftp_class):
        """Setup FTP connection mock."""
        mock_ftp = Mock()
        mock_ftp_class.return_value = mock_ftp
    
    def _setup_http_mock(self, mock_urlopen):
        """Setup HTTP mock."""
        mock_response = Mock()
        mock_response.read.return_value = b'x' * 10485760
        mock_urlopen.return_value.__enter__.return_value = mock_response
    
    def _mock_timing(self):
        """Mock timing to return predictable values."""
        times = [0.0, 5.0, 0.0, 3.0, 0.0, 8.0]  # Different speeds for each protocol
        if not hasattr(self._mock_timing, 'call_count'):
            self._mock_timing.call_count = 0
        
        time_value = times[self._mock_timing.call_count]
        self._mock_timing.call_count += 1
        return time_value


if __name__ == "__main__":
    unittest.main()