# Usage Guide

This guide provides comprehensive examples and detailed usage instructions for the Wireless LAN Scanner and Performance Analyzer.

## Table of Contents

- [Basic Operations](#basic-operations)
- [Measurement Types](#measurement-types)
- [Command-Line Examples](#command-line-examples)
- [Configuration Usage](#configuration-usage)
- [Output Analysis](#output-analysis)
- [Advanced Scenarios](#advanced-scenarios)
- [Integration Examples](#integration-examples)

## Basic Operations

### First Run Setup

1. **Create configuration file**:
```bash
python main.py --create-config
```

2. **Validate setup**:
```bash
python main.py --dry-run
```

3. **Run first measurement**:
```bash
python main.py
```

### Single Measurement

Execute a complete measurement cycle with all enabled tests:

```bash
# Default configuration
python main.py

# Custom configuration file  
python main.py -c /path/to/config.ini

# Specific output directory
python main.py --output-dir /data/wifi-measurements
```

### Continuous Monitoring

For ongoing network monitoring:

```bash
# Every 60 seconds (default)
python main.py --continuous

# Every 5 minutes
python main.py --continuous -i 300

# Every 30 seconds for 2 hours (240 measurements)
python main.py --continuous -i 30 --max-measurements 240

# Run overnight monitoring
python main.py --continuous -i 600 --log-file overnight.log
```

## Measurement Types

### WiFi Information Collection

Collect detailed wireless connection information:

```bash
# WiFi info only
python main.py --tests wifi_info

# WiFi info with verbose output
python main.py --tests wifi_info -v
```

**Output includes**:
- SSID (network name)
- RSSI (signal strength in dBm)
- Link quality percentage
- TX/RX rates (Mbps)
- Channel and frequency
- Interface details

### Network Latency Testing

Ping tests for network latency and reliability:

```bash
# Ping test only
python main.py --tests ping

# Ping with custom timeout
python main.py --tests ping --timeout 5

# Continuous ping monitoring
python main.py --tests ping --continuous -i 10
```

**Measurement details**:
- Tests multiple target IPs from configuration
- Configurable packet count and size
- Statistics: min/max/avg RTT, packet loss, standard deviation

### iPerf3 Throughput Testing

High-precision network throughput measurements:

#### TCP Throughput
```bash
# TCP throughput only
python main.py --tests iperf_tcp

# Extended duration test
python main.py --tests iperf_tcp -c config_long_test.ini
```

#### UDP Throughput  
```bash
# UDP throughput only
python main.py --tests iperf_udp

# Both TCP and UDP
python main.py --tests iperf_tcp,iperf_udp
```

**Configuration requirements**:
- iPerf3 server must be running: `iperf3 -s`
- Server IP configured in `[measurement]` section
- Firewall ports opened (default: 5201)

### File Transfer Performance

Real-world file transfer testing:

```bash
# File transfer test only
python main.py --tests file_transfer

# File transfer with other tests
python main.py --tests ping,file_transfer
```

**Supported protocols**:
- SMB (Windows file sharing)
- FTP (File Transfer Protocol)
- HTTP (Web-based transfer)

## Command-Line Examples

### Development and Testing

```bash
# Validate configuration without running tests
python main.py --validate-config

# Check prerequisites only  
python main.py --check-prerequisites

# Dry run - full validation without execution
python main.py --dry-run

# Debug mode with detailed logging
python main.py --log-level DEBUG -v
```

### Production Monitoring

```bash
# Production continuous monitoring
python main.py --continuous -i 300 \
  --log-file /var/log/wifi-scanner.log \
  --output-dir /data/measurements \
  --log-level INFO

# Lightweight monitoring (ping only)
python main.py --continuous --tests ping -i 60 \
  --quiet --log-file ping-monitor.log

# Comprehensive monitoring with rotation
python main.py --continuous -i 900 \
  --max-measurements 96 \
  --log-file daily-$(date +%Y%m%d).log
```

### Troubleshooting Scenarios

```bash
# Verbose debugging
python main.py --tests ping -v --log-level DEBUG

# Test specific target
python main.py --tests ping -c debug-config.ini -v

# Single test with timeout override
python main.py --tests iperf_tcp --timeout 30 -v

# Minimal test for connectivity
python main.py --tests wifi_info,ping --quiet
```

## Configuration Usage

### Multiple Configuration Files

Maintain different configurations for various scenarios:

```bash
# Office network configuration
python main.py -c config/office.ini --continuous

# Home network configuration  
python main.py -c config/home.ini --continuous

# Test lab configuration
python main.py -c config/testlab.ini --tests iperf_tcp,iperf_udp
```

### Configuration Override Examples

Override configuration values from command line:

```bash
# Override timeout
python main.py --timeout 15

# Override output directory
python main.py --output-dir /tmp/measurements

# Override log level
python main.py --log-level WARNING --quiet
```

## Output Analysis

### CSV Data Structure

The CSV output contains comprehensive measurement data:

```csv
measurement_id,timestamp,wifi_ssid,wifi_rssi,wifi_link_quality,wifi_tx_rate,wifi_rx_rate,wifi_channel,wifi_frequency,ping_target,ping_packet_loss,ping_avg_rtt,ping_min_rtt,ping_max_rtt,ping_std_dev,iperf_tcp_upload,iperf_tcp_download,iperf_tcp_retransmits,iperf_udp_throughput,iperf_udp_packet_loss,iperf_udp_jitter,file_transfer_speed,file_transfer_throughput,file_transfer_direction,error_count
```

### Data Processing Examples

#### Basic Analysis with pandas
```python
import pandas as pd

# Load measurement data
df = pd.read_csv('data/measurements_2024-01-15.csv')

# Signal strength analysis
print(f"Average RSSI: {df['wifi_rssi'].mean():.1f} dBm")
print(f"Signal quality: {df['wifi_link_quality'].mean():.1f}%")

# Latency statistics
print(f"Average ping: {df['ping_avg_rtt'].mean():.2f} ms")
print(f"Packet loss: {df['ping_packet_loss'].mean():.2f}%")

# Throughput analysis
print(f"Average upload: {df['iperf_tcp_upload'].mean():.1f} Mbps")  
print(f"Average download: {df['iperf_tcp_download'].mean():.1f} Mbps")
```

#### Time Series Analysis
```python
import matplotlib.pyplot as plt

# Convert timestamp to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Plot signal strength over time
plt.figure(figsize=(12, 6))
plt.plot(df['timestamp'], df['wifi_rssi'])
plt.title('WiFi Signal Strength Over Time')
plt.ylabel('RSSI (dBm)')
plt.xlabel('Time')
plt.xticks(rotation=45)
plt.tight_layout()
plt.show()
```

## Advanced Scenarios

### Network Performance Baseline

Establish performance baselines:

```bash
# 24-hour baseline collection
python main.py --continuous -i 600 \
  --max-measurements 144 \
  --log-file baseline-$(date +%Y%m%d).log \
  --output-dir baseline-data
```

### Before/After Comparison

Compare network changes:

```bash
# Before network changes
python main.py --continuous -i 60 --max-measurements 60 \
  --output-dir before-changes

# After network changes
python main.py --continuous -i 60 --max-measurements 60 \
  --output-dir after-changes
```

### Multi-Location Testing

Test from different locations:

```bash
# Location 1
python main.py -c config/location1.ini \
  --output-dir data/location1 --continuous -i 300

# Location 2  
python main.py -c config/location2.ini \
  --output-dir data/location2 --continuous -i 300
```

### Performance Stress Testing

High-frequency measurements for stress testing:

```bash
# High-frequency monitoring
python main.py --continuous -i 10 \
  --tests wifi_info,ping \
  --max-measurements 360 \
  --log-level WARNING
```

## Integration Examples

### Scheduled Monitoring

#### Windows Task Scheduler
Create a batch file `wifi-monitor.bat`:
```batch
@echo off
cd /d "C:\path\to\wlan-scanner"
python main.py --continuous -i 300 --max-measurements 288 --log-file daily-monitor.log
```

#### Linux Cron Job
Add to crontab:
```bash
# Run every 4 hours for 1 hour (15 measurements)
0 */4 * * * cd /home/user/wlan-scanner && python main.py --continuous -i 240 --max-measurements 15 --quiet
```

### System Monitoring Integration

#### Grafana Integration
Export data for visualization:
```bash
# Generate data for Grafana
python main.py --continuous -i 60 \
  --output-dir /opt/grafana/data/wifi \
  --log-file /var/log/wifi-monitor.log
```

#### Alert Integration
```bash
# Monitor with alert thresholds
python main.py --tests ping \
  --log-level WARNING \
  --quiet 2>&1 | grep -i "error\|warning" | \
  mail -s "WiFi Alert" admin@company.com
```

### API Integration

#### REST API Monitoring
```python
import requests
import json
import subprocess

def run_measurement():
    result = subprocess.run(['python', 'main.py', '--tests', 'ping', '--quiet'], 
                          capture_output=True, text=True)
    # Parse and send to monitoring API
    return result

# Integrate with monitoring systems
data = run_measurement()
requests.post('http://monitoring-api/metrics', json=data)
```

## Best Practices

### Measurement Frequency
- **Continuous monitoring**: 5-15 minutes for general monitoring
- **Troubleshooting**: 30 seconds to 2 minutes for detailed analysis  
- **Baseline collection**: 10-30 minutes for long-term trends
- **Stress testing**: 10-30 seconds for maximum detail

### Resource Considerations
- iPerf3 tests consume network bandwidth
- File transfer tests use storage space
- High-frequency measurements increase CPU usage
- Log files can grow large with verbose logging

### Data Management
- Rotate log files regularly
- Archive old measurement data
- Monitor disk space usage
- Compress historical data

---

For configuration details, see [`CONFIGURATION.md`](CONFIGURATION.md).  
For troubleshooting, see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).