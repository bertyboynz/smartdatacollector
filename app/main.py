from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
import asyncio
import json

from .database import db
from .smart_collector import SmartCollector

scheduler = AsyncIOScheduler()
collector: Optional[SmartCollector] = None
collecting_task: Optional[asyncio.Task] = None

async def run_collection():
    """Run SMART collection in background, storing results as each drive completes."""
    global collector
    config = await db.get_all_config()
    excluded = config.get("excluded_drives", "[]")
    excluded_list = json.loads(excluded) if excluded else []

    collector = SmartCollector(excluded_drives=excluded_list)
    drives = await collector.get_all_drives()
    semaphore = asyncio.Semaphore(2)

    async def collect_one(drive):
        async with semaphore:
            smart_data = await collector.collect_smart_data(drive["path"])
            if smart_data:
                smart_data["drive_info"] = drive
                return smart_data
        return None

    tasks = [asyncio.create_task(collect_one(d)) for d in drives]
    for task in asyncio.as_completed(tasks):
        try:
            result = await task
        except Exception:
            continue
        if result:
            serial = result.get("serial")
            drive_info = result.get("drive_info", {})
            if serial:
                await db.upsert_drive({
                    "serial": serial,
                    "path": drive_info.get("path"),
                    "model": drive_info.get("model"),
                    "size": drive_info.get("size"),
                    "drive_type": drive_info.get("type"),
                })
                await db.store_reading(serial, result)

    collector = None

async def collect_smart_data():
    """Background task to collect SMART data."""
    global collecting_task
    if collecting_task and not collecting_task.done():
        return
    collecting_task = asyncio.create_task(run_collection())

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()

    interval = await db.get_config("collection_interval")
    interval_minutes = int(interval) if interval else 360

    scheduler.add_job(
        collect_smart_data,
        'interval',
        minutes=interval_minutes,
        id='smart_collector',
        replace_existing=True
    )
    scheduler.start()

    yield

    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("app/static/index.html") as f:
        return f.read()

@app.get("/api/drives")
async def get_drives():
    drives = await db.get_all_drives()
    return drives

@app.get("/api/drives/{serial}/history")
async def get_drive_history(serial: str, limit: int = 100):
    readings = await db.get_readings(serial, limit)
    return readings

@app.post("/api/config")
async def update_config(config: Dict[str, str]):
    for key, value in config.items():
        await db.set_config(key, str(value))

    if "collection_interval" in config:
        scheduler.reschedule_job(
            'smart_collector',
            trigger='interval',
            minutes=int(config["collection_interval"])
        )

    return {"status": "ok"}

@app.get("/api/config")
async def get_config():
    config = await db.get_all_config()
    return config

@app.post("/api/collect")
async def manual_collect():
    await collect_smart_data()
    return {"status": "ok", "message": "Collection started"}

@app.get("/api/collecting")
async def get_collecting():
    """Return which drive paths are currently being scanned."""
    if collector:
        return {"collecting": list(collector.collecting)}
    return {"collecting": []}

@app.post("/api/populate")
async def populate_drives():
    """Scan for drives and add them to the database without running full SMART collection."""
    config = await db.get_all_config()
    excluded = config.get("excluded_drives", "[]")
    excluded_list = json.loads(excluded) if excluded else []

    c = SmartCollector(excluded_drives=excluded_list)
    drives = await c.get_all_drives()

    for drive in drives:
        await db.upsert_drive({
            "serial": drive["serial"],
            "path": drive.get("path"),
            "model": drive.get("model"),
            "size": drive.get("size"),
            "drive_type": drive.get("type"),
        })

    return {"status": "ok", "message": f"Found {len(drives)} drives", "count": len(drives)}

@app.post("/api/drives/{serial}/exclude")
async def exclude_drive(serial: str, exclude: bool = True):
    await db.set_excluded(serial, exclude)
    return {"status": "ok"}