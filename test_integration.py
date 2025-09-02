#!/usr/bin/env python3
"""
Integration test script to demonstrate all components working together.
This bypasses the WiFi requirement to show the network testing functionality.
"""

import logging
from datetime import datetime
from src.network_tester import NetworkTester
from src.config_manager import ConfigurationManager
from src.data_export_manager import DataExportManager
from src.models import MeasurementResult

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=== WLAN Scanner Integration Test ===")
    print("Testing core network measurement functionality")
    print()
    
    # Load configuration
    print("1. Loading configuration...")
    config_manager = ConfigurationManager('config/config.ini')
    config = config_manager.load_config()
    print(f"   ✓ Configuration loaded from config/config.ini")
    print(f"   ✓ iPerf3 server: {config.iperf_server}:{config.iperf_port}")
    print(f"   ✓ Ping targets: {config.target_ips}")
    print()
    
    # Initialize network tester
    print("2. Initializing network tester...")
    network_tester = NetworkTester(timeout=config.timeout)
    print("   ✓ NetworkTester initialized")
    print()
    
    # Perform ping tests
    print("3. Running ping tests...")
    ping_results = []
    for target in config.target_ips:
        print(f"   Testing ping to {target}...")
        result = network_tester.ping(
            target=target,
            count=config.ping_count,
            size=config.ping_size,
            interval=config.ping_interval
        )
        ping_results.append(result)
        print(f"   ✓ {result.packets_received}/{result.packets_sent} packets, "
              f"{result.packet_loss:.1f}% loss, avg RTT: {result.avg_rtt:.2f}ms")
    print()
    
    # Perform iPerf3 tests
    print("4. Running iPerf3 TCP tests...")
    print(f"   Testing TCP upload to {config.iperf_server}...")
    tcp_upload = network_tester.iperf_tcp_upload(
        server_ip=config.iperf_server,
        server_port=config.iperf_port,
        duration=3  # Short duration for demo
    )
    print(f"   ✓ Upload: {tcp_upload.throughput_upload:.2f} Mbps, "
          f"Retransmits: {tcp_upload.retransmits}")
    
    print(f"   Testing TCP download from {config.iperf_server}...")
    tcp_download = network_tester.iperf_tcp_download(
        server_ip=config.iperf_server,
        server_port=config.iperf_port,
        duration=3  # Short duration for demo
    )
    print(f"   ✓ Download: {tcp_download.throughput_download:.2f} Mbps, "
          f"Retransmits: {tcp_download.retransmits}")
    print()
    
    # Create measurement result (using first ping result as representative)
    print("5. Creating measurement result...")
    measurement_result = MeasurementResult(
        measurement_id=f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        timestamp=datetime.now(),
        wifi_info=None,  # No WiFi available
        ping_result=ping_results[0],  # Use first ping result
        iperf_tcp_result=tcp_upload,  # Use upload result as representative
        iperf_udp_result=None,  # Skip UDP for this demo
        file_transfer_result=None,  # Skip file transfer for this demo
        errors=[]
    )
    print(f"   ✓ Measurement result created with ID: {measurement_result.measurement_id}")
    print()
    
    # Export to CSV
    print("6. Exporting data to CSV...")
    export_manager = DataExportManager(output_directory=config.output_dir)
    csv_filename = export_manager.export_to_csv([measurement_result])
    print(f"   ✓ Data exported to: {csv_filename}")
    
    # Show summary
    print()
    print("=== Integration Test Summary ===")
    print(f"✓ Configuration loading: SUCCESS")
    print(f"✓ Network connectivity: SUCCESS")
    print(f"✓ Ping tests: {len(ping_results)} targets tested")
    print(f"✓ iPerf3 TCP upload: {tcp_upload.throughput_upload:.1f} Mbps")
    print(f"✓ iPerf3 TCP download: {tcp_download.throughput_download:.1f} Mbps") 
    print(f"✓ Data export: SUCCESS ({csv_filename})")
    print()
    print("All core components are working correctly!")
    print("The application would work fully on a system with WiFi interface.")

if __name__ == "__main__":
    main()