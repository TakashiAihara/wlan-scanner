# Configuration Templates

This directory contains pre-configured templates for different usage scenarios.

## Available Configurations

### `config.ini` (Default)
- **Purpose**: Basic configuration suitable for most users
- **Network**: Standard home/office settings
- **Measurements**: Balanced parameters for general use
- **Usage**: `python main.py` (uses default config)

### `home.ini`  
- **Purpose**: Optimized for home networks
- **Network**: Consumer router targets (192.168.1.x)
- **Measurements**: Moderate testing frequency
- **Bandwidth**: Conservative settings for home connections
- **Usage**: `python main.py -c config/home.ini`

### `office.ini`
- **Purpose**: Corporate/enterprise environments
- **Network**: Office network targets (10.0.0.x)
- **Measurements**: Comprehensive testing
- **Bandwidth**: Higher performance expectations
- **Usage**: `python main.py -c config/office.ini`

### `performance.ini`
- **Purpose**: Detailed performance analysis and benchmarking
- **Network**: Multiple targets for comprehensive testing
- **Measurements**: Extended duration, high frequency
- **Bandwidth**: Maximum throughput testing
- **Usage**: `python main.py -c config/performance.ini`

### `minimal.ini`
- **Purpose**: Basic monitoring with minimal resource usage
- **Network**: Single target, infrequent testing
- **Measurements**: WiFi info and ping only
- **Bandwidth**: No iPerf or file transfer tests
- **Usage**: `python main.py -c config/minimal.ini`

### `debug.ini`
- **Purpose**: Troubleshooting and problem diagnosis
- **Network**: Multiple targets, very frequent testing
- **Measurements**: Extended parameters for detailed analysis
- **Logging**: Maximum verbosity
- **Usage**: `python main.py -c config/debug.ini`

## Customization

1. **Copy a template** that matches your needs:
   ```bash
   cp config/home.ini config/my-config.ini
   ```

2. **Edit network settings** to match your environment:
   ```ini
   [network]
   interface_name = Your-WiFi-Interface
   target_ips = your.gateway.ip, 8.8.8.8
   iperf_server = your.server.ip
   ```

3. **Adjust measurement parameters** based on requirements:
   ```ini
   [measurement]
   ping_count = 10           # Increase for more accuracy
   iperf_duration = 30       # Longer tests for stable results
   file_size_mb = 100        # Adjust based on connection speed
   ```

4. **Configure output settings**:
   ```ini
   [output]
   data_directory = data/custom
   verbose = true            # Enable for troubleshooting
   log_level = DEBUG         # Detailed logging
   ```

## Quick Start by Environment

### Home Users
```bash
# Copy and customize home template
cp config/home.ini config/my-home.ini
# Edit my-home.ini with your router IP and server settings
python main.py -c config/my-home.ini --continuous
```

### Office/Corporate
```bash
# Copy and customize office template
cp config/office.ini config/my-office.ini
# Update with corporate network addresses
python main.py -c config/my-office.ini --continuous
```

### Troubleshooting
```bash
# Use debug configuration for problem diagnosis
python main.py -c config/debug.ini -v
```

### Performance Testing
```bash
# Run comprehensive performance analysis
python main.py -c config/performance.ini --tests iperf_tcp,iperf_udp
```

## Configuration Validation

Always validate configuration changes:

```bash
# Check configuration syntax
python main.py -c config/my-config.ini --validate-config

# Test prerequisites without running measurements
python main.py -c config/my-config.ini --dry-run

# Run with debug output to verify settings
python main.py -c config/my-config.ini --log-level DEBUG -v
```

## Network-Specific Adaptations

### Different Network Ranges
Update IP addresses to match your network:

```ini
# For 192.168.0.x networks
target_ips = 192.168.0.1, 8.8.8.8
iperf_server = 192.168.0.100

# For 10.x.x.x corporate networks  
target_ips = 10.1.1.1, 10.1.1.10, 8.8.8.8
iperf_server = 10.1.1.100

# For 172.16.x.x networks
target_ips = 172.16.1.1, 8.8.8.8
iperf_server = 172.16.1.100
```

### Interface Names by Platform

**Windows**:
```ini
interface_name = Wi-Fi
interface_name = WiFi
interface_name = Wireless Network Connection
```

**Linux**:
```ini
interface_name = wlan0
interface_name = wlp2s0  
interface_name = wifi0
```

**macOS**:
```ini
interface_name = en0
interface_name = Wi-Fi
```

## Best Practices

1. **Start with templates**: Use the closest match to your environment
2. **Test incrementally**: Validate each change with `--dry-run`
3. **Document changes**: Comment your customizations
4. **Version control**: Keep configuration files in git
5. **Environment separation**: Use separate configs for different networks
6. **Security**: Don't include credentials in config files

For detailed configuration options, see [`CONFIGURATION.md`](../docs/CONFIGURATION.md).