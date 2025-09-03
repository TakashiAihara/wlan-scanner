#!/usr/bin/env python3
"""
Debug script to test WiFi interface detection on Windows
"""

import subprocess
import sys

def test_wifi_detection():
    """Test WiFi detection on Windows."""
    
    print("=== WiFi Interface Detection Debug ===\n")
    
    # Test 1: List all interfaces
    print("1. Listing all WiFi interfaces:")
    print("-" * 40)
    cmd = "netsh wlan show interfaces"
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
    print(result.stdout)
    print()
    
    # Test 2: Check specific interface
    interface_name = "Wi-Fi"
    print(f"2. Checking specific interface '{interface_name}':")
    print("-" * 40)
    cmd = f'netsh wlan show interfaces name="{interface_name}"'
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, encoding='utf-8', errors='replace')
    
    if result.returncode != 0:
        print(f"ERROR: Command failed with return code {result.returncode}")
        print(f"STDERR: {result.stderr}")
    else:
        print("Command succeeded!")
        print(f"Output:\n{result.stdout}")
    
    print()
    
    # Test 3: Parse the output
    print("3. Parsing the output:")
    print("-" * 40)
    
    output = result.stdout
    info = {}
    
    for line in output.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            # Print each key-value pair for debugging
            print(f"  Key: '{key}' -> Value: '{value}'")
            
            # Check for SSID (both English and Japanese)
            if 'SSID' in key and 'BSSID' not in key:
                info['ssid'] = value
                print(f"  >> Found SSID: {value}")
            
            # Check for connection state
            if '状態' in key or 'State' in key or 'Status' in key:
                info['state'] = value
                print(f"  >> Found State: {value}")
    
    print()
    print("4. Summary:")
    print("-" * 40)
    print(f"Parsed info: {info}")
    
    if 'ssid' in info and info['ssid']:
        print(f"✓ WiFi is connected to: {info['ssid']}")
        return True
    else:
        print("✗ WiFi does not appear to be connected")
        return False

if __name__ == "__main__":
    try:
        is_connected = test_wifi_detection()
        sys.exit(0 if is_connected else 1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)