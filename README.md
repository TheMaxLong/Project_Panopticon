# Anderson Facility Monitor

A Raspberry Pi 5 monitoring system for the Anderson grow facility. Tracks pH,
EC, and flow data from 3 buildings in real time, with a dark-themed web
dashboard, anomaly alerts, and cloud backup.

**Built entirely with AI assistance.** No prior coding experience required.

---

## Table of Contents

1. [What You Need](#what-you-need)
2. [Part 1: Setting Up the Raspberry Pi](#part-1-setting-up-the-raspberry-pi)
3. [Part 2: Installing the Software](#part-2-installing-the-software)
4. [Part 3: Getting the Code on the Pi](#part-3-getting-the-code-on-the-pi)
5. [Part 4: Starting Everything Up](#part-4-starting-everything-up)
6. [Part 5: Remote Access with Tailscale](#part-5-remote-access-with-tailscale)
7. [Part 6: The VS Code + GitHub Workflow](#part-6-the-vs-code--github-workflow)
8. [Part 7: Updating the HTML Selectors](#part-7-updating-the-html-selectors)
9. [Troubleshooting](#troubleshooting)

---

## What You Need

- **Raspberry Pi 5** (any RAM size works)
- **MicroSD card** (32 GB or larger)
- **Ethernet cable** (to connect the Pi to the facility network)
- **USB-C power supply** for the Pi
- **A Mac** (your development machine — at home or wherever)
- **A GitHub account** (free — github.com)

---

## Part 1: Setting Up the Raspberry Pi

### Step 1: Flash the Operating System

The Pi needs an operating system on its SD card. We're using **Raspberry Pi OS
Lite (64-bit)** — "Lite" means no desktop interface, which is perfect because
we'll control it entirely over SSH (remote terminal).

1. On your Mac, download and open **Raspberry Pi Imager** from
   [raspberrypi.com/software](https://www.raspberrypi.com/software/)
2. Click **Choose OS** → **Raspberry Pi OS (other)** → **Raspberry Pi OS Lite (64-bit)**
3. Click **Choose Storage** → select your SD card
4. **Before clicking Write**, click the **gear icon** (⚙) or press Cmd+Shift+X
   to open Advanced Options:
   - **Enable SSH** → Use password authentication
   - **Set username:** `pi`
   - **Set password:** (pick something you'll remember)
   - **Set hostname:** `anderson-hub`
   - **Configure WiFi:** Skip this — we're using ethernet
5. Click **Write** and wait for it to finish

### Step 2: Boot the Pi

1. Put the SD card into the Pi
2. Plug in the ethernet cable to the facility network
3. Plug in the USB-C power supply
4. Wait about 60 seconds for it to boot up

### Step 3: Find the Pi on the Network

From your Mac, open **Terminal** (search for "Terminal" in Spotlight) and try:

```bash
ping anderson-hub.local
```

If that works, you'll see responses with an IP address. If it doesn't work
(some networks block this), you'll need to find the Pi's IP address another way:

- Check your router's admin page for connected devices
- Or try: `arp -a | grep raspberry`
- Or ask your network admin what IP was assigned

### Step 4: SSH Into the Pi

SSH lets you control the Pi from your Mac's terminal — like a remote control.

```bash
ssh pi@anderson-hub.local
```

Or if you're using the IP address directly:

```bash
ssh pi@10.10.x.x
```

It'll ask for the password you set in Step 1. Type it (it won't show on screen
— that's normal) and press Enter.

**You're now inside the Pi.** Everything you type runs on the Pi, not your Mac.

### Step 5: Update the System

First thing after logging in — update everything to the latest versions:

```bash
sudo apt update && sudo apt upgrade -y
```

This takes a few minutes. `sudo` means "run as admin." `apt` is the package
manager (like an app store for Linux).

---

## Part 2: Installing the Software

### Step 6: Install Python Packages

Python 3 comes pre-installed on Raspberry Pi OS. We need to install the
additional libraries our code uses:

```bash
sudo apt install -y python3-pip python3-venv git
```

Now install the Python packages our scripts need:

```bash
pip3 install flask requests beautifulsoup4 python-dotenv --break-system-packages
```

Here's what each one does:
- **flask** — The web framework that runs our dashboard
- **requests** — Lets Python fetch web pages (from the Anderson controllers)
- **beautifulsoup4** — Parses HTML to find specific values on a page
- **python-dotenv** — Reads secrets from the .env file

### Step 7: Install Tailscale (Remote Access)

Tailscale creates a private network between your devices. Once it's set up,
you can access the Pi from anywhere — your Mac at home, your phone, wherever.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

Then start it and log in:

```bash
sudo tailscale up
```

It'll print a URL. Open that URL in any browser to link the Pi to your
Tailscale account. If you don't have an account yet, it's free at
[tailscale.com](https://tailscale.com).

---

## Part 3: Getting the Code on the Pi

### Step 8: Clone the GitHub Repository

This downloads all the code from GitHub onto the Pi:

```bash
cd /home/pi
git clone https://github.com/YOUR_USERNAME/anderson-monitor.git
cd anderson-monitor
```

Replace `YOUR_USERNAME` with your actual GitHub username.

### Step 9: Create the .env File

The .env file holds settings that shouldn't be in GitHub (like URLs that might
change). Create it from the template:

```bash
cp .env.example .env
```

The defaults are fine for now. You can edit it later with:

```bash
nano .env
```

(Press Ctrl+X to exit nano, Y to save.)

### Step 10: Make update.sh Executable

The update script needs permission to run:

```bash
chmod +x update.sh
```

---

## Part 4: Starting Everything Up

### Step 11: Install the Systemd Services

Systemd is what makes the scraper and dashboard start automatically when the
Pi boots up (and restart if they crash). Copy the service files into place:

```bash
sudo cp scraper.service /etc/systemd/system/
sudo cp dashboard.service /etc/systemd/system/
```

Tell systemd to read the new files:

```bash
sudo systemctl daemon-reload
```

Enable them to start on boot:

```bash
sudo systemctl enable scraper
sudo systemctl enable dashboard
```

Start them now:

```bash
sudo systemctl start scraper
sudo systemctl start dashboard
```

### Step 12: Verify Everything Is Running

Check the scraper:

```bash
sudo systemctl status scraper
```

You should see `Active: active (running)` in green. Check the dashboard:

```bash
sudo systemctl status dashboard
```

Same thing — `Active: active (running)`.

### Step 13: Open the Dashboard

From any device on the facility network, open a browser and go to:

```
http://anderson-hub.local:5000
```

Or use the Pi's IP address:

```
http://10.10.x.x:5000
```

You should see the dark-themed dashboard with 3 building cards.

> **Note:** The readings will show "—" until you update the HTML selectors
> (Part 7 below). The scraper is running, but it doesn't know exactly where
> to find the values on the controller pages yet.

---

## Part 5: Remote Access with Tailscale

### On Your Mac

1. Download Tailscale from [tailscale.com/download](https://tailscale.com/download)
2. Install and open it
3. Log in with the **same account** you used on the Pi

Once both devices are on the same Tailscale account, you can access the Pi from
anywhere in the world:

**Dashboard from anywhere:**
```
http://anderson-hub:5000
```

**SSH from anywhere:**
```bash
ssh pi@anderson-hub
```

That's it. No port forwarding, no VPN configuration, no firewall rules.
Tailscale handles all of it. You never need to be on the facility network again
to manage the Pi.

---

## Part 6: The VS Code + GitHub Workflow

This is how you make changes to the code going forward. You never edit files
directly on the Pi — you edit on your Mac and push to GitHub, then the Pi
pulls the changes.

### The Flow

1. **Open VS Code** on your Mac. Open the `anderson-monitor` folder.

2. **Make your changes.** You can:
   - Use **GitHub Copilot** (VS Code extension) for small edits — it
     autocompletes code as you type
   - Paste code from **Claude** for bigger changes or new features
   - They work as a team: Copilot for quick fixes, Claude for architecture

3. **Push to GitHub.** In VS Code's built-in terminal (View → Terminal):
   ```bash
   git add .
   git commit -m "describe what you changed"
   git push
   ```

4. **Update the Pi.** SSH in from your Mac (works from anywhere with Tailscale):
   ```bash
   ssh pi@anderson-hub
   cd /home/pi/anderson-monitor
   ./update.sh
   ```

5. **Done.** The Pi pulls your latest code and restarts both services.

---

## Part 7: Updating the HTML Selectors

The scraper uses placeholder CSS selectors (`#ph1`, `#ph2`, `#ec`, `#flow`)
that need to be updated to match the actual Anderson controller web pages.

### How to Find the Right Selectors

1. Open one of the controller pages in Chrome or Edge:
   - Building AB: `http://10.10.9.254`
   - Building EF: `http://10.10.13.50`
   - Building GH: `http://10.10.13.251`

2. Find the **pH Sensor 1** value on the page.

3. **Right-click** on that number → click **Inspect**.

4. The browser's developer tools will open and highlight the HTML element.
   It might look something like:
   ```html
   <span class="sensor-value" id="ph1">6.12</span>
   ```
   or:
   ```html
   <td data-field="ph_sensor_1">6.12</td>
   ```

5. Note the **id**, **class**, or **data-** attribute that uniquely identifies
   that element.

6. Open `scraper.py` in VS Code and find the `SELECTORS` dictionary near the
   top. Update the selectors to match what you found:
   ```python
   SELECTORS = {
       "ph1":  "#ph1",             # Change this
       "ph2":  "#ph2",             # Change this
       "ec":   "#ec",              # Change this
       "flow": "#flow",            # Change this
   }
   ```

   **Selector syntax:**
   - If the element has `id="something"` → use `#something`
   - If the element has `class="something"` → use `.something`
   - If it's more complex → ask Claude, paste the HTML you see

7. Push your changes and run `./update.sh` on the Pi.

---

## Troubleshooting

### "Can't reach the dashboard"
- Is the Pi running? SSH in and check: `sudo systemctl status dashboard`
- Are you on the same network (or connected via Tailscale)?
- Try the IP address directly instead of the hostname

### "All buildings show OFFLINE"
- The scraper might not be running: `sudo systemctl status scraper`
- The HTML selectors might not match the controller pages (see Part 7)
- The controllers themselves might be unreachable — try opening their
  IPs in a browser from the Pi: `curl http://10.10.9.254`

### "Readings show — (dashes)"
- This means the scraper is running but can't parse the values
- The HTML selectors need to be updated (Part 7)
- Check `errors.log` in the project folder for details

### "Replit mirror warnings in the log"
- These are harmless. The Pi saves data locally no matter what.
- Replit being slow or down does NOT affect the Pi's data collection.

### How to See the Scraper's Live Output
```bash
sudo journalctl -u scraper -f
```
Press Ctrl+C to stop watching.

### How to See the Dashboard's Live Output
```bash
sudo journalctl -u dashboard -f
```

### How to Restart Everything
```bash
cd /home/pi/anderson-monitor
./update.sh
```

### How to Wipe the Database and Start Fresh
```bash
cd /home/pi/anderson-monitor
sudo systemctl stop scraper dashboard
rm anderson.db
sudo systemctl start scraper dashboard
```
The scraper will recreate the database automatically on next start.

---

## File Overview

| File | What It Does |
|------|-------------|
| `scraper.py` | Polls all 3 building controllers, saves to SQLite, mirrors to Replit |
| `dashboard.py` | Flask web server serving the dashboard on port 5000 |
| `templates/index.html` | Dashboard UI — dark theme, live readings, charts |
| `scraper.service` | Makes the scraper auto-start on boot |
| `dashboard.service` | Makes the dashboard auto-start on boot |
| `update.sh` | One-command update: git pull + restart services |
| `.env` | Local secrets (not in GitHub) |
| `.env.example` | Template for .env |
| `requirements.txt` | Python package list |
| `CLAUDE_CONTEXT.md` | Context file for AI assistants |
| `README.md` | This file |

---

*Built with Claude and GitHub Copilot. April 2026.*
