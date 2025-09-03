# Wireless LAN Scanner and Performance Analyzer

A comprehensive Python-based tool for analyzing wireless LAN performance and connectivity. This tool provides detailed measurements of WiFi connection quality, network latency, throughput, and file transfer performance.

## Features

- **WiFi Information Collection**: RSSI, link quality, channel, frequency, and transmission rates
- **Network Latency Testing**: Ping measurements with comprehensive statistics
- **Throughput Testing**: iPerf3 TCP and UDP performance measurements  
- **File Transfer Testing**: Real-world file transfer performance analysis
- **Continuous Monitoring**: Automated measurements with configurable intervals
- **Data Export**: CSV output with comprehensive measurement data
- **Flexible Configuration**: INI-based configuration with command-line overrides
- **Cross-Platform**: Windows and Linux support with platform-specific optimizations

## Installation

### Prerequisites

- Python 3.7 or higher
- Active WiFi connection
- iPerf3 server (for throughput testing)
- File server access (for file transfer testing)

### System Dependencies

#### Windows
```bash
# Install iPerf3
# Download from: https://iperf.fr/iperf-download.php
# Or via Chocolatey:
choco install iperf3
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install iperf3

# RHEL/CentOS/Fedora
sudo yum install iperf3
# or
sudo dnf install iperf3
```

### Python Installation

1. **Clone the repository**:
```bash
git clone https://github.com/TakashiAihara/wlan-scanner.git
cd wlan-scanner
```

2. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

3. **Run immediately** (no configuration needed):
```bash
# Basic measurement with auto-detected WiFi interface
python main.py

# Continuous monitoring every 5 minutes
python main.py --continuous -i 300

# Specify custom settings via command line
python main.py --interface Wi-Fi --targets 8.8.8.8,1.1.1.1 --ping-count 20

# With iPerf3 server
python main.py --iperf-server 192.168.1.100 --iperf-duration 10
```

### Optional: Configuration File

If you prefer using a configuration file instead of command-line options:

1. **Create configuration file** (optional):
```bash
python main.py --create-config
```

2. **Edit settings** (optional - edit `config/config.ini`):
```ini
[network]
interface_name = auto  # or specific interface like "Wi-Fi"
target_ips = 8.8.8.8, 1.1.1.1
iperf_server = 192.168.1.100

[measurement]
ping_count = 10
iperf_duration = 10

[output]
data_directory = data
output_format = csv
```

## Quick Start

### Basic Usage

```bash
# Run single measurement with default settings
python main.py

# Run with custom configuration
python main.py -c path/to/config.ini

# Validate configuration and prerequisites
python main.py --dry-run

# Create default configuration file
python main.py --create-config
```

### Continuous Monitoring

```bash
# Run continuous measurements (60-second interval)
python main.py --continuous

# Custom interval (5 minutes)
python main.py --continuous -i 300

# Limited number of measurements
python main.py --continuous --max-measurements 100
```

### Selective Testing

```bash
# Run only WiFi info and ping tests
python main.py --tests wifi_info,ping

# Run only throughput tests
python main.py --tests iperf_tcp,iperf_udp

# Run single file transfer test
python main.py --tests file_transfer
```

## Measurement Types

### WiFi Information (`wifi_info`)
Collects wireless connection details:
- **SSID**: Network name
- **RSSI**: Signal strength (dBm)  
- **Link Quality**: Connection quality percentage
- **TX/RX Rate**: Transmission speeds (Mbps)
- **Channel**: WiFi channel number
- **Frequency**: Operating frequency (GHz)

### Ping Testing (`ping`)  
Network latency measurements:
- **Packet Loss**: Percentage of lost packets
- **RTT Statistics**: Min/Max/Average/StdDev round-trip times
- **Target Flexibility**: Multiple IP addresses supported

### iPerf3 TCP Testing (`iperf_tcp`)
Bidirectional TCP throughput:
- **Upload/Download Speed**: Separate measurements
- **Retransmission Count**: TCP reliability metrics
- **Duration Control**: Configurable test duration

### iPerf3 UDP Testing (`iperf_udp`)
UDP performance analysis:
- **Throughput**: Maximum UDP bandwidth
- **Packet Loss**: UDP packet loss percentage  
- **Jitter**: Network timing variation

