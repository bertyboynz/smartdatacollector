import subprocess
import json
import os
from typing import Dict, List, Optional
from datetime import datetime

SMART_ATTRIBUTES = {
    5: "reallocated_sectors",
    187: "reported_uncorrectable",
    188: "command_timeout",
    197: "current_pending_sector",
    198: "offline_uncorrectable",
    199: "udma_crc_error_count",
}

class SmartCollector:
    def __init__(self, excluded_drives: List[str] = None):
        self.excluded_drives = excluded_drives or []

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
                    serial = self._get_serial(drive_path)
                    if serial and serial not in self.excluded_drives:
                        drives.append({
                            "path": drive_path,
                            "serial": serial,
                            "model": device.get("model_name", "Unknown"),
                            "size": device.get("size", {}).get("string", "Unknown"),
                            "type": device.get("type", "Unknown"),
                        })
        except Exception as e:
            print(f"Error scanning drives: {e}")
        return drives

    def _get_serial(self, drive_path: str) -> Optional[str]:
        """Get drive serial number."""
        try:
            result = subprocess.run(
                ["smartctl", "-i", "--json", drive_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("serial_number")
        except Exception:
            pass
        return None

    def collect_smart_data(self, drive_path: str) -> Optional[Dict]:
        """Collect SMART data from a drive."""
        try:
            result = subprocess.run(
                ["smartctl", "-A", "-i", "--json", drive_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return self._parse_smart_data(data, drive_path)
        except Exception as e:
            print(f"Error collecting SMART data from {drive_path}: {e}")
        return None

    def _parse_smart_data(self, data: Dict, drive_path: str) -> Dict:
        """Parse SMART data and extract relevant attributes."""
        attributes = {
            "timestamp": datetime.utcnow().isoformat(),
            "drive_path": drive_path,
            "serial": data.get("serial_number"),
            "model": data.get("model_name"),
            "power_on_hours": None,
            "temperature": None,
            "load_cycle_count": None,
        }

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

        return attributes

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