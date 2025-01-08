import re
import MySQLdb
from datetime import datetime
import subprocess
import time
import psutil
import threading
import json
import os
import sys
import argparse

class NetworkTracker:
    
    def __init__(self, config):
        self.db = MySQLdb.connect(
            host=config['mysql']['host'],
            user=config['mysql']['user'],
            passwd=config['mysql']['passwd']
        )
        self.cursor = self.db.cursor()
        self.setup_database(config.get("sql_setup", []))
        self.previous_net_io = None  # Store previous network I/O stats
        self.hostname_filters = config.get("hostname_filters", [])
        self.hostname_mappings = config.get("hostname_mappings", {})
        self.ip_mappings = config.get("ip_mappings", {})
        self.sleep_duration = config.get("sleep_duration", 300)  # Default to 300 if not specified
        self.interfaces = config.get("interfaces", [])  # Load interfaces from config
        self.processed_entries = set()  # Initialize processed_entries as an instance variable
        
    def load_config(self, config_path='config.json'):
        if not os.path.exists(config_path):
            print(f"Error: Configuration file '{config_path}' not found.")
            sys.exit(1)
        
        with open(config_path, 'r') as config_file:
            return json.load(config_file)
    
    def setup_database(self, sql_setup):
        try:
            for statement in sql_setup:
                self.cursor.execute(statement)
            self.db.commit()
        except Exception as e:
            print(f"Error setting up database: {e}")
    
    def parse_dnsmasq_leases(self):
        leases = []
        with open('/var/lib/misc/dnsmasq.leases', 'r') as f:
            for line in f:
                parts = line.strip().split()
                lease = {
                    'mac_address': parts[1],
                    'ip_address': parts[2],
                    'hostname': parts[3] if parts[3] != '*' else None
                }
                leases.append(lease)
        return leases
    
    def parse_ifstat(self):
        try:
            net_io = psutil.net_io_counters(pernic=True)
            if self.previous_net_io is None:
                # Initialize previous_net_io on the first run
                self.previous_net_io = net_io
                return None

            traffic = {}
            for interface in self.interfaces:
                if interface in net_io and interface in self.previous_net_io:
                    traffic[interface] = {
                        'in': (net_io[interface].bytes_recv - self.previous_net_io[interface].bytes_recv) / 1024,
                        'out': (net_io[interface].bytes_sent - self.previous_net_io[interface].bytes_sent) / 1024
                    }

            # Update previous_net_io for the next iteration
            self.previous_net_io = net_io
            return traffic
        except KeyError as e:
            print(f"Interface not found: {e}")
            return None
        except Exception as e:
            print(f"Error retrieving network stats: {e}")
            return None
    
    def monitor_syslog(self):
        try:
            with open('/var/log/syslog', 'r') as f:

                # Read the last 2000 lines
                f.seek(0, 2)  # Go to the end of the file
                file_size = f.tell()
                buffer_size = 8192
                lines = []
                block_count = 0

                while len(lines) < 2000 and file_size > 0:
                    block_count += 1

                    if file_size - buffer_size * block_count > 0:
                        f.seek(file_size - buffer_size * block_count)
                    else:
                        f.seek(0)

                    lines = f.readlines()

                # Only keep the last 2000 lines
                lines = lines[-2000:]

                # If processed_entries is empty, populate it with current syslog entries and return
                if not self.processed_entries:
                    for line in lines:
                        if 'from 10.10.10.' in line:
                            timestamp_str = line[:32]  # Adjust to capture the full timestamp with timezone
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%f%z').replace(tzinfo=None)
                            ip_match = re.search(r'from (10\.10\.10\.\d+)', line)
                            if ip_match:
                                ip_address = ip_match.group(1)
                                entry_key = (ip_address, timestamp.replace(second=0, microsecond=0))
                                self.processed_entries.add(entry_key)
                    return

                for line in lines:
                    if 'from 10.10.10.' in line:
                        timestamp_str = line[:32]  # Adjust to capture the full timestamp with timezone
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%f%z').replace(tzinfo=None)
                        ip_match = re.search(r'from (10\.10\.10\.\d+)', line)
                        if ip_match:
                            ip_address = ip_match.group(1)
                            entry_key = (ip_address, timestamp.replace(second=0, microsecond=0))

                            # Check if the entry has already been processed
                            if entry_key not in self.processed_entries:
                                self.processed_entries.add(entry_key)
                                self.update_device_activity(ip_address, timestamp)

                # Keep only the last 2000 processed entries
                if len(self.processed_entries) > 2000:
                    self.processed_entries = set(list(self.processed_entries)[-2000:])
        except Exception as e:
            print(f"Error processing syslog: {e}")
    
    def update_device_activity(self, ip_address, timestamp):
        # Round the timestamp to the nearest minute
        rounded_timestamp = timestamp.replace(second=0, microsecond=0)

        # Find device_id and hostname from IP address
        self.cursor.execute("""
            SELECT id, hostname FROM devices 
            WHERE ip_address = %s 
            ORDER BY last_seen DESC LIMIT 1
        """, (ip_address,))
        result = self.cursor.fetchone()
        
        if result:
            device_id, hostname = result

            # Use IP mapping if hostname is None
            if hostname is None:
                hostname = self.ip_mappings.get(ip_address, ip_address)  # Default to IP address if no mapping

            # Filter out hostnames based on the configuration
            if any(hostname.startswith(prefix) for prefix in self.hostname_filters):
                return

            # Map hostname if a mapping exists
            mapped_hostname = self.hostname_mappings.get(hostname, hostname)

            print(f"Device Active: {ip_address} {mapped_hostname} at {rounded_timestamp}")

            # Check if the activity period already exists with the rounded timestamp
            self.cursor.execute("""
                SELECT COUNT(*) FROM activity_periods
                WHERE device_id = %s AND timestamp = %s
            """, (device_id, rounded_timestamp))
            
            if self.cursor.fetchone()[0] == 0:
                # Insert new activity period
                self.cursor.execute("""
                    INSERT INTO activity_periods (device_id, hostname, timestamp)
                    VALUES (%s, %s, %s)
                """, (device_id, mapped_hostname, rounded_timestamp))
                
                # Update the last_seen timestamp in the devices table
                self.cursor.execute("""
                    UPDATE devices
                    SET last_seen = %s
                    WHERE id = %s
                """, (rounded_timestamp, device_id))
                
                self.db.commit()
    
    def save_traffic_data(self, traffic_data):
        timestamp = datetime.now()
        for interface, data in traffic_data.items():
            self.cursor.execute("""
                INSERT INTO traffic_data 
                (timestamp, interface_name, bytes_in, bytes_out)
                VALUES (%s, %s, %s, %s)
            """, (timestamp, interface, data['in'] * 1024, data['out'] * 1024))
        self.db.commit()
    
    def update_devices(self, leases):
        timestamp = datetime.now()
        for lease in leases:
            try:
                # Insert or update the device record
                self.cursor.execute("""
                    INSERT INTO devices 
                    (mac_address, ip_address, hostname, first_seen, last_seen)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                    hostname = COALESCE(VALUES(hostname), hostname),
                    last_seen = VALUES(last_seen)
                """, (lease['mac_address'], lease['ip_address'], lease['hostname'],
                      timestamp, timestamp))
                self.db.commit()
            except MySQLdb.Error as e:
                print(f"Error updating device: {e}")

    def run(self):
        while True:
            try:
                # Monitor syslog
                self.monitor_syslog()

                # Update device leases
                leases = self.parse_dnsmasq_leases()
                self.update_devices(leases)

                # Update traffic data
                traffic = self.parse_ifstat()
                if traffic:
                    self.save_traffic_data(traffic)

                # Wait for next iteration
                time.sleep(self.sleep_duration)

            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(self.sleep_duration)

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Network Tracker Service')
    parser.add_argument('--config', type=str, default='config.json', help='Path to the configuration file')
    args = parser.parse_args()

    # Load the configuration
    config = NetworkTracker.load_config(None, args.config)

    # Create an instance of NetworkTracker
    tracker = NetworkTracker(config)

    # Run the tracker
    tracker.run()

if __name__ == "__main__":
    main()
