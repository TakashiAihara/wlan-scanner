"""Configuration management system for wireless LAN analyzer."""

import os
import configparser
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from src.models import Configuration


class ConfigurationManager:
    """Manages application configuration loading and validation."""

    DEFAULT_CONFIG_PATH = "config/config.ini"
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file. Uses default if None.
        """
        self.config_path = Path(config_path or self.DEFAULT_CONFIG_PATH)
        self.logger = logging.getLogger(__name__)
        self._config_parser = configparser.ConfigParser()
        self._config_dict: Dict[str, Any] = {}
        self._configuration: Optional[Configuration] = None

    def load_config(self) -> Configuration:
        """Load configuration from file.
        
        Returns:
            Configuration object with loaded settings.
            
        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            configparser.Error: If configuration file is invalid.
            ValueError: If configuration validation fails.
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        self.logger.info(f"Loading configuration from {self.config_path}")
        
        try:
            self._config_parser.read(self.config_path)
            self._parse_configuration()
            self._configuration = Configuration.from_dict(self._config_dict)
            self._configuration.validate()
            
            self.logger.info("Configuration loaded and validated successfully")
            return self._configuration
            
        except configparser.Error as e:
            self.logger.error(f"Failed to parse configuration file: {e}")
            raise
        except ValueError as e:
            self.logger.error(f"Configuration validation failed: {e}")
            raise

    def _parse_configuration(self) -> None:
        """Parse configuration from ConfigParser to dictionary."""
        # Network settings
        if 'network' in self._config_parser:
            network = self._config_parser['network']
            self._config_dict['interface_name'] = network.get('interface_name', 'Wi-Fi')
            
            # Parse target IPs as list
            target_ips_str = network.get('target_ips', '192.168.1.1')
            self._config_dict['target_ips'] = [
                ip.strip() for ip in target_ips_str.split(',')
            ]
            
            self._config_dict['scan_interval'] = network.getint('scan_interval', 60)
            self._config_dict['timeout'] = network.getint('timeout', 10)

        # Measurement settings
        if 'measurement' in self._config_parser:
            measurement = self._config_parser['measurement']
            
            # Ping settings
            self._config_dict['ping_count'] = measurement.getint('ping_count', 10)
            self._config_dict['ping_size'] = measurement.getint('ping_size', 32)
            self._config_dict['ping_interval'] = measurement.getfloat('ping_interval', 1.0)
            
            # iPerf settings
            self._config_dict['iperf_server'] = measurement.get('iperf_server', '192.168.1.100')
            self._config_dict['iperf_port'] = measurement.getint('iperf_port', 5201)
            self._config_dict['iperf_duration'] = measurement.getint('iperf_duration', 10)
            self._config_dict['iperf_parallel'] = measurement.getint('iperf_parallel', 1)
            self._config_dict['iperf_udp_bandwidth'] = measurement.get('iperf_udp_bandwidth', '10M')
            
            # File transfer settings
            self._config_dict['file_server'] = measurement.get('file_server', '192.168.1.100')
            self._config_dict['file_size_mb'] = measurement.getint('file_size_mb', 100)
            self._config_dict['file_protocol'] = measurement.get('file_protocol', 'SMB')

        # Output settings
        if 'output' in self._config_parser:
            output = self._config_parser['output']
            self._config_dict['output_dir'] = output.get('data_directory', 'data')
            self._config_dict['output_format'] = output.get('output_format', 'csv')
            self._config_dict['verbose'] = output.getboolean('verbose', False)
            self._config_dict['log_level'] = output.get('log_level', 'INFO').upper()

    def get_configuration(self) -> Configuration:
        """Get current configuration object.
        
        Returns:
            Current Configuration object.
            
        Raises:
            RuntimeError: If configuration hasn't been loaded yet.
        """
        if self._configuration is None:
            raise RuntimeError("Configuration not loaded. Call load_config() first.")
        return self._configuration

    def set_config_value(self, section: str, key: str, value: Any) -> None:
        """Set a configuration value.
        
        Args:
            section: Configuration section name.
            key: Configuration key name.
            value: New value for the configuration.
        """
        if section not in self._config_parser:
            self._config_parser.add_section(section)
        
        self._config_parser.set(section, key, str(value))
        self.logger.debug(f"Set {section}.{key} = {value}")

    def save_config(self, path: Optional[str] = None) -> None:
        """Save current configuration to file.
        
        Args:
            path: Path to save configuration. Uses current path if None.
        """
        save_path = Path(path) if path else self.config_path
        
        # Create directory if it doesn't exist
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(save_path, 'w') as config_file:
            self._config_parser.write(config_file)
        
        self.logger.info(f"Configuration saved to {save_path}")

    def get_defaults(self) -> Dict[str, Any]:
        """Get default configuration values.
        
        Returns:
            Dictionary of default configuration values.
        """
        default_config = Configuration()
        return {
            field: getattr(default_config, field)
            for field in default_config.__dataclass_fields__
        }

    def validate_network_settings(self) -> bool:
        """Validate network-specific configuration settings.
        
        Returns:
            True if network settings are valid.
            
        Raises:
            ValueError: If network settings are invalid.
        """
        config = self.get_configuration()
        
        # Validate target IPs
        for ip in config.target_ips:
            parts = ip.split('.')
            if len(parts) != 4:
                raise ValueError(f"Invalid IP address format: {ip}")
            
            for part in parts:
                try:
                    num = int(part)
                    if not 0 <= num <= 255:
                        raise ValueError(f"Invalid IP address: {ip}")
                except ValueError:
                    raise ValueError(f"Invalid IP address: {ip}")
        
        # Validate iPerf server
        if config.iperf_server:
            parts = config.iperf_server.split('.')
            if len(parts) == 4:  # IP address
                for part in parts:
                    try:
                        num = int(part)
                        if not 0 <= num <= 255:
                            raise ValueError(f"Invalid iPerf server IP: {config.iperf_server}")
                    except ValueError:
                        pass  # Could be hostname
        
        # Validate port numbers
        if not 1 <= config.iperf_port <= 65535:
            raise ValueError(f"Invalid iPerf port: {config.iperf_port}")
        
        return True

    def create_default_config(self, path: Optional[str] = None) -> None:
        """Create a default configuration file.
        
        Args:
            path: Path to create configuration file. Uses default if None.
        """
        save_path = Path(path) if path else self.config_path
        
        # Set default values
        self._config_parser['network'] = {
            'interface_name': 'Wi-Fi',
            'target_ips': '192.168.1.1, 8.8.8.8',
            'scan_interval': '60',
            'timeout': '10'
        }
        
        self._config_parser['measurement'] = {
            'ping_count': '10',
            'ping_size': '32',
            'ping_interval': '1.0',
            'iperf_server': '192.168.1.100',
            'iperf_port': '5201',
            'iperf_duration': '10',
            'iperf_parallel': '1',
            'iperf_udp_bandwidth': '10M',
            'file_server': '192.168.1.100',
            'file_size_mb': '100',
            'file_protocol': 'SMB'
        }
        
        self._config_parser['output'] = {
            'data_directory': 'data',
            'output_format': 'csv',
            'verbose': 'false',
            'log_level': 'INFO'
        }
        
        self.save_config(str(save_path))
        self.logger.info(f"Created default configuration at {save_path}")