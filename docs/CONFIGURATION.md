# Configuration Guide

This guide details all configuration options for the Wireless LAN Scanner and Performance Analyzer. The application uses INI-format configuration files with sections for different functional areas.

## Table of Contents

- [Configuration File Format](#configuration-file-format)
- [Network Section](#network-section)
- [Measurement Section](#measurement-section)
- [Output Section](#output-section)
- [Configuration Examples](#configuration-examples)
- [Command-Line Overrides](#command-line-overrides)
- [Environment-Specific Configs](#environment-specific-configs)
- [Validation and Defaults](#validation-and-defaults)

## Configuration File Format

The application uses standard INI format with three main sections:

```ini
[network]
# Network interface and connectivity settings

[measurement]  
# Measurement parameters for all test types

[output]
# Output formatting and logging settings
```

### Creating Configuration Files

```bash
# Create default configuration
python main.py --create-config

# Create with custom path
python main.py --create-config -c /path/to/config.ini

# Validate existing configuration
python main.py --validate-config -c config.ini
```

## Network Section

Controls network interface selection and target configuration.

### Configuration Options

```ini
[network]
interface_name = Wi-Fi
target_ips = 192.168.1.1, 8.8.8.8
scan_interval = 60
timeout = 10
```

#### `interface_name`
- **Type**: String
- **Default**: `Wi-Fi`
- **Description**: Network interface name for WiFi information collection
- **Examples**:
  - Windows: `Wi-Fi`, `WiFi`, `Wireless Network Connection`
  - Linux: `wlan0`, `wlp2s0`, `wifi0`

```ini
# Windows examples
interface_name = Wi-Fi
interface_name = WiFi 2

# Linux examples  
interface_name = wlan0
interface_name = wlp3s0
```

#### `target_ips`
- **Type**: Comma-separated IP addresses
- **Default**: `192.168.1.1`
- **Description**: IP addresses for ping testing
- **Examples**:

```ini
# Single target
target_ips = 192.168.1.1

# Multiple targets
target_ips = 192.168.1.1, 8.8.8.8, 1.1.1.1

# Mix of local and public IPs
target_ips = 192.168.1.1, 10.0.0.1, 8.8.8.8, 1.1.1.1
```

#### `scan_interval`
- **Type**: Integer (seconds)
- **Default**: `60`
- **Range**: 1-86400 (1 second to 24 hours)
- **Description**: Default interval between measurements in continuous mode

```ini
# Various interval examples
scan_interval = 30    # 30 seconds
scan_interval = 300   # 5 minutes  
scan_interval = 900   # 15 minutes
scan_interval = 3600  # 1 hour
```

#### `timeout`
- **Type**: Integer (seconds)
- **Default**: `10`
- **Range**: 1-300
- **Description**: Global timeout for all measurement operations

```ini
# Timeout examples
timeout = 5     # Fast timeout for responsive networks
timeout = 15    # Extended timeout for slower networks
timeout = 30    # Maximum timeout for unreliable connections
```

## Measurement Section

Configures parameters for all measurement types.

### Ping Configuration

```ini
[measurement]
ping_count = 10
ping_size = 32
ping_interval = 1.0
```

#### `ping_count`
- **Type**: Integer
- **Default**: `10`
- **Range**: 1-100
- **Description**: Number of ping packets per test

#### `ping_size`  
- **Type**: Integer (bytes)
- **Default**: `32`
- **Range**: 8-65500
- **Description**: Size of ping packets

#### `ping_interval`
- **Type**: Float (seconds)
- **Default**: `1.0`
- **Range**: 0.1-10.0
- **Description**: Interval between ping packets

### iPerf3 Configuration

```ini
[measurement]
iperf_server = 192.168.1.100
iperf_port = 5201  
iperf_duration = 10
iperf_parallel = 1
iperf_udp_bandwidth = 10M
```

#### `iperf_server`
- **Type**: IP address or hostname
- **Default**: `192.168.1.100`
- **Description**: iPerf3 server address for throughput testing

```ini
# IP address examples
iperf_server = 192.168.1.100
iperf_server = 10.0.0.50

# Hostname examples
iperf_server = iperf-server.local
iperf_server = performance-test.company.com
```

#### `iperf_port`
- **Type**: Integer
- **Default**: `5201`  
- **Range**: 1024-65535
- **Description**: iPerf3 server port

#### `iperf_duration`
- **Type**: Integer (seconds)
- **Default**: `10`
- **Range**: 1-3600
- **Description**: Duration for each iPerf3 test

```ini
# Duration examples
iperf_duration = 5    # Quick test
iperf_duration = 30   # Standard test
iperf_duration = 60   # Extended test
iperf_duration = 300  # Comprehensive test
```

#### `iperf_parallel`
- **Type**: Integer
- **Default**: `1`
- **Range**: 1-10
- **Description**: Number of parallel streams for TCP testing

#### `iperf_udp_bandwidth`
- **Type**: String (bandwidth specification)
- **Default**: `10M`
- **Description**: Target bandwidth for UDP testing

```ini
# Bandwidth examples  
iperf_udp_bandwidth = 1M     # 1 Mbps
iperf_udp_bandwidth = 10M    # 10 Mbps
iperf_udp_bandwidth = 100M   # 100 Mbps
iperf_udp_bandwidth = 1G     # 1 Gbps
```

### File Transfer Configuration

```ini
[measurement]
file_server = 192.168.1.100
file_size_mb = 100
file_protocol = SMB
```

#### `file_server`
- **Type**: IP address or hostname
- **Default**: `192.168.1.100`
- **Description**: File server address for transfer testing

#### `file_size_mb`
- **Type**: Integer (megabytes)
- **Default**: `100`
- **Range**: 1-10240 (1 MB to 10 GB)
- **Description**: Size of test file for transfer measurements

```ini
# File size examples
file_size_mb = 10     # 10 MB - quick test
file_size_mb = 100    # 100 MB - standard test  
file_size_mb = 1000   # 1 GB - comprehensive test
```

#### `file_protocol`
- **Type**: String
- **Default**: `SMB`
- **Options**: `SMB`, `FTP`, `HTTP`
- **Description**: Protocol for file transfer testing

```ini
# Protocol examples
file_protocol = SMB    # Windows file sharing
file_protocol = FTP    # FTP server
file_protocol = HTTP   # Web server
```

## Output Section

Controls data output formatting and logging behavior.

```ini
[output]
data_directory = data
output_format = csv
verbose = false
log_level = INFO
```

#### `data_directory`
- **Type**: String (directory path)
- **Default**: `data`
- **Description**: Directory for measurement data files

```ini
# Directory examples
data_directory = data
data_directory = /var/lib/wifi-measurements
data_directory = C:\WiFi-Data
data_directory = measurements/$(date +%Y%m)
```

#### `output_format`
- **Type**: String
- **Default**: `csv`
- **Options**: `csv`
- **Description**: Output format for measurement data

#### `verbose`
- **Type**: Boolean
- **Default**: `false`
- **Description**: Enable verbose logging output

```ini
# Verbose examples
verbose = true    # Enable verbose logging
verbose = false   # Standard logging
```

#### `log_level`
- **Type**: String
- **Default**: `INFO`
- **Options**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Description**: Logging level for application messages

```ini
# Log level examples
log_level = DEBUG     # Detailed debugging
log_level = INFO      # Standard information
log_level = WARNING   # Warnings and errors only
log_level = ERROR     # Errors only
```

## Configuration Examples

### Home Network Configuration

```ini
# config/home.ini
[network]
interface_name = Wi-Fi
target_ips = 192.168.1.1, 8.8.8.8
scan_interval = 300
timeout = 15

[measurement]
ping_count = 5
ping_size = 32
iperf_server = 192.168.1.10
iperf_duration = 10
file_server = 192.168.1.10
file_size_mb = 50

[output]
data_directory = data/home
output_format = csv
verbose = false
log_level = INFO
```

### Office Network Configuration

```ini
# config/office.ini
[network]
interface_name = Wi-Fi
target_ips = 10.0.0.1, 10.0.0.10, 8.8.8.8
scan_interval = 60
timeout = 10

[measurement]
ping_count = 10
ping_size = 64
iperf_server = 10.0.0.100
iperf_port = 5201
iperf_duration = 15
iperf_parallel = 2
file_server = 10.0.0.100
file_size_mb = 200
file_protocol = SMB

[output]
data_directory = data/office
output_format = csv
verbose = true
log_level = DEBUG
```

### High-Performance Testing Configuration

```ini
# config/performance.ini
[network]
interface_name = Wi-Fi
target_ips = 192.168.1.1, 1.1.1.1
scan_interval = 30
timeout = 30

[measurement]
ping_count = 20
ping_size = 1024
ping_interval = 0.5
iperf_server = 192.168.1.200
iperf_duration = 30
iperf_parallel = 4
iperf_udp_bandwidth = 100M
file_server = 192.168.1.200
file_size_mb = 1000
file_protocol = SMB

[output]
data_directory = data/performance
output_format = csv
verbose = true
log_level = INFO
```

### Minimal Testing Configuration

```ini
# config/minimal.ini
[network]
interface_name = Wi-Fi
target_ips = 8.8.8.8
scan_interval = 120
timeout = 5

[measurement]
ping_count = 3
ping_size = 32
# iPerf and file transfer disabled by not setting servers

[output]
data_directory = data/minimal
output_format = csv
verbose = false
log_level = WARNING
```

## Command-Line Overrides

Many configuration options can be overridden from the command line:

### Timeout Override
```bash
python main.py --timeout 20
```

### Output Directory Override
```bash
python main.py --output-dir /custom/path
```

### Interval Override (Continuous Mode)
```bash
python main.py --continuous -i 180
```

### Logging Overrides
```bash
python main.py --log-level DEBUG --verbose
python main.py --quiet --log-file custom.log
```

## Environment-Specific Configs

### Development Configuration
```ini
# config/dev.ini - Quick testing
[network]
scan_interval = 30
timeout = 5

[measurement]  
ping_count = 3
iperf_duration = 5
file_size_mb = 10

[output]
verbose = true
log_level = DEBUG
```

### Production Configuration
```ini
# config/prod.ini - Stable monitoring
[network]
scan_interval = 300
timeout = 10

[measurement]
ping_count = 10
iperf_duration = 15
file_size_mb = 100

[output]
verbose = false
log_level = INFO
```

### Troubleshooting Configuration
```ini
# config/debug.ini - Problem diagnosis
[network]
scan_interval = 10
timeout = 30

[measurement]
ping_count = 20
ping_interval = 0.1
iperf_duration = 60

[output]
verbose = true
log_level = DEBUG
```

## Validation and Defaults

### Configuration Validation

The application validates configuration values on startup:

- **Numeric ranges**: All numeric values checked against valid ranges
- **Network addresses**: IP addresses validated for format
- **File paths**: Output directories created if they don't exist
- **Dependencies**: Server addresses verified for required tests

### Default Value Inheritance

Configuration uses a hierarchy of defaults:

1. **Built-in defaults**: Hard-coded in the application
2. **Configuration file**: Values from INI file override defaults  
3. **Command-line options**: CLI arguments override configuration
4. **Environment variables**: (Future enhancement)

### Error Handling

Configuration errors are handled gracefully:

```bash
# Validate configuration
python main.py --validate-config

# Check for issues without running
python main.py --dry-run

# Display configuration values
python main.py --dry-run --verbose
```

### Configuration File Templates

Generate templates for different scenarios:

```bash
# Default template
python main.py --create-config

# Copy and modify for specific environments
cp config/config.ini config/office.ini
cp config/config.ini config/home.ini
```

## Best Practices

### Configuration Management
- Use separate files for different environments
- Version control configuration files
- Document custom settings and rationale
- Test configuration changes with `--dry-run`

### Performance Considerations
- Balance measurement frequency with resource usage
- Adjust timeouts based on network conditions
- Consider bandwidth impact of iPerf tests
- Monitor disk space for measurement data

### Security Considerations
- Protect configuration files with appropriate permissions
- Use non-privileged ports when possible
- Avoid storing credentials in configuration files
- Validate server addresses and ports

---

For usage examples, see [`USAGE.md`](USAGE.md).  
For troubleshooting configuration issues, see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).