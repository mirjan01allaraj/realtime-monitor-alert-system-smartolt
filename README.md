# SmartOLT Real-Time Monitor Alert System

SmartOLT real-time monitoring suite with Chrome extension, desktop controller, and Telegram alerts for proactive network management.

## Overview

This project is an all-in-one SmartOLT monitoring toolkit designed to track key dashboard metrics in real time and notify the operator when network conditions change.

It combines:

- a **Chrome extension** for reading SmartOLT dashboard values
- a **Flask backend** for processing monitor updates
- a **desktop GUI controller** for logs, controls, and tray monitoring
- **Telegram + desktop notifications** for instant alerts

## Features

- Real-time SmartOLT dashboard monitoring
- Multi-region selector with saved regions
- Chrome extension popup controls
- Desktop GUI controller
- Telegram alert support
- Desktop toast notifications
- System log and notification log
- Tray icons for online/offline values
- Test notification support
- Local backend communication through `127.0.0.1:5005`

## Project Structure

  
smartolt-monitor/
├── backend/
│   ├── monitor_server.py
│   ├── smartolt_monitor_app.py
│   ├── telegram_config.example.json
│
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── popup.js
│   ├── popup.html
│
├── .gitignore
└── README.md

Requirements
Backend / Desktop App
Python 3.10+
Google Chrome
Windows OS recommended (desktop notifications and tray integration)
Python packages

Install the required packages:

pip install flask flask-cors requests customtkinter pystray pillow win10toast-click
Setup
1. Clone the repository
git clone https://github.com/mirjan01allaraj/realtime-monitor-alert-system-smartolt.git
cd realtime-monitor-alert-system-smartolt

Running the Project
1. Start the backend / desktop controller

From the backend folder:

cd backend
python smartolt_monitor_app.py

This starts the desktop controller and the local backend server.

2. Load the Chrome extension
Open Chrome
Go to chrome://extensions/
Enable Developer Mode
Click Load unpacked
Select the extension/ folder
How to Use
Open your SmartOLT dashboard in Chrome
Open the extension popup
Add and pick the dashboard regions you want to monitor
Save labels/selectors
Click START
Keep the desktop controller running
Receive alerts on desktop and Telegram when values change
Alert Logic

The backend compares current SmartOLT values with previous values and triggers notifications on changes such as:

offline increase
online decrease
restoration of connectivity
improvement in network state
Notes
The extension communicates with a local backend at http://127.0.0.1:5005
This project is intended for local/private operational use
Backend must be running for the extension to work correctly
Roadmap Ideas
packaged Windows executable
configurable alert rules
database log history
multi-device monitoring
web dashboard for remote control
installer for backend + extension setup
Author

Created by Mallaraj

