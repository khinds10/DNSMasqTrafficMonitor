#!/bin/bash

# Check if the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

# Get the current directory
CURRENT_DIR=$(pwd)

# Define the service file content with the correct path
SERVICE_CONTENT="[Unit]
Description=Network Tracker Service
After=network.target

[Service]
ExecStart=/usr/bin/python3 $CURRENT_DIR/server_monitor.py
Restart=always
User=root
Group=root

[Install]
WantedBy=multi-user.target"

# Create the server_monitor.service file
echo "$SERVICE_CONTENT" > server_monitor.service

# Copy the service file to the systemd directory
sudo cp server_monitor.service /etc/systemd/system/

# Reload systemd daemon to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable server_monitor.service

# Start the service
sudo systemctl start server_monitor.service

# Check the status of the service
sudo systemctl status server_monitor.service 