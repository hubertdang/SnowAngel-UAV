# Project Setup

## Prerequisites

This project requires the following tools to be installed on your system:

- **GCC** – C compiler  
- **G++** – C++ compiler  
- **clang-format** – Code formatter  
- **clangd** – Language server for C/C++ (used by IDEs like VS Code)

## Installation

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install build-essential clang-format clangd -y
```

### macOS (with Homebrew)
```bash
brew install gcc clang-format clangd
```

### Verify Installation
```bash
gcc --version
g++ --version
clang-format --version
clangd --version
```

### Note
On VS Code, make you see clangd at the bottom left of your screen on your status bar. If you don't, reload your editor.

## Auto-Start Program on Boot

This section describes how to make the snow angel executable a linux service that starts when the pi boots up

1) Create the .service file
```bash
sudo nano /etc/systemd/system/snow_angel_uav.service
```

2) Copy-paste the following, changing paths and user names
```bash
[Unit]
Description=Auto Start Snow Angel UAV on Boot
After=dev-ttyACM0.device
Requires=dev-ttyACM0.device

[Service]
Type=oneshot
User=<insert_pi_userid_here>
WorkingDirectory=/path/to/build/directory
ExecStart=/path/to/snow_angel_uav_app
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

3) Apply the changes
```bash
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable snow_angel_uav.service
sudo systemctl start yoursnow_angel_uavprogram.service
```

4) Verify its working
```bash
systemctl status snow_angel_uav.service
journalctl -u snow_angel_uav.service -f
sudo reboot # Should see the program is running
```
