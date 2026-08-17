import subprocess
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

SMART_ATTRIBUTES = {
    5: "reallocated_sectors",
    12: "power_cycle_count",
    184: "end_to_end_error",
    187: "reported_uncorrectable",
    188: "command_timeout",
    195: "hardware_ecc_recovered",
    197: "current_pending_sector",
    198: "offline_uncorrectable",
    199: "udma_crc_error_count",
}

def _format_bytes(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

class SmartCollector:
    def __init__(self, excluded_drives: List[str] = None):
        self.excluded_drives = excluded_drives or []

    def _detect_drive_type(self, protocol: str, transport: str, sata_version: str,
                           scan_type: str, rotation_rate: Optional[int]) -> str:
        """Detect drive type from smartctl -i fields.

        Returns a human-readable type like 'SATA SSD', 'SAS HDD', 'NVMe SSD', etc.
        Detection order: transport > sata_version > protocol > scan_type.

        On Linux, libata can cause SATA drives to report unreliable scan_type and
        protocol values, so we check transport and sata_version first as they are
        more direct indicators from the drive itself.
        """
        if scan_type == "nvme":
            return "NVMe SSD"

        bus = None

        # Check transport field first (e.g., "SAS (SPL-4)" for SAS drives)
        if transport:
            t = transport.lower()
            if "sas" in t or "scsi" in t:
                bus = "SAS"
            elif "sata" in t:
                bus = "SATA"
            else:
                bus = None

        # Fall back to sata_version presence (e.g., "SATA 3.3, 6.0 Gb/s")
        if not bus and sata_version:
            bus = "SATA"

        # Fall back to protocol field from smartctl -i
        if not bus and protocol:
            p = protocol.lower()
            if "sas" in p or "scsi" in p:
                bus = "SAS"
            elif "sata" in p or "ata" in p:
                bus = "SATA"

        # Final fallback to scan_type from smartctl --scan
        if not bus:
            bus = "SAS" if scan_type == "scsi" else "SATA"

        if rotation_rate is not None and rotation_rate > 0:
            return f"{bus} HDD"
        return f"{bus} SSD"

    def get_all_drives(self) -> List[Dict]:
        """Get list of all drives in the system."""
        drives = []
        try:
            result = subprocess.run(
                ["smartctl", "--scan", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for device in data.get("devices", []):
                    drive_path = device["name"]
                    scan_type = device.get("type", "Unknown")
                    info = self._get_drive_info(drive_path)
                    if info and info["serial"] and info["serial"] not in self.excluded_drives:
                        drive_type = self._detect_drive_type(
                            info.get("protocol"), info.get("transport"),
                            info.get("sata_version"), scan_type,
                            info.get("rotation_rate")
                        )
                        drives.append({
                            "path": drive_path,
                            "serial": info["serial"],
                            "model": info["model"],
                            "size": info["size"],
                            "type": drive_type,
                            "bus_type": scan_type,
                        })
        except Exception as e:
            print(f"Error scanning drives: {e}")
        return drives

    def _get_drive_info(self, drive_path: str) -> Optional[Dict]:
        """Get drive serial, model, size, and type from smartctl -i."""
        try:
            result = subprocess.run(
                ["smartctl", "-i", "--json", drive_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode <= 1 and result.stdout:
                data = json.loads(result.stdout)
                serial = data.get("serial_number")
                model = data.get("model_name") or data.get("scsi_model_name", "Unknown")
                size_bytes = data.get("user_capacity", {}).get("bytes")
                size = _format_bytes(size_bytes) if size_bytes else "Unknown"
                rotation_rate = data.get("rotation_rate")
                protocol = data.get("protocol")
                transport = data.get("transport")
                sata_version = data.get("sata_version")
                return {
                    "serial": serial,
                    "model": model,
                    "size": size,
                    "rotation_rate": rotation_rate,
                    "protocol": protocol,
                    "transport": transport,
                    "sata_version": sata_version,
                }
        except Exception:
            pass
        return None

    def collect_smart_data(self, drive_path: str) -> Optional[Dict]:
        """Collect SMART data from a drive."""
        try:
            result = subprocess.run(
                ["smartctl", "-a", "--json", drive_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            # smartctl returns 0 for OK, 1 for errors/issues, 2 for critical errors.
            # Exit code 1 often means data was collected but some features are unsupported
            # (common with SAS drives or USB-attached drives). Only bail on code 2+.
            if result.returncode <= 1 and result.stdout:
                data = json.loads(result.stdout)
                return self._parse_smart_data(data, drive_path)
        except Exception as e:
            print(f"Error collecting SMART data from {drive_path}: {e}")
        return None

    def _parse_smart_data(self, data: Dict, drive_path: str) -> Dict:
        """Parse SMART data from smartctl -a --json output.

        Handles both ATA (ata_smart_attributes) and SAS/SCSI drives.
        For SAS, extracts health from top-level fields and SCSI log pages.
        """
        protocol = (data.get("protocol") or "").lower()
        transport = (data.get("transport") or "").lower()
        sata_version = data.get("sata_version")
        # sata_version presence is the most reliable SATA indicator;
        # transport/protocol can be wrong on Linux with libata.
        is_sas = not sata_version and ("sas" in transport or "scsi" in transport or
                                       "sas" in protocol or "scsi" in protocol)

        attributes = {
            "timestamp": datetime.utcnow().isoformat(),
            "drive_path": drive_path,
            "serial": data.get("serial_number"),
            "model": data.get("model_name") or data.get("scsi_model_name"),
            "drive_type": "SAS" if is_sas else "SATA",
            "power_on_hours": None,
            "temperature": None,
            "load_cycle_count": None,
            "health_status": None,
            "reallocated_sectors": None,
            "power_cycle_count": None,
            "end_to_end_error": None,
            "reported_uncorrectable": None,
            "command_timeout": None,
            "hardware_ecc_recovered": None,
            "current_pending_sector": None,
            "offline_uncorrectable": None,
            "udma_crc_error_count": None,
        }

        # Health status from smart_status (both ATA and SAS)
        smart_status = data.get("smart_status", {})
        if "passed" in smart_status:
            attributes["health_status"] = smart_status["passed"]

        # Power on hours from top-level field (both ATA and SAS)
        power_on_time = data.get("power_on_time", {})
        if "hours" in power_on_time:
            attributes["power_on_hours"] = power_on_time["hours"]

        if is_sas:
            self._parse_sas_data(data, attributes)
        else:
            self._parse_ata_data(data, attributes)

        return attributes

    def _parse_ata_data(self, data: Dict, attributes: Dict):
        """Parse ATA-specific SMART attributes."""
        # Temperature from top-level field
        temp_data = data.get("temperature", {})
        if "current" in temp_data:
            attributes["temperature"] = temp_data["current"]

        # ATA SMART attributes table
        for attr in data.get("ata_smart_attributes", {}).get("table", []):
            attr_id = attr["id"]
            attr_value = attr["value"]
            attr_name = attr["name"]

            if attr_id in SMART_ATTRIBUTES:
                attributes[SMART_ATTRIBUTES[attr_id]] = attr_value
            elif attr_name == "Power_On_Hours":
                attributes["power_on_hours"] = attr_value
            elif attr_name == "Temperature_Celsius":
                attributes["temperature"] = attr_value
            elif attr_name == "Load_Cycle_Count":
                attributes["load_cycle_count"] = attr_value

    def _parse_sas_data(self, data: Dict, attributes: Dict):
        """Parse SAS/SCSI SMART data from smartctl -a --json output."""
        # Temperature (SAS uses 'temperature' key, not 'temperature.current')
        temp_data = data.get("temperature", {})
        if "temperature" in temp_data:
            attributes["temperature"] = temp_data["temperature"]

        # Load cycle count from SCSI start/stop cycle counter
        start_stop = data.get("scsi_start_stop_cycle_counter", {})
        if "accumulated_number_of_cycle_uploads" in start_stop:
            attributes["load_cycle_count"] = start_stop["accumulated_number_of_cycle_uploads"]
        elif "number_of_status_changes" in start_stop:
            attributes["load_cycle_count"] = start_stop["number_of_status_changes"]

        # Reallocated sectors from SCSI grown defect list
        defect_list = data.get("scsi_grown_defect_list", {})
        if "grown_defect_list_count" in defect_list:
            attributes["reallocated_sectors"] = defect_list["grown_defect_list_count"]

        # Error counters from SCSI error counter log
        error_log = data.get("scsi_error_counter_log", {})
        if "read" in error_log:
            read_errs = error_log["read"]
            if "correction_of_errors" in read_errs:
                attributes["reported_uncorrectable"] = read_errs["correction_of_errors"]
        if "write" in error_log:
            write_errs = error_log["write"]
            if "correction_of_errors" in write_errs:
                if attributes["reported_uncorrectable"] is None:
                    attributes["reported_uncorrectable"] = write_errs["correction_of_errors"]
                else:
                    attributes["reported_uncorrectable"] += write_errs["correction_of_errors"]

    def collect_all(self) -> List[Dict]:
        """Collect SMART data from all non-excluded drives."""
        drives = self.get_all_drives()
        all_data = []

        for drive in drives:
            smart_data = self.collect_smart_data(drive["path"])
            if smart_data:
                smart_data["drive_info"] = drive
                all_data.append(smart_data)

        return all_data
