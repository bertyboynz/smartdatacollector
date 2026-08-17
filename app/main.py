from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager
import json

from .database import db
from .smart_collector import SmartCollector

scheduler = AsyncIOScheduler()

async def collect_smart_data():
    """Background task to collect SMART data."""
    config = await db.get_all_config()
    excluded = config.get("excluded_drives", "[]")
    excluded_list = json.loads(excluded) if excluded else []

    collector = SmartCollector(excluded_drives=excluded_list)
    all_data = collector.collect_all()

    for data in all_data:
        serial = data.get("serial")
        drive_info = data.get("drive_info", {})

        if serial:
            await db.upsert_drive({
                "serial": serial,
                "path": drive_info.get("path"),
                "model": drive_info.get("model"),
                "size": drive_info.get("size"),
            })
            await db.store_reading(serial, data)

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
    return {"status": "ok", "message": "Collection completed"}

@app.post("/api/drives/{serial}/exclude")
async def exclude_drive(serial: str, exclude: bool = True):
    await db.set_excluded(serial, exclude)
    return {"status": "ok"}