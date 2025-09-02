# Troubleshooting Guide

This guide provides solutions for common issues encountered with the Wireless LAN Scanner and Performance Analyzer.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Issues](#installation-issues)
- [Configuration Problems](#configuration-problems)
- [WiFi Collection Issues](#wifi-collection-issues)
- [Network Testing Problems](#network-testing-problems)
- [iPerf3 Issues](#iperf3-issues)
- [File Transfer Problems](#file-transfer-problems)
- [Performance Issues](#performance-issues)
- [Platform-Specific Issues](#platform-specific-issues)
- [Error Messages](#error-messages)

## Quick Diagnostics

Start troubleshooting with these basic diagnostic commands:

### System Check
```bash
# Validate configuration
python main.py --validate-config

# Check prerequisites  
python main.py --check-prerequisites

# Dry run without executing tests
python main.py --dry-run

# Debug mode with verbose logging
python main.py --log-level DEBUG -v
```

### Connection Test
```bash
# Test basic connectivity
python main.py --tests ping --timeout 5 -v

# Test WiFi information only
python main.py --tests wifi_info -v

# Minimal test
python main.py --tests wifi_info,ping --quiet
```

## Installation Issues

### Python Dependencies

**Problem**: Import errors or missing modules
```
ModuleNotFoundError: No module named 'pythonping'
```

**Solution**:
```bash
# Verify Python version (3.7+ required)
python --version

# Install/reinstall dependencies
pip install -r requirements.txt

# Or install individually
pip install pythonping iperf3 configparser pywin32
```

**Problem**: Permission errors during installation
```
ERROR: Could not install packages due to an EnvironmentError
```

**Solution**:
```bash
# Use user installation
pip install --user -r requirements.txt

# Or use virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### System Dependencies

**Problem**: iPerf3 not found
```
Command 'iperf3' not found
```

**Solution**:

**Windows**:
```bash
# Download from https://iperf.fr/iperf-download.php
# Or use Chocolatey:
choco install iperf3

# Or use Scoop:
scoop install iperf3
```

**Linux**:
```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install iperf3

# RHEL/CentOS/Fedora
sudo yum install iperf3
# or
sudo dnf install iperf3
```

## Configuration Problems

### Configuration File Not Found

**Problem**:
```
Configuration file not found: config/config.ini
```

**Solution**:
```bash
# Create default configuration
python main.py --create-config

# Or create at specific location
python main.py --create-config -c /path/to/config.ini
```

### Invalid Configuration Values

**Problem**:
```
ValueError: Invalid log level: VERBOSE
```

**Solution**:
```ini
# Fix invalid values in config.ini
[output]
log_level = INFO  # Must be: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Problem**:
```
ValueError: Scan interval must be positive
```

**Solution**:
```ini
# Ensure positive numeric values
[network]
scan_interval = 60    # Must be > 0
timeout = 10          # Must be > 0
```

### Network Address Issues

**Problem**:
```
Invalid IP address format: 192.168.1
```

**Solution**:
```ini
# Use complete IP addresses
[network]
target_ips = 192.168.1.1, 8.8.8.8  # Not: 192.168.1

[measurement]
iperf_server = 192.168.1.100        # Complete IP required
```

## WiFi Collection Issues

### No WiFi Interface Detected

**Problem**:
```
WiFi interface 'Wi-Fi' not found
```

**Solution**:

**Windows**:
```bash
# List available interfaces
netsh interface show interface

# Update configuration with correct name
# config.ini:
[network]
interface_name = WiFi            # Try: WiFi, Wi-Fi, Wireless Network Connection
```

**Linux**:
```bash
# List wireless interfaces
iwconfig
# or
ip link show

# Update configuration
# config.ini:
[network]
interface_name = wlan0           # Try: wlan0, wlp2s0, wifi0
```

### WiFi Not Connected

**Problem**:
```
No active WiFi connection detected
```

**Solution**:
1. Ensure WiFi is connected to a network
2. Check WiFi adapter is enabled
3. Verify network connectivity:
```bash
# Test basic connectivity
ping 8.8.8.8

# Check interface status (Linux)
iwconfig wlan0

# Check interface status (Windows)
netsh wlan show interface
```

### Permission Issues

**Problem**: Access denied to WiFi information

**Linux Solution**:
```bash
# Run with appropriate privileges
sudo python main.py --tests wifi_info

# Or add user to netdev group
sudo usermod -a -G netdev $USER
```

**Windows Solution**:
- Run Command Prompt as Administrator
- Ensure WiFi service is running

## Network Testing Problems

### Ping Test Failures

**Problem**: All ping tests fail
```
Ping test failed: Network unreachable
```

**Solution**:
1. **Check network connectivity**:
```bash
# Test manual ping
ping 8.8.8.8
ping 192.168.1.1
```

2. **Verify target IPs in configuration**:
```ini
# Use reachable targets
[network]
target_ips = 192.168.1.1, 8.8.8.8  # Ensure these are reachable
```

3. **Check firewall settings**:
- Ensure ICMP is allowed
- Check Windows Firewall or Linux iptables

### High Packet Loss

**Problem**: Consistent packet loss in ping tests

**Solution**:
1. **Adjust ping parameters**:
```ini
[measurement]
ping_count = 20        # Increase sample size
ping_interval = 2.0    # Increase interval
ping_size = 32         # Use standard size
```

2. **Check network conditions**:
- Test during different times
- Check for network congestion
- Verify WiFi signal strength

### DNS Resolution Issues

**Problem**: Hostnames not resolving

**Solution**:
```ini
# Use IP addresses instead of hostnames
[network]
target_ips = 8.8.8.8, 1.1.1.1     # Instead of google.com, cloudflare.com

[measurement]
iperf_server = 192.168.1.100       # Instead of server.local
```

## iPerf3 Issues

### iPerf3 Server Not Running

**Problem**:
```
Connection refused: iPerf3 server not reachable
```

**Solution**:
1. **Start iPerf3 server**:
```bash
# Default port (5201)
iperf3 -s

# Custom port
iperf3 -s -p 5202
```

2. **Verify server is listening**:
```bash
# Check if port is open
netstat -an | grep 5201
# or
ss -tuln | grep 5201
```

### Firewall Blocking iPerf3

**Problem**: Connection timeouts to iPerf3 server

**Solution**:

**Windows Firewall**:
```bash
# Allow iPerf3 through firewall
netsh advfirewall firewall add rule name="iPerf3" dir=in action=allow protocol=TCP localport=5201
```

**Linux iptables**:
```bash
# Allow iPerf3 port
sudo iptables -A INPUT -p tcp --dport 5201 -j ACCEPT

# For UFW
sudo ufw allow 5201
```

### iPerf3 Performance Issues

**Problem**: Unexpectedly low throughput results

**Solution**:
1. **Increase test duration**:
```ini
[measurement]
iperf_duration = 30    # Longer test for stable results
```

2. **Adjust parallel streams**:
```ini
[measurement]
iperf_parallel = 4     # Multiple streams may improve performance
```

3. **Check network utilization**:
- Ensure no other bandwidth-heavy applications
- Test during low-usage periods

### UDP Bandwidth Issues

**Problem**: UDP tests showing packet loss

**Solution**:
```ini
# Reduce UDP bandwidth target
[measurement]
iperf_udp_bandwidth = 50M    # Reduce from higher values
```

## File Transfer Problems

### File Server Unreachable

**Problem**:
```
File server connection failed: Connection refused
```

**Solution**:
1. **Verify server accessibility**:
```bash
# Test connectivity
ping 192.168.1.100

# Test specific service
telnet 192.168.1.100 445  # SMB
telnet 192.168.1.100 21   # FTP
telnet 192.168.1.100 80   # HTTP
```

2. **Check service status**:
```bash
# Windows - check SMB service
sc query lanmanserver

# Linux - check Samba
systemctl status smbd
```

### Authentication Issues

**Problem**: Access denied to file server

**Solution**:
1. **For SMB/CIFS**:
- Ensure proper share permissions
- Check user authentication
- Verify Windows file sharing is enabled

2. **For FTP**:
- Check FTP user credentials
- Ensure FTP service allows anonymous access if needed

### Disk Space Issues

**Problem**:
```
File transfer failed: Insufficient disk space
```

**Solution**:
1. **Check available space**:
```bash
# Check disk space
df -h                  # Linux
dir                    # Windows
```

2. **Reduce test file size**:
```ini
[measurement]
file_size_mb = 50      # Reduce from larger values
```

## Performance Issues

### Slow Measurement Execution

**Problem**: Measurements taking too long

**Solution**:
1. **Reduce test duration**:
```ini
[measurement]
ping_count = 5         # Reduce from 10
iperf_duration = 5     # Reduce from 10
```

2. **Increase timeouts if needed**:
```ini
[network]
timeout = 15           # Increase if operations timeout
```

3. **Disable unnecessary tests**:
```bash
# Run only essential tests
python main.py --tests wifi_info,ping
```

### High CPU Usage

**Problem**: Application consuming excessive CPU

**Solution**:
1. **Reduce measurement frequency**:
```bash
# Increase interval in continuous mode
python main.py --continuous -i 300  # 5 minutes instead of 60 seconds
```

2. **Reduce concurrent operations**:
```ini
[measurement]
iperf_parallel = 1     # Single stream instead of multiple
```

### Memory Usage

**Problem**: High memory consumption

**Solution**:
1. **Reduce logging verbosity**:
```ini
[output]
verbose = false
log_level = WARNING    # Reduce from DEBUG/INFO
```

2. **Limit measurement history**:
- Archive old measurement files
- Use log rotation

## Platform-Specific Issues

### Windows Issues

**Problem**: WiFi API access failures
```
Access denied to WiFi information
```

**Solution**:
1. Run as Administrator
2. Check Windows WiFi service:
```cmd
sc query wlansvc
sc start wlansvc
```

**Problem**: pywin32 import errors

**Solution**:
```bash
# Reinstall pywin32
pip uninstall pywin32
pip install pywin32

# Run post-install script
python Scripts/pywin32_postinstall.py -install
```

### Linux Issues

**Problem**: WiFi information not available
```
WiFi collection failed: nl80211 not supported
```

**Solution**:
```bash
# Install wireless tools
sudo apt-get install wireless-tools iw

# Check kernel modules
lsmod | grep cfg80211
```

**Problem**: Permission denied for network operations

**Solution**:
```bash
# Run with sudo (temporary)
sudo python main.py

# Or configure capabilities (permanent)
sudo setcap cap_net_raw+ep /usr/bin/python3
```

## Error Messages

### Common Error Patterns

#### Configuration Errors
```
ConfigError: Invalid configuration section 'netwrok'
```
**Solution**: Fix typo in section name (`[network]`)

#### Network Errors
```
NetworkError: Host unreachable: 192.168.1.100
```
**Solution**: Verify IP address and network connectivity

#### Timeout Errors
```
TimeoutError: Operation timed out after 10 seconds
```
**Solution**: Increase timeout or check network conditions

#### Permission Errors
```
PermissionError: Access denied to WiFi interface
```
**Solution**: Run with appropriate privileges or fix permissions

### Debug Mode Analysis

Enable debug mode for detailed error information:
```bash
python main.py --log-level DEBUG -v --tests wifi_info
```

This will provide:
- Detailed operation logs
- API call traces
- Network communication details
- Configuration parsing information

### Log File Analysis

Check log files for persistent issues:
```bash
# View recent errors
tail -f /path/to/logfile.log | grep ERROR

# Search for specific issues
grep -i "timeout\|error\|failed" /path/to/logfile.log
```

## Getting Help

If issues persist after trying these solutions:

1. **Check the GitHub Issues**: Review existing issues for similar problems
2. **Create detailed bug report**: Include configuration, error messages, and system information
3. **Provide debug logs**: Use `--log-level DEBUG -v` for detailed information
4. **Include system details**: OS version, Python version, network setup

### System Information Collection
```bash
# Collect system information for bug reports
python --version
pip list | grep -E "(pythonping|iperf3|configparser)"
uname -a          # Linux
systeminfo        # Windows
```

---

For configuration reference, see [`CONFIGURATION.md`](CONFIGURATION.md).  
For usage examples, see [`USAGE.md`](USAGE.md).