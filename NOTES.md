# SMART Data Collector - Developer Notes

## Quick Reference

- **Dashboard**: `http://<unraid-ip>:8080`
- **Repo**: `github.com/bertyboynz/smartdatacollector`
- **Docker image**: `ghcr.io/bertyboynz/smartdatacollector:latest`
- **Unraid template XML**: Must set `TZ` env var — not hardcoded in docker-compose.yml

## How It Works

1. On page load, auto-scans for drives via `smartctl --scan`
2. For each drive, runs `smartctl -i` to get identity info (model, serial, size, protocol)
3. Drive type detection uses `transport`, `sata_version`, `protocol` fields from `smartctl -i`
4. Click **Run SMART** to collect health data — runs `smartctl -a` on all non-excluded drives
5. Drives collected 2 at a time in parallel (asyncio.Semaphore)
6. Results stored to SQLite as each drive completes
7. Scheduled collection runs every N minutes (default 360)

## Drive Type Detection

Detection order (most reliable first):
1. `transport` field — e.g., "SAS (SPL-4)" = SAS, "SATA" = SATA
2. `sata_version` presence — if present, it's SATA
3. `protocol` field from smartctl -i
4. `scan_type` from smartctl --scan (fallback, unreliable on Linux due to libata)

**Known issue**: On Linux, libata presents SATA drives via the SCSI subsystem, causing `smartctl --scan` to report them as `"scsi"`. The `transport` and `sata_version` fields are more reliable.

## Tracked SMART Attributes

### ATA Attributes
| ID | Name | Key | Notes |
|----|------|-----|-------|
| 4 | Start/Stop Count | `start_stop_count` | Head load/unload cycles |
| 5 | Reallocated Sectors | `reallocated_sectors` | Bad sector reallocation |
| 12 | Power Cycle Count | `power_cycle_count` | Spin up/down count |
| 184 | End-to-End Error | `end_to_end_error` | Data integrity |
| 187 | Reported Uncorrectable | `reported_uncorrectable` | |
| 188 | Command Timeout | `command_timeout` | |
| 195 | Hardware ECC Recovered | `hardware_ecc_recovered` | Error correction activity |
| 197 | Current Pending Sector | `current_pending_sector` | |
| 198 | Offline Uncorrectable | `offline_uncorrectable` | |
| 199 | UDMA CRC Error Count | `udma_crc_error_count` | SATA bus CRC errors |

### Common Fields (both ATA and SAS)
| Field | Key | Notes |
|-------|-----|-------|
| Temperature | `temperature` | From `temperature.current` (ATA) or `temperature.temperature` (SAS) |
| Power On Hours | `power_on_hours` | From `power_on_time.hours` top-level field |
| Health Status | `health_status` | From `smart_status.passed` |
| Load Cycle Count | `load_cycle_count` | From ATA attribute or `scsi_start_stop_cycle_counter` |

### SAS-Specific Fields
| Source | Key |
|--------|-----|
| `scsi_grown_defect_list.grown_defect_list_count` | `reallocated_sectors` |
| `scsi_error_counter_log.read.correction_of_errors` | `reported_uncorrectable` |

## Frontend Features

- **Dashboard**: Drive cards sorted by size (included first, excluded last)
- **Status badges**: Included (green), Excluded (yellow), Pending (grey), Collecting (blue pulse)
- **Drive detail modal**: Shows all SMART stats with delta (change from previous reading)
  - Red `+N` = increase (usually bad for error counters)
  - Green `-N` = decrease
  - Prev/Next arrows to browse drives
- **Drives tab**: Table view with include/exclude toggle
- **Settings tab**: Collection interval, drive history chart
- **Refresh button**: Re-scans for drives and reloads dashboard

## Security Measures

1. **XSS prevention**: `escapeHtml()` on all device data before innerHTML
2. **Config whitelist**: Only `collection_interval` and `excluded_drives` accepted
3. **Rate limiting**: 30s cooldown between Run SMART clicks
4. **CORS**: Explicit middleware (GET/POST only)
5. **Input validation**: Serial must match `[A-Za-z0-9_-]+`
6. **Security headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy
7. **SRI hash**: Chart.js pinned to v4.5.1 with integrity check
8. **Collection guard**: Prevents concurrent collection runs

## Known Limitations

- No authentication (anyone on network can access)
- Container runs privileged (required for /dev access on Unraid)
- No HTTPS (plain HTTP on port 8080)
- Old readings in database won't have newly added attributes until re-collected
- `smartctl --scan` can be slow with many drives

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard |
| GET | `/api/drives?scan=true` | List drives (optionally scan for new ones) |
| GET | `/api/drives/{serial}/history?limit=50` | SMART history for a drive |
| GET | `/api/collecting` | Currently collecting drive paths |
| GET | `/api/config` | Get all config |
| POST | `/api/config` | Update config (whitelist: collection_interval, excluded_drives) |
| POST | `/api/collect` | Start SMART collection (30s cooldown) |
| POST | `/api/populate` | Scan and add drives (no longer used by UI) |
| POST | `/api/drives/{serial}/exclude?exclude=true` | Toggle drive exclusion |

## File Structure

```
app/
├── main.py              # FastAPI app, routes, scheduler
├── smart_collector.py   # Drive discovery, SMART collection (async)
├── database.py          # SQLite via aiosqlite
└── static/
    ├── index.html       # Dashboard HTML
    ├── icon.png         # Favicon
    ├── css/style.css    # Styles (including animation for collecting state)
    └── js/app.js        # Frontend logic (escapeHtml, polling, charts)
```

## Unraid Notes

- Container needs `privileged: true` for `/dev` access
- Must set `TZ` env var in Unraid template (not hardcoded in docker-compose)
- Icon URL in Unraid template: `https://raw.githubusercontent.com/bertyboynz/smartdatacollector/main/icon.png`
- Data persists at `/mnt/user/appdata/smartdatacollector` → `/app/data`
- Port 8883 mapped to container 8080
