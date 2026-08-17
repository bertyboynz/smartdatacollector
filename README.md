# SMART Data Collector

A Docker-based application for monitoring SMART data from Unraid drives over time. Collects, stores, and visualizes drive health metrics with a web-based dashboard.

## Features

- **Automatic Drive Discovery**: Scans system for all drives and collects SMART data
- **Historical Tracking**: Stores SMART readings over time to track trends
- **Web Dashboard**: Visualize drive health with interactive charts
- **Configurable Collection**: Set collection interval via the web UI
- **Drive Exclusion**: Exclude specific drives from monitoring
- **Change Detection**: View deltas between readings to spot issues early

## Key SMART Attributes Monitored

- Reallocated Sectors Count
- Current Pending Sector Count
- Offline Uncorrectable
- Reported Uncorrectable Errors
- Command Timeout
- UDMA CRC Error Count
- Temperature
- Power-On Hours
- Load Cycle Count

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Access to drives (requires privileged mode or device access)

### Installation

1. Clone or download this repository

2. Build and start the container:
   ```bash
   docker-compose up -d
   ```

3. Access the web dashboard at:
   ```
   http://localhost:8080
   ```

### First Run

1. Open the dashboard in your browser
2. Click "Collect Now" to perform an initial scan of your drives
3. The dashboard will populate with your drive information
4. Configure collection interval in the Settings tab

## Configuration

### Web UI Settings

- **Collection Interval**: How often to collect SMART data (in minutes)
- **Drive Exclusion**: Exclude specific drives from monitoring

### Environment Variables

- `TZ`: Timezone for the container (default: UTC)

## Docker Compose Options

The `docker-compose.yml` is configured with:

- **Privileged Mode**: Required to access `/dev` for drive information
- **Volume Mounts**:
  - `/dev:ro`: Read-only access to device files
  - `/dev/disk/by-id:ro`: Read-only access to disk IDs
  - `./data:/app/data`: Persistent storage for SQLite database
- **Port**: 8080 for web interface

## API Endpoints

- `GET /api/drives` - List all drives
- `GET /api/drives/{serial}/history` - Get SMART history for a drive
- `POST /api/collect` - Trigger manual collection
- `GET /api/config` - Get configuration
- `POST /api/config` - Update configuration
- `POST /api/drives/{serial}/exclude` - Toggle drive exclusion

## Data Storage

Data is stored in an SQLite database at `./data/smartdata.db`. This persists across container restarts.

## Troubleshooting

### No Drives Found

1. Ensure the container is running with `--privileged` or appropriate device access
2. Check that smartmontools is installed: `docker exec -it smartdatacollector smartctl --version`
3. Click "Collect Now" to trigger a manual scan

### Permission Issues

The container needs access to `/dev` to read drive information. The `docker-compose.yml` is configured with:
- `privileged: true`
- Read-only mounts for `/dev` and `/dev/disk/by-id`

## Development

### Build Pipeline

Pushing to `main` triggers an automated Docker build. No manual build step is needed — just push and the new image is built and available from your Docker registry.

### Project Structure

```
smartdatacollector/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py              # FastAPI application
│   ├── database.py          # SQLite database operations
│   ├── smart_collector.py   # SMART data collection
│   └── static/
│       ├── index.html       # Dashboard HTML
│       ├── css/style.css    # Styles
│       └── js/app.js        # Frontend logic
└── data/                    # Persistent data directory
```

### Local Development

For development without Docker:

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install smartmontools:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install smartmontools
   ```

3. Run the application:
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

## License

MIT License