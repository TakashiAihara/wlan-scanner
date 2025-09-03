"""WiFi information collector using Win32 API."""

import logging
import subprocess
import json
import platform
from typing import Optional, Dict, Any, List
from datetime import datetime
from src.models import WiFiInfo


class WiFiInfoCollector:
    """Collects wireless LAN information using platform-specific APIs."""

    def __init__(self, interface_name: str = "auto"):
        """Initialize WiFi info collector.
        
        Args:
            interface_name: Name of the wireless interface, or "auto" to auto-detect.
        """
        self.logger = logging.getLogger(__name__)
        self.platform = platform.system()
        
        # Auto-detect interface if needed
        if interface_name == "auto" or interface_name == "":
            detected = self._auto_detect_interface()
            if detected:
                self.interface_name = detected
                self.logger.info(f"Auto-detected WiFi interface: {detected}")
            else:
                # Fallback to common defaults
                if self.platform == "Windows":
                    self.interface_name = "Wi-Fi"
                elif self.platform == "Linux":
                    self.interface_name = "wlan0"
                elif self.platform == "Darwin":
                    self.interface_name = "en0"
                else:
                    self.interface_name = "Wi-Fi"
                self.logger.warning(f"Could not auto-detect interface, using default: {self.interface_name}")
        else:
            self.interface_name = interface_name
        
    def collect_wifi_info(self) -> Optional[WiFiInfo]:
        """Collect current WiFi information.
        
        Returns:
            WiFiInfo object with current wireless information, or None if failed.
        """
        try:
            if self.platform == "Windows":
                return self._collect_windows_wifi_info()
            elif self.platform == "Linux":
                return self._collect_linux_wifi_info()
            elif self.platform == "Darwin":  # macOS
                return self._collect_macos_wifi_info()
            else:
                self.logger.error(f"Unsupported platform: {self.platform}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to collect WiFi info: {e}")
            return None

    def _collect_windows_wifi_info(self) -> Optional[WiFiInfo]:
        """Collect WiFi info on Windows using netsh command.
        
        Returns:
            WiFiInfo object or None if failed.
        """
        try:
            # Get interface details
            interface_info = self._get_windows_interface_info()
            if not interface_info:
                return None
                
            # Get signal strength and quality
            signal_info = self._get_windows_signal_info()
            if not signal_info:
                return None
            
            # Combine information
            wifi_info = WiFiInfo(
                ssid=interface_info.get('ssid', 'Unknown'),
                rssi=signal_info.get('rssi', -100),
                link_quality=signal_info.get('quality', 0),
                tx_rate=interface_info.get('tx_rate', 0.0),
                rx_rate=interface_info.get('rx_rate', 0.0),
                channel=interface_info.get('channel', 0),
                frequency=self._channel_to_frequency(interface_info.get('channel', 0)),
                interface_name=self.interface_name,
                mac_address=interface_info.get('mac_address', '00:00:00:00:00:00')
            )
            
            wifi_info.validate()
            return wifi_info
            
        except Exception as e:
            self.logger.error(f"Windows WiFi collection failed: {e}")
            return None

    def _get_windows_interface_info(self) -> Dict[str, Any]:
        """Get Windows interface information using netsh.
        
        Returns:
            Dictionary with interface information.
        """
        try:
            # Get interface status
            cmd = f'netsh wlan show interfaces name="{self.interface_name}"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                self.logger.error(f"netsh command failed: {result.stderr}")
                return {}
            
            output = result.stdout
            info = {}
            
            # Parse output (supports both English and Japanese Windows)
            for line in output.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # SSID (both English and Japanese)
                    if ('SSID' in key and 'BSSID' not in key and 'AP' not in key):
                        info['ssid'] = value
                    # MAC address (BSSID)
                    elif 'BSSID' in key or 'AP BSSID' in key:
                        info['mac_address'] = value
                    # Channel (English: Channel, Japanese: チャネル)
                    elif 'Channel' in key or 'チャネル' in key:
                        try:
                            info['channel'] = int(value)
                        except ValueError:
                            pass
                    # Receive rate (English: Receive rate, Japanese: 受信速度)
                    elif 'Receive rate' in key or '受信速度' in key:
                        try:
                            # Remove (Mbps) if present
                            value = value.replace('(Mbps)', '').strip()
                            info['rx_rate'] = float(value.split()[0])
                        except (ValueError, IndexError):
                            pass
                    # Transmit rate (English: Transmit rate, Japanese: 送信速度)
                    elif 'Transmit rate' in key or '送信速度' in key:
                        try:
                            # Remove (Mbps) if present
                            value = value.replace('(Mbps)', '').strip()
                            info['tx_rate'] = float(value.split()[0])
                        except (ValueError, IndexError):
                            pass
                    # Connection state (English: State, Japanese: 状態)
                    elif 'State' in key or '状態' in key:
                        info['state'] = value
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get Windows interface info: {e}")
            return {}

    def _get_windows_signal_info(self) -> Dict[str, Any]:
        """Get Windows signal strength information.
        
        Returns:
            Dictionary with signal information.
        """
        try:
            # Get signal strength
            cmd = f'netsh wlan show interfaces name="{self.interface_name}"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                return {}
            
            output = result.stdout
            info = {}
            
            for line in output.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Signal quality (English: Signal, Japanese: シグナル)
                    if 'Signal' in key or 'シグナル' in key:
                        try:
                            # Parse percentage (e.g., "80%" or "88%")
                            quality = int(value.replace('%', ''))
                            info['quality'] = quality
                        except ValueError:
                            pass
                    # RSSI value (English: Rssi, Japanese: Rssi)
                    elif 'Rssi' in key or 'RSSI' in key:
                        try:
                            # Parse RSSI value (e.g., "-34")
                            info['rssi'] = int(value)
                        except ValueError:
                            # If RSSI not available, calculate from quality
                            if 'quality' in info:
                                info['rssi'] = self._quality_to_rssi(info['quality'])
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get Windows signal info: {e}")
            return {}

    def _collect_linux_wifi_info(self) -> Optional[WiFiInfo]:
        """Collect WiFi info on Linux using iwconfig/iw commands.
        
        Returns:
            WiFiInfo object or None if failed.
        """
        try:
            # Try using iw command first (newer)
            info = self._get_linux_iw_info()
            
            # Fallback to iwconfig if iw fails
            if not info:
                info = self._get_linux_iwconfig_info()
            
            if not info:
                return None
            
            wifi_info = WiFiInfo(
                ssid=info.get('ssid', 'Unknown'),
                rssi=info.get('rssi', -100),
                link_quality=info.get('quality', 0),
                tx_rate=info.get('tx_rate', 0.0),
                rx_rate=info.get('rx_rate', 0.0),
                channel=info.get('channel', 0),
                frequency=info.get('frequency', 0.0),
                interface_name=self.interface_name,
                mac_address=info.get('mac_address', '00:00:00:00:00:00')
            )
            
            wifi_info.validate()
            return wifi_info
            
        except Exception as e:
            self.logger.error(f"Linux WiFi collection failed: {e}")
            return None

    def _get_linux_iw_info(self) -> Dict[str, Any]:
        """Get Linux WiFi info using iw command.
        
        Returns:
            Dictionary with WiFi information.
        """
        try:
            info = {}
            
            # Get link information
            cmd = f"iw dev {self.interface_name} link"
            result = subprocess.run(cmd.split(), capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode == 0:
                output = result.stdout
                for line in output.split('\n'):
                    if 'SSID:' in line:
                        info['ssid'] = line.split('SSID:')[1].strip()
                    elif 'freq:' in line:
                        try:
                            freq = int(line.split('freq:')[1].split()[0])
                            info['frequency'] = freq / 1000.0  # Convert MHz to GHz
                            info['channel'] = self._frequency_to_channel(info['frequency'])
                        except (ValueError, IndexError):
                            pass
                    elif 'signal:' in line:
                        try:
                            rssi = int(line.split('signal:')[1].split()[0])
                            info['rssi'] = rssi
                            info['quality'] = self._rssi_to_quality(rssi)
                        except (ValueError, IndexError):
                            pass
                    elif 'tx bitrate:' in line:
                        try:
                            rate = float(line.split('tx bitrate:')[1].split()[0])
                            info['tx_rate'] = rate
                        except (ValueError, IndexError):
                            pass
            
            # Get MAC address
            cmd = f"ip link show {self.interface_name}"
            result = subprocess.run(cmd.split(), capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode == 0:
                output = result.stdout
                for line in output.split('\n'):
                    if 'link/ether' in line:
                        parts = line.split()
                        idx = parts.index('link/ether')
                        if idx + 1 < len(parts):
                            info['mac_address'] = parts[idx + 1]
            
            # Set rx_rate same as tx_rate (approximation)
            if 'tx_rate' in info:
                info['rx_rate'] = info['tx_rate']
            
            return info
            
        except Exception as e:
            self.logger.debug(f"iw command failed: {e}")
            return {}

    def _get_linux_iwconfig_info(self) -> Dict[str, Any]:
        """Get Linux WiFi info using iwconfig command (fallback).
        
        Returns:
            Dictionary with WiFi information.
        """
        try:
            cmd = f"iwconfig {self.interface_name}"
            result = subprocess.run(cmd.split(), capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                return {}
            
            output = result.stdout
            info = {}
            
            # Parse iwconfig output
            for line in output.split('\n'):
                if 'ESSID:' in line:
                    essid = line.split('ESSID:')[1].strip().strip('"')
                    info['ssid'] = essid
                elif 'Frequency:' in line:
                    try:
                        freq_str = line.split('Frequency:')[1].split()[0]
                        info['frequency'] = float(freq_str)
                        info['channel'] = self._frequency_to_channel(info['frequency'])
                    except (ValueError, IndexError):
                        pass
                elif 'Link Quality=' in line:
                    try:
                        quality_str = line.split('Link Quality=')[1].split()[0]
                        if '/' in quality_str:
                            current, max_val = quality_str.split('/')
                            quality = int((float(current) / float(max_val)) * 100)
                            info['quality'] = quality
                            info['rssi'] = self._quality_to_rssi(quality)
                    except (ValueError, IndexError):
                        pass
                elif 'Bit Rate=' in line:
                    try:
                        rate = float(line.split('Bit Rate=')[1].split()[0])
                        info['tx_rate'] = rate
                        info['rx_rate'] = rate
                    except (ValueError, IndexError):
                        pass
            
            # Get MAC address
            cmd = f"ip link show {self.interface_name}"
            result = subprocess.run(cmd.split(), capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'link/ether' in line:
                        parts = line.split()
                        idx = parts.index('link/ether')
                        if idx + 1 < len(parts):
                            info['mac_address'] = parts[idx + 1]
            
            return info
            
        except Exception as e:
            self.logger.debug(f"iwconfig command failed: {e}")
            return {}

    def _collect_macos_wifi_info(self) -> Optional[WiFiInfo]:
        """Collect WiFi info on macOS using airport command.
        
        Returns:
            WiFiInfo object or None if failed.
        """
        try:
            # Use airport utility
            cmd = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -I"
            result = subprocess.run(cmd.split(), capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                return None
            
            output = result.stdout
            info = {}
            
            for line in output.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == 'SSID':
                        info['ssid'] = value
                    elif key == 'BSSID':
                        info['mac_address'] = value
                    elif key == 'channel':
                        try:
                            info['channel'] = int(value.split(',')[0])
                        except (ValueError, IndexError):
                            pass
                    elif key == 'agrCtlRSSI':
                        try:
                            info['rssi'] = int(value)
                            info['quality'] = self._rssi_to_quality(int(value))
                        except ValueError:
                            pass
                    elif key == 'lastTxRate':
                        try:
                            info['tx_rate'] = float(value)
                            info['rx_rate'] = float(value)  # Approximation
                        except ValueError:
                            pass
            
            if 'channel' in info:
                info['frequency'] = self._channel_to_frequency(info['channel'])
            
            if not info:
                return None
            
            wifi_info = WiFiInfo(
                ssid=info.get('ssid', 'Unknown'),
                rssi=info.get('rssi', -100),
                link_quality=info.get('quality', 0),
                tx_rate=info.get('tx_rate', 0.0),
                rx_rate=info.get('rx_rate', 0.0),
                channel=info.get('channel', 0),
                frequency=info.get('frequency', 0.0),
                interface_name=self.interface_name,
                mac_address=info.get('mac_address', '00:00:00:00:00:00')
            )
            
            wifi_info.validate()
            return wifi_info
            
        except Exception as e:
            self.logger.error(f"macOS WiFi collection failed: {e}")
            return None

    def _channel_to_frequency(self, channel: int) -> float:
        """Convert WiFi channel to frequency in GHz.
        
        Args:
            channel: WiFi channel number.
            
        Returns:
            Frequency in GHz.
        """
        if 1 <= channel <= 14:
            # 2.4 GHz band
            if channel == 14:
                return 2.484
            else:
                return 2.407 + (channel * 0.005)
        elif 36 <= channel <= 165:
            # 5 GHz band
            return 5.000 + (channel * 0.005)
        else:
            return 0.0

    def _frequency_to_channel(self, frequency: float) -> int:
        """Convert frequency in GHz to WiFi channel.
        
        Args:
            frequency: Frequency in GHz.
            
        Returns:
            WiFi channel number.
        """
        if 2.4 <= frequency <= 2.5:
            # 2.4 GHz band
            if abs(frequency - 2.484) < 0.001:
                return 14
            else:
                return int(round((frequency - 2.407) / 0.005))
        elif 5.0 <= frequency <= 5.9:
            # 5 GHz band
            return int(round((frequency - 5.000) / 0.005))
        else:
            return 0

    def _rssi_to_quality(self, rssi: int) -> int:
        """Convert RSSI to quality percentage.
        
        Args:
            rssi: RSSI value in dBm.
            
        Returns:
            Quality percentage (0-100).
        """
        if rssi <= -100:
            return 0
        elif rssi >= -50:
            return 100
        else:
            return 2 * (rssi + 100)

    def _quality_to_rssi(self, quality: int) -> int:
        """Convert quality percentage to approximate RSSI.
        
        Args:
            quality: Quality percentage (0-100).
            
        Returns:
            Approximate RSSI value in dBm.
        """
        if quality <= 0:
            return -100
        elif quality >= 100:
            return -50
        else:
            return int((quality / 2) - 100)

    def get_available_interfaces(self) -> List[str]:
        """Get list of available network interfaces.
        
        Returns:
            List of interface names.
        """
        interfaces = []
        
        try:
            if self.platform == "Windows":
                cmd = "netsh wlan show interfaces"
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Name' in line and ':' in line:
                            name = line.split(':')[1].strip()
                            interfaces.append(name)
                            
            elif self.platform == "Linux":
                cmd = "ip link show"
                result = subprocess.run(cmd.split(), capture_output=True, text=True, encoding='utf-8', errors='replace')
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if ':' in line and 'mtu' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                name = parts[1].strip()
                                if name and not name.startswith('lo'):
                                    interfaces.append(name)
                                    
            elif self.platform == "Darwin":
                cmd = "ifconfig -l"
                result = subprocess.run(cmd.split(), capture_output=True, text=True, encoding='utf-8', errors='replace')
                
                if result.returncode == 0:
                    interfaces = result.stdout.strip().split()
                    
        except Exception as e:
            self.logger.error(f"Failed to get interfaces: {e}")
        
        return interfaces

    def _auto_detect_interface(self) -> Optional[str]:
        """Auto-detect the first available WiFi interface.
        
        Returns:
            Interface name if found, None otherwise.
        """
        try:
            if self.platform == "Windows":
                cmd = "netsh wlan show interfaces"
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
                
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        # Look for "Name" or "名前" (Japanese)
                        if ('Name' in line or '名前' in line) and ':' in line:
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                interface = parts[1].strip()
                                # Check if it's connected
                                check_cmd = f'netsh wlan show interfaces name="{interface}"'
                                check_result = subprocess.run(check_cmd, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
                                if check_result.returncode == 0:
                                    # Check for connected state
                                    if '接続されました' in check_result.stdout or 'connected' in check_result.stdout.lower():
                                        return interface
                                    
            elif self.platform == "Linux":
                # Try iwconfig first
                try:
                    result = subprocess.run("iwconfig", capture_output=True, text=True, encoding='utf-8', errors='replace')
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'IEEE 802.11' in line:
                                interface = line.split()[0]
                                return interface
                except:
                    pass
                    
                # Fallback to ip link
                result = subprocess.run("ip link show", capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'wlan' in line.lower() or 'wlp' in line.lower():
                            parts = line.split(':')
                            if len(parts) >= 2:
                                return parts[1].strip()
                                
            elif self.platform == "Darwin":
                # macOS
                result = subprocess.run("networksetup -listallhardwareports", capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for i, line in enumerate(lines):
                        if 'Wi-Fi' in line:
                            # Next line should have the device
                            if i + 1 < len(lines):
                                device_line = lines[i + 1]
                                if 'Device:' in device_line:
                                    return device_line.split('Device:')[1].strip()
                                    
        except Exception as e:
            self.logger.debug(f"Auto-detect failed: {e}")
            
        return None
    
    def is_connected(self) -> bool:
        """Check if WiFi is connected.
        
        Returns:
            True if connected, False otherwise.
        """
        try:
            wifi_info = self.collect_wifi_info()
            return wifi_info is not None and wifi_info.ssid != "Unknown"
        except:
            return False