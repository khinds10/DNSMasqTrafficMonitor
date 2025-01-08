# Network Tracker Service

The Network Tracker Service is a Linux service to monitor and track network devices using a Python script (`server_monitor.py`) configured as a systemd service on Linux systems. This service efficiently logs device activity, tracks network traffic, and provides detailed insights into network usage.

## Features

- **Device Monitoring**: Automatically detects and logs devices connected to the network.
- **Traffic Analysis**: Records network traffic data for comprehensive analysis.
- **Customizable Configuration**: Easily configure MySQL database settings, hostname filters, hostname mappings, IP mappings, SQL setup commands, sleep duration, and network interfaces.
- **Systemd Integration**: Seamlessly integrates with systemd for reliable service management.
- **Automatic Restart**: Configured to restart automatically in case of failure, ensuring continuous monitoring.

## Prerequisites

- Ensure you have Python 3 installed on your system.
- Ensure you have the necessary permissions to create and manage systemd services.

## Required Packages

Before running the `server_monitor.service`, ensure the following packages are installed:

```bash
sudo apt install mysql-server
sudo apt install python3-mysql.connector
sudo pip3 install mysql-connector-python
sudo apt install python3-mysqldb
``` 

## Configuration

Before running the service, you need to create a `config.json` file with your specific settings. You can use the `config.json-example` file as a template. Copy it and modify the values as needed:

```bash
cp config.json-example config.json
```

Edit the `config.json` file to include your MySQL credentials, hostname filters, hostname mappings, IP mappings, SQL setup commands, sleep duration, and the network interfaces you want to monitor.

## Installation Steps

1. **Set Execute Permissions**

   Make the `install.sh` script executable:

   ```bash
   chmod +x install.sh
   ```

2. **Run the Installation Script as Root**

   Execute the `install.sh` script with root privileges to set up the service:

   ```bash
   sudo ./install.sh
   ```

## Manual Installation Steps

1. **Copy the Service File**

   Copy the `server_monitor.service` file to the systemd directory (make sure you have the correct file path for the service python file):

   ```bash
   sudo cp server_monitor.service /etc/systemd/system/
   ```

2. **Reload Systemd Daemon**

   Reload the systemd daemon to recognize the new service:

   ```bash
   sudo systemctl daemon-reload
   ```

3. **Enable the Service**

   Enable the service to start on boot:

   ```bash
   sudo systemctl enable server_monitor.service
   ```

4. **Start the Service**

   Start the service:

   ```bash
   sudo systemctl start server_monitor.service
   ```

5. **Check Service Status**

   Check the status of the service to ensure it is running:

   ```bash
   sudo systemctl status server_monitor.service
   ```

## Notes

- The service is configured to automatically restart if it fails.
- Ensure the paths in the `server_monitor.service` file are correct.
- You can view logs for the service using `journalctl`:

  ```bash
  sudo journalctl -u server_monitor.service
  ```

## Uninstallation

To remove the service, disable and stop it, then remove the service file:

```bash
sudo systemctl disable server_monitor.service
sudo systemctl stop server_monitor.service
sudo rm /etc/systemd/system/server_monitor.service
sudo systemctl daemon-reload
```