### File Transfer Testing (`file_transfer`)
Real-world transfer performance:
- **Protocol Support**: SMB, FTP, HTTP
- **Bidirectional**: Upload and download testing
- **Configurable Size**: Variable file sizes

## Command-Line Options

### Configuration
- `-c, --config FILE`: Configuration file path
- `--create-config`: Create default configuration file
- `--validate-config`: Validate configuration only

### Measurement Control  
- `--continuous`: Run measurements continuously
- `-i, --interval SECONDS`: Measurement interval (default: 60)
- `--tests LIST`: Comma-separated test types
- `--max-measurements N`: Maximum measurement count
- `--timeout SECONDS`: Override measurement timeout

### Validation
- `--dry-run`: Validate without running measurements
- `--check-prerequisites`: Check system requirements

### Output and Logging
- `-v, --verbose`: Enable verbose output
- `--log-level LEVEL`: Set logging level (DEBUG/INFO/WARNING/ERROR)
- `--log-file FILE`: Log to file
- `--output-dir DIR`: Override output directory
- `--quiet`: Suppress non-essential output

## Output Data

### CSV Format
Measurements are exported to CSV files in the configured output directory:

```csv
measurement_id,timestamp,wifi_ssid,wifi_rssi,wifi_link_quality,ping_packet_loss,ping_avg_rtt,iperf_tcp_upload,iperf_tcp_download,iperf_udp_throughput,file_transfer_speed
2024-01-15-143022-001,2024-01-15T14:30:22.123456,MyNetwork,-45,85,0.0,12.34,95.6,87.3,45.2,78.9
```

### File Structure
```
data/
├── measurements_2024-01-15.csv
├── measurements_2024-01-16.csv
└── logs/
    └── scanner.log
```

## Configuration

The application uses INI-format configuration files. See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for detailed configuration options.

### Sample Configuration Sections

#### Network Settings
```ini
[network]
interface_name = Wi-Fi            # Network interface name
target_ips = 192.168.1.1, 8.8.8.8 # Ping targets
scan_interval = 60                # Default interval (seconds)
timeout = 10                      # Operation timeout
```

#### Measurement Parameters  
```ini
[measurement]
ping_count = 10                   # Packets per ping test
iperf_server = 192.168.1.100     # iPerf3 server address
iperf_duration = 10              # Test duration (seconds)
file_size_mb = 100               # Transfer test file size
```

## Troubleshooting

### Common Issues

**No WiFi connection detected**
- Ensure WiFi adapter is enabled and connected
- Verify interface name in configuration
- Check Windows WiFi service status

**iPerf3 tests failing**
- Confirm iPerf3 server is running: `iperf3 -s`
- Verify server IP address and port configuration
- Check firewall settings for port 5201

**File transfer tests failing**  
- Verify file server accessibility
- Check credentials and permissions
- Ensure sufficient disk space

**Permission errors (Linux)**
- Run with appropriate privileges for network operations
- Consider using `sudo` for system-level network access

For detailed troubleshooting, see [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Development

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python -m pytest tests/test_wifi_collector.py
python -m pytest tests/integration_tests.py
```

### Code Structure
```
src/
├── config_manager.py        # Configuration handling
├── wifi_collector.py        # WiFi information collection  
├── network_tester.py        # Ping and network tests
├── file_transfer_tester.py  # File transfer measurements
├── measurement_orchestrator.py # Test coordination
├── data_export_manager.py   # Data export and CSV handling
├── error_handler.py         # Error management
└── models.py               # Data models and types
```

## Requirements

See [`requirements.txt`](requirements.txt) for Python dependencies:
- `pythonping`: Cross-platform ping implementation
- `iperf3`: Python iPerf3 integration  
- `configparser`: Configuration file handling
- `pywin32`: Windows-specific WiFi API access

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement changes with tests
4. Submit a pull request

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for version history and release notes.

## Support

For issues and questions:
- Create an issue on GitHub
- Check the troubleshooting guide
- Review configuration documentation

---

**Version**: 1.0.0  
**Author**: TakashiAihara  
**Repository**: https://github.com/TakashiAihara/wlan-scanner