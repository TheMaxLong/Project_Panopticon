# CLAUDE_CONTEXT.md — Anderson Facility Monitoring System

> **For Claude / AI assistants:** Read this file first. It tells you everything
> you need to know about this project, the person building it, and how the
> system works.


## Message from Claude Before you: I_Miss_The_Old_Claudye
PROJECT: Project_Panopticon
COMPANION REPO: github.com/TheMaxLong/Fluxuum-Logger (TypeScript/Node.js cloud dashboard on Replit — Panopticon feeds data into this as backup)
OWNER SKILL LEVEL: Not a developer. All code written by Claude + GitHub Copilot.
EDIT WORKFLOW: Edit on Mac in VS Code → git push to GitHub → SSH into Pi → ./update.sh

---

## Who Is Building This

The owner is **not a developer**. All code in this repo was written by AI
assistants — Claude and GitHub Copilot. The owner operates a cannabis grow
facility on the overnight shift (midnight–11:30 AM) and built this monitoring
system to track pH, EC, and flow data across three buildings in real time.

**What this means for you:**
- All code must be heavily commented in plain English
- Variable names must be obvious and descriptive
- No clever one-liners or abstract patterns
- When there are options, choose the simpler one
- Explain what you're doing and why before giving code
- Never ask the owner to read or write code manually — render artifacts directly

---

## The System

A **Raspberry Pi 5** (hostname: `anderson-hub`) sits on-site at the facility,
connected to the same local network as the building controllers. It runs two
services:

1. **Scraper** (`scraper.py`) — Polls 3 building controllers every 3 seconds,
   parses pH, EC, and flow data, stores it in SQLite, and mirrors it to Replit.

2. **Dashboard** (`dashboard.py`) — A Flask web server on port 5000 that shows
   live readings, anomaly alerts, and 2-hour trend charts.

**Replit** (`fluxuum.replit.app`) is a cloud backup — not the primary system.
The Pi's local SQLite database is the source of truth.

---

## The 3 Buildings

| Building | IP Address      | Label                    | Notes          |
|----------|-----------------|--------------------------|----------------|
| AB       | 10.10.9.254     | Building AB (Primary)    | Always first   |
| EF       | 10.10.13.50     | Building EF              |                |
| GH       | 10.10.13.251    | Building GH              |                |

Each building has an **H.E. Anderson** irrigation controller with a plain HTTP
web interface. The scraper fetches these pages and parses out sensor values
using BeautifulSoup.

---

## Tech Stack

| Component     | Technology                | Why                                          |
|---------------|---------------------------|----------------------------------------------|
| Language      | Python 3                  | Simple, readable, no compilation step        |
| Web framework | Flask                     | Minimal — one file, no boilerplate           |
| Database      | SQLite                    | Zero setup — just a file, no server          |
| Scraping      | requests + BeautifulSoup  | Standard Python HTTP + HTML parsing          |
| Charts        | Chart.js (CDN)            | No npm/node — just a script tag              |
| Remote access | Tailscale                 | Zero-config VPN — SSH from anywhere          |
| Source control| GitHub                    | Source of truth for all code                 |
| Cloud backup  | Replit (fluxuum.replit.app)| Testing sandbox + mirror of Pi data          |
| Dev machine   | Mac + VS Code + Copilot   | Code editing and GitHub pushes happen here   |

**Hard rules:** No Docker. No Django/FastAPI. No npm/node. No external databases.
Keep it simple.

---

## Edit Workflow

1. Open VS Code on the Mac. Open the repo folder.
2. Make changes (with Copilot or by pasting Claude's code).
3. In VS Code terminal: `git add . && git commit -m "description" && git push`
4. SSH into Pi: `ssh pi@anderson-hub`
5. Run: `cd /home/pi/anderson-monitor && ./update.sh`
6. Done. Pi is updated, services restart automatically.

---

## Anomaly Thresholds

| Metric | Warning Range           | Critical         |
|--------|-------------------------|-------------------|
| pH     | Below 5.6 or above 6.3  | —                 |
| EC     | Below 2.5 or above 3.5 mS/cm | —            |
| Flow   | —                       | 0 GPM             |

---

## File Structure

```
anderson-monitor/
├── scraper.py          # Polls controllers, writes to SQLite, mirrors to Replit
├── dashboard.py        # Flask web server — serves the dashboard
├── templates/
│   └── index.html      # Dashboard UI — dark theme, charts, live readings
├── scraper.service     # systemd service file — auto-starts the scraper
├── dashboard.service   # systemd service file — auto-starts the dashboard
├── update.sh           # One-command update script: git pull + restart services
├── anderson.db         # SQLite database (auto-created, not in git)
├── errors.log          # Scraper error log (auto-created, not in git)
├── .env                # Secrets (not in git — copy from .env.example)
├── .env.example        # Template for .env
├── requirements.txt    # Python dependencies
├── CLAUDE_CONTEXT.md   # This file — project context for AI assistants
└── README.md           # Full setup walkthrough from zero to running
```

---

## Controller Communication

**The Anderson controllers communicate via WebSocket at `ws://10.10.x.x/rundata/ws`
— NOT plain HTTP.** The existing `poller/poller.js` in Fluxuum-Logger already
handles this correctly using the `ws` npm package. The Python scraper in this
project uses `websocket-client` as its primary method, with HTTP/BeautifulSoup
as a fallback in case the controllers also serve a plain status page.

The exact WebSocket message format (JSON key names) needs to be verified on-site.
The scraper has a flexible parser that tries multiple common key patterns, plus
instructions in `scraper.py` for how to inspect the actual messages using
Chrome DevTools → Network → WS tab.

---

## Known Limitations

1. **WebSocket message keys are best-guess.** The scraper tries multiple
   possible key names (ph1, pH1, ph_sensor_1, etc.) but may need updating
   once you see the actual JSON the controller sends. Instructions are in
   scraper.py — or just paste a raw message to Claude.

2. **No authentication.** The dashboard has no login. Anyone on the Tailscale
   network (or local network) can view it. This is fine for now.

3. **SQLite concurrency.** SQLite handles one writer at a time. With a single
   scraper writing every 3 seconds, this is never a problem. If you add a
   second scraper, you'll need to think about locking.

4. **No data pruning.** The database grows forever. At ~1 KB per reading × 3
   buildings × 20 readings/min, that's about 85 MB per month. The Pi's SD card
   can handle years of this, but eventually you may want to add a cleanup job.

---

## Related Systems

The owner also maintains:
- A **facility tracker** React artifact in Claude (v324 design) for daily
  runoff reports, day counts, and environmental data
- A **browser extension** that scrapes the Anderson controller UI with pH
  flagging and CSV export
- A **Replit Node.js project** with Chart.js dashboard and SQLite backend

These are separate from this Pi monitoring system but may eventually integrate.

---

*Last updated: April 2026*
