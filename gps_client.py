#!/usr/bin/env python3
"""
GPS Client — Discover and read from ESP8266 GPS units on the network.

Usage:
  python3 gps_client.py                    # Discover and read once
  python3 gps_client.py --watch            # Continuous reading (10 sec intervals)
  python3 gps_client.py --host esp8266-gps.local  # Direct connection
"""

import socket
import sys
import time
import json
import argparse
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange

SERVICE_TYPE = "_gps._tcp.local."

gps_units = {}


def on_service_state_change(zeroconf, service_type, name, state_change):
    """Called when a GPS unit appears or disappears on the network."""
    if state_change == ServiceStateChange.Added:
        info = zeroconf.get_service_info(service_type, name)
        if info:
            ip = socket.inet_ntoa(info.addresses[0])
            port = info.port
            url = f"http://{ip}:{port}/gps"
            gps_units[name] = {
                "url": url,
                "ip": ip,
                "port": port,
                "hostname": name.replace("._gps._tcp.local.", ""),
            }
            print(f"✓ Found GPS unit: {name}")
            print(f"  URL: {url}")

    elif state_change == ServiceStateChange.Removed:
        if name in gps_units:
            print(f"✗ GPS unit disconnected: {name}")
            del gps_units[name]


def discover_gps_units(timeout=3):
    """Discover GPS units on the network via mDNS."""
    print(f"Scanning for GPS units ({timeout}s)...")
    print()

    zeroconf = Zeroconf()
    browser = ServiceBrowser(zeroconf, SERVICE_TYPE, handlers=[on_service_state_change])

    time.sleep(timeout)

    zeroconf.close()

    if not gps_units:
        print("No GPS units found on the network.")
        print()
        print("Troubleshooting:")
        print("  1. Verify ESP8266 is powered on and connected to GREEN-BEAN WiFi")
        print("  2. Check that mDNS/Bonjour is installed:")
        print("     Ubuntu/Debian: sudo apt install avahi-daemon")
        print("     macOS: Should be built-in")
        print("     Windows: Install Bonjour (iTunes, or standalone)")
        print("  3. On Pi, verify mDNS is advertising:")
        print("     avahi-browse -rtp _gps._tcp")
        return None

    print(f"Found {len(gps_units)} GPS unit(s)")
    print()
    return gps_units


def read_gps_direct(host, port=80):
    """Read GPS data directly from a host/IP (no discovery)."""
    try:
        import requests

        url = f"http://{host}/gps"
        print(f"Connecting to {url}...")
        print()

        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            print_gps_data(data, host)
            return data
        elif response.status_code == 503:
            print(f"⚠ GPS unit {host} has no fix yet")
            print(f"  Response: {response.text}")
            return None
        else:
            print(f"✗ Error: HTTP {response.status_code}")
            print(f"  Response: {response.text}")
            return None

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None


def read_gps_from_url(url):
    """Read GPS data from a specific URL."""
    try:
        import requests

        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            hostname = url.split("//")[1].split(":")[0]
            print_gps_data(data, hostname)
            return data
        elif response.status_code == 503:
            print(f"⚠ No GPS fix available yet")
            return None
        else:
            print(f"✗ Error: HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return None


def print_gps_data(data, source):
    """Pretty-print GPS data."""
    print("╔═══════════════════════════════════════╗")
    print(f"║ GPS Data from: {source:<26} ║")
    print("╠═══════════════════════════════════════╣")

    if "error" in data:
        print(f"║ ✗ Error: {data['error']:<28} ║")
    else:
        print(f"║ Latitude:  {data.get('lat', 'N/A'):<28} ║")
        print(f"║ Longitude: {data.get('lng', 'N/A'):<28} ║")
        print(f"║ Satellites: {str(data.get('satellites', 'N/A')):<27} ║")
        print(f"║ HDOP: {str(data.get('hdop', 'N/A')):<32} ║")
        print(f"║ Date: {data.get('date', 'N/A'):<32} ║")
        print(f"║ Time: {data.get('time', 'N/A'):<32} ║")
        print(f"║ Fix: {str(data.get('fix', 'N/A')):<33} ║")

    print("╚═══════════════════════════════════════╝")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Read GPS data from ESP8266 GPS units",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover and read from first available GPS unit
  python3 gps_client.py
  
  # Continuously read every 10 seconds
  python3 gps_client.py --watch
  
  # Connect directly to a known host
  python3 gps_client.py --host esp8266-gps.local
  
  # Connect directly by IP
  python3 gps_client.py --host 10.42.0.123
        """,
    )

    parser.add_argument(
        "--host",
        help="Connect directly to host/IP (skip discovery)",
        type=str,
    )
    parser.add_argument(
        "--watch",
        help="Continuously read GPS every 10 seconds",
        action="store_true",
    )
    parser.add_argument(
        "--interval",
        help="Poll interval in seconds (default: 10)",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--timeout",
        help="Discovery timeout in seconds (default: 3)",
        type=int,
        default=3,
    )

    args = parser.parse_args()

    # Try to import requests
    try:
        import requests
    except ImportError:
        print("ERROR: 'requests' library not installed")
        print("Install it with: pip install requests")
        sys.exit(1)

    # Direct connection mode
    if args.host:
        print(f"Direct connection mode: {args.host}")
        print()

        if args.watch:
            print(f"Reading every {args.interval} seconds (Ctrl+C to stop)")
            print()
            try:
                while True:
                    read_gps_direct(args.host)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nStopped.")
        else:
            read_gps_direct(args.host)

    # Discovery mode
    else:
        units = discover_gps_units(timeout=args.timeout)

        if not units:
            sys.exit(1)

        # Select first unit
        first_unit = list(units.values())[0]
        url = first_unit["url"]
        hostname = first_unit["hostname"]

        if args.watch:
            print(f"Continuous reading from {hostname}")
            print(f"Reading every {args.interval} seconds (Ctrl+C to stop)")
            print()
            try:
                while True:
                    read_gps_from_url(url)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nStopped.")
        else:
            read_gps_from_url(url)


if __name__ == "__main__":
    main()
