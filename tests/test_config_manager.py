"""Unit tests for configuration management system."""

import unittest
import tempfile
import os
from pathlib import Path
from src.config_manager import ConfigurationManager
from src.models import Configuration


class TestConfigurationManager(unittest.TestCase):
    """Test ConfigurationManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test configs
        self.temp_dir = tempfile.mkdtemp()
        self.test_config_path = Path(self.temp_dir) / "test_config.ini"
        
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary files
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_default_config(self):
        """Test creating default configuration file."""
        manager = ConfigurationManager()
        manager.create_default_config(str(self.test_config_path))
        
        # Check file was created
        self.assertTrue(self.test_config_path.exists())
        
        # Load and verify content
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        self.assertEqual(config.interface_name, "Wi-Fi")
        self.assertEqual(len(config.target_ips), 2)
        self.assertEqual(config.ping_count, 10)

    def test_load_config(self):
        """Test loading configuration from file."""
        # Create a test config
        manager = ConfigurationManager()
        manager.create_default_config(str(self.test_config_path))
        
        # Load it
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        self.assertIsInstance(config, Configuration)
        self.assertTrue(config.validate())

    def test_load_missing_config(self):
        """Test loading non-existent configuration file."""
        manager = ConfigurationManager("nonexistent.ini")
        
        with self.assertRaises(FileNotFoundError):
            manager.load_config()

    def test_parse_target_ips(self):
        """Test parsing target IPs from comma-separated string."""
        # Create config with multiple IPs
        manager = ConfigurationManager()
        manager.set_config_value('network', 'target_ips', '192.168.1.1, 10.0.0.1, 8.8.8.8')
        manager.save_config(str(self.test_config_path))
        
        # Load and verify
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        self.assertEqual(len(config.target_ips), 3)
        self.assertIn('192.168.1.1', config.target_ips)
        self.assertIn('10.0.0.1', config.target_ips)
        self.assertIn('8.8.8.8', config.target_ips)

    def test_set_config_value(self):
        """Test setting individual configuration values."""
        manager = ConfigurationManager()
        
        manager.set_config_value('network', 'interface_name', 'Ethernet')
        manager.set_config_value('measurement', 'ping_count', '20')
        manager.save_config(str(self.test_config_path))
        
        # Load and verify
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        self.assertEqual(config.interface_name, 'Ethernet')
        self.assertEqual(config.ping_count, 20)

    def test_validate_network_settings(self):
        """Test network settings validation."""
        manager = ConfigurationManager()
        manager.create_default_config(str(self.test_config_path))
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        # Valid settings should pass
        self.assertTrue(manager.validate_network_settings())
        
        # Test invalid IP
        config.target_ips = ['999.999.999.999']
        manager._configuration = config
        
        with self.assertRaises(ValueError):
            manager.validate_network_settings()
        
        # Test invalid port
        config.target_ips = ['192.168.1.1']
        config.iperf_port = 99999
        manager._configuration = config
        
        with self.assertRaises(ValueError):
            manager.validate_network_settings()

    def test_get_configuration_before_load(self):
        """Test getting configuration before loading."""
        manager = ConfigurationManager()
        
        with self.assertRaises(RuntimeError):
            manager.get_configuration()

    def test_get_defaults(self):
        """Test getting default configuration values."""
        manager = ConfigurationManager()
        defaults = manager.get_defaults()
        
        self.assertIn('interface_name', defaults)
        self.assertIn('ping_count', defaults)
        self.assertIn('iperf_server', defaults)
        self.assertEqual(defaults['interface_name'], 'Wi-Fi')
        self.assertEqual(defaults['ping_count'], 10)

    def test_config_with_missing_sections(self):
        """Test loading config with missing sections uses defaults."""
        # Create minimal config with only network section
        with open(self.test_config_path, 'w') as f:
            f.write('[network]\n')
            f.write('interface_name = Ethernet\n')
        
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        # Should use provided value for interface_name
        self.assertEqual(config.interface_name, 'Ethernet')
        
        # Should use defaults for missing values
        self.assertEqual(config.ping_count, 10)  # default
        self.assertEqual(config.iperf_port, 5201)  # default

    def test_boolean_parsing(self):
        """Test parsing boolean values from config."""
        manager = ConfigurationManager()
        manager.set_config_value('output', 'verbose', 'true')
        manager.save_config(str(self.test_config_path))
        
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        self.assertTrue(config.verbose)
        
        # Test false value
        manager.set_config_value('output', 'verbose', 'false')
        manager.save_config(str(self.test_config_path))
        
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        self.assertFalse(config.verbose)

    def test_log_level_uppercase(self):
        """Test that log level is converted to uppercase."""
        manager = ConfigurationManager()
        manager.set_config_value('output', 'log_level', 'debug')
        manager.save_config(str(self.test_config_path))
        
        manager = ConfigurationManager(str(self.test_config_path))
        config = manager.load_config()
        
        self.assertEqual(config.log_level, 'DEBUG')


if __name__ == '__main__':
    unittest.main()