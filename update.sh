#!/bin/bash
# ==========================================================================
# update.sh — The only command you need to run after pushing code to GitHub
#
# What this does:
#   1. Pulls the latest code from GitHub
#   2. Installs any new Python packages (if requirements.txt changed)
#   3. Copies the service files to systemd (if they changed)
#   4. Reloads systemd to pick up any service file changes
#   5. Restarts the scraper and dashboard
#
# How to use:
#   SSH into the Pi:   ssh pi@anderson-hub
#   Navigate to repo:  cd /home/pi/anderson-monitor
#   Run this script:   ./update.sh
#
# That's it. The Pi is now running your latest code.
# ==========================================================================

echo ""
echo "========================================"
echo "  Anderson Monitor — Updating..."
echo "========================================"
echo ""

# Step 1: Pull latest code from GitHub
echo ">> Pulling latest code from GitHub..."
git pull
echo ""

# Step 2: Install/update Python packages if requirements.txt exists
if [ -f requirements.txt ]; then
    echo ">> Installing Python packages..."
    pip3 install -r requirements.txt --break-system-packages
    echo ""
fi

# Step 3: Copy service files to systemd directory
echo ">> Updating service files..."
sudo cp scraper.service /etc/systemd/system/
sudo cp dashboard.service /etc/systemd/system/

# Step 4: Tell systemd to re-read the service files
echo ">> Reloading systemd..."
sudo systemctl daemon-reload

# Step 5: Restart both services
echo ">> Restarting scraper..."
sudo systemctl restart scraper

echo ">> Restarting dashboard..."
sudo systemctl restart dashboard

echo ""
echo "========================================"
echo "  Done! Both services restarted."
echo "  Dashboard: http://anderson-hub:5000"
echo "========================================"
echo ""

# Show the status of both services so you can confirm they're running
echo ">> Service status:"
echo ""
sudo systemctl status scraper --no-pager -l | head -5
echo ""
sudo systemctl status dashboard --no-pager -l | head -5
echo ""
