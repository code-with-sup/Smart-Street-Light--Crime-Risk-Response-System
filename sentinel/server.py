"""FastAPI app: REST API, MJPEG camera stream and a WebSocket for live state."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import alerts, hardware, reports
from .config import EVIDENCE_DIR, ROOT, WEB_DIR
from .detection import MODELS
from .service import Sentinel, SettingsError
from .storage import INCIDENT_STATUSES

log = logging.getLogger("sentinel.server")
sentinel = Sentinel()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sentinel.start()
    yield
    sentinel.shutdown()


app = FastAPI(title="Sentinel Street", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_error(_request, error: RequestValidationError) -> JSONResponse:
    """FastAPI echoes the bad input back, which itself crashes on NaN/Infinity; send only where and why."""
    detail = [{"loc": list(e.get("loc", ())), "msg": e.get("msg", "Invalid value"), "type": e.get("type", "")}
              for e in error.errors()]
    return JSONResponse(status_code=422, content={"detail": detail})


@app.middleware("http")
async def revalidate_static(request, call_next):
    """Make browsers re-check UI files so an update is never hidden behind a stale cache."""
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def _bad_request(error: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(error))


# ------------------------------------------------------------------ pages
@app.get("/", include_in_schema=False)
def landing() -> FileResponse:
    return FileResponse(WEB_DIR / "landing.html", headers={"Cache-Control": "no-store"})


@app.get("/app", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/evidence/{name}", include_in_schema=False)
def evidence(name: str) -> FileResponse:
    path = EVIDENCE_DIR / Path(name).name  # basename only: no path traversal
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path)


# ------------------------------------------------------------- live data
@app.get("/api/stream")
async def stream() -> StreamingResponse:
    async def frames():
        last = None
        while True:
            data = await run_in_threadpool(sentinel.jpeg)
            if data is None:
                await asyncio.sleep(0.25)
                if not sentinel.camera.running:
                    break
                continue
            if data is not last:
                last = data
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n"
            await asyncio.sleep(1 / 25)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store"})


@app.get("/api/snapshot")
def snapshot() -> Response:
    data = sentinel.jpeg()
    if data is None:
        raise HTTPException(404, "Camera is off")
    return Response(data, media_type="image/jpeg")


@app.websocket("/ws")
async def live(socket: WebSocket) -> None:
    await socket.accept()
    try:
        while True:
            await socket.send_json(await run_in_threadpool(sentinel.state))
            await asyncio.sleep(0.4)
    except (WebSocketDisconnect, RuntimeError):
        pass


@app.get("/api/state")
def state() -> dict:
    return sentinel.state()


# ----------------------------------------------------------------- camera
class CameraStart(BaseModel):
    index: int | None = Field(default=None, ge=0, le=9)


@app.post("/api/camera/start")
def camera_start(body: CameraStart) -> dict:
    ok, message = sentinel.camera.start(body.index)
    if not ok:
        raise HTTPException(409, message)
    sentinel.camera_changed()
    sentinel.update_settings({"camera_index": sentinel.camera.index})
    sentinel.note("system", message)
    return {"message": message}


@app.post("/api/camera/stop")
def camera_stop() -> dict:
    sentinel.camera.stop()
    sentinel.note("system", "Camera stopped")
    return {"message": "Camera stopped"}


@app.post("/api/camera/switch")
def camera_switch() -> dict:
    ok, message = sentinel.camera.switch()
    if ok:
        sentinel.camera_changed()
        sentinel.settings = sentinel.store.save_settings({"camera_index": sentinel.camera.index})
    return {"ok": ok, "message": message}


class Mirror(BaseModel):
    mirror: bool


@app.post("/api/camera/mirror")
def camera_mirror(body: Mirror) -> dict:
    sentinel.update_settings({"mirror": body.mirror})
    return {"mirror": body.mirror}


# -------------------------------------------------------------- incidents
@app.get("/api/incidents")
def list_incidents(level: str = "", status: str = "", start: float | None = None, end: float | None = None,
                   limit: int = Query(200, ge=1, le=5000)) -> list[dict]:
    return sentinel.store.incidents(level=level.upper(), status=status, start=start, end=end, limit=limit)


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: int) -> dict:
    item = sentinel.store.incident(incident_id)
    if item is None:
        raise HTTPException(404, "Incident not found")
    return item


class IncidentPatch(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=1000)


@app.patch("/api/incidents/{incident_id}")
def patch_incident(incident_id: int, body: IncidentPatch) -> dict:
    if body.status is not None and body.status not in INCIDENT_STATUSES:
        raise HTTPException(400, f"status must be one of {', '.join(INCIDENT_STATUSES)}")
    item = sentinel.store.update_incident(incident_id, status=body.status, notes=body.notes)
    if item is None:
        raise HTTPException(404)
    return item


@app.delete("/api/incidents/{incident_id}")
def delete_incident(incident_id: int) -> dict:
    if not sentinel.store.delete_incident(incident_id):
        raise HTTPException(404)
    return {"deleted": incident_id}


@app.post("/api/incidents/{incident_id}/alert")
def send_incident_alert(incident_id: int) -> dict:
    try:
        return sentinel.dispatch_alert(incident_id, confirmed=True)
    except KeyError:
        raise HTTPException(404) from None


# --------------------------------------------------------------- contacts
class ContactIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    channel: str
    address: str = Field(min_length=1, max_length=120)


class ContactPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    enabled: bool | None = None


@app.get("/api/contacts")
def list_contacts() -> dict:
    return {"contacts": sentinel.store.contacts(), "channels": alerts.channel_status(),
            "log": sentinel.store.alert_log(20), "alert_mode": sentinel.settings["alert_mode"]}


@app.post("/api/contacts")
def add_contact(body: ContactIn) -> dict:
    address = body.address.strip()
    error = alerts.validate_address(body.channel, address)
    if error:
        raise HTTPException(400, error)
    return sentinel.store.add_contact(body.name.strip(), body.channel, address)


@app.patch("/api/contacts/{contact_id}")
def patch_contact(contact_id: int, body: ContactPatch) -> dict:
    item = sentinel.store.update_contact(contact_id, name=body.name, enabled=body.enabled)
    if item is None:
        raise HTTPException(404)
    return item


@app.delete("/api/contacts/{contact_id}")
def delete_contact(contact_id: int) -> dict:
    sentinel.store.delete_contact(contact_id)
    return {"deleted": contact_id}


@app.post("/api/contacts/{contact_id}/test")
def test_contact(contact_id: int) -> dict:
    contact = sentinel.store.contact(contact_id)
    if contact is None:
        raise HTTPException(404)
    ok, error = sentinel.notifier.send(contact, "Sentinel Street test alert",
                                       "This is a test message from your Sentinel Street dashboard. "
                                       "If you received it, alerts to you are working.")
    sentinel.store.log_alert(None, contact_id, contact["channel"], ok, error)
    if not ok:
        raise HTTPException(502, error)
    return {"message": f"Test sent to {contact['name']}"}


# --------------------------------------------------------------- settings
@app.get("/api/settings")
def get_settings() -> dict:
    return sentinel.settings


@app.put("/api/settings")
def put_settings(values: dict) -> dict:
    try:
        return sentinel.update_settings(values)
    except SettingsError as error:
        raise _bad_request(error) from None


class LocationIn(BaseModel):
    lat: float = Field(allow_inf_nan=False)
    lng: float = Field(allow_inf_nan=False)
    accuracy: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    label: str = ""
    source: str = "manual"


@app.put("/api/location")
def put_location(body: LocationIn) -> dict:
    try:
        return sentinel.set_location(body.lat, body.lng, body.accuracy, body.label, body.source)
    except SettingsError as error:
        raise _bad_request(error) from None


# --------------------------------------------------------------- hardware
@app.get("/api/hardware/ports")
def ports() -> list[dict]:
    return hardware.list_ports()


class Connect(BaseModel):
    port: str = ""


@app.post("/api/hardware/connect")
def connect(body: Connect) -> dict:
    ok, message = sentinel.connect_hardware(body.port)
    if not ok:
        raise HTTPException(409, message)
    return {"message": message}


class HardwareTest(BaseModel):
    brightness: int = Field(ge=0, le=100)
    buzzer: bool = False
    seconds: float = Field(default=3, gt=0, le=30)


@app.post("/api/hardware/test")
def hardware_test(body: HardwareTest) -> dict:
    sentinel.hardware.test_output(body.brightness, body.buzzer, body.seconds)
    return {"message": f"Testing light {body.brightness}%{' + buzzer' if body.buzzer else ''} for {body.seconds:g}s"}


# -------------------------------------------------------- analytics/report
@app.get("/api/heatmap")
def heatmap(days: int = Query(7, ge=1, le=90)) -> dict:
    return sentinel.heatmap(days)


@app.get("/api/analytics")
def analytics(days: int = Query(7, ge=1, le=90)) -> dict:
    return sentinel.analytics(days)


def _period(start: str, end: str) -> tuple[datetime, datetime]:
    tz = sentinel.tz
    try:
        first = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=tz)
        last = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=tz)
    except ValueError:
        raise HTTPException(400, "Dates must be YYYY-MM-DD") from None
    if last < first:
        raise HTTPException(400, "End date is before start date")
    if (last - first).days > 3660 or last.year > 9000:
        raise HTTPException(400, "Date range is too large")
    return first, last


@app.get("/api/reports/pdf")
def report_pdf(start: str, end: str) -> Response:
    first, last = _period(start, end)
    incidents = sentinel.store.incidents(start=first.timestamp(), end=(last + timedelta(days=1)).timestamp(), limit=None)
    data = reports.build_pdf(incidents, start=first, end=last, tz=sentinel.tz,
                             location=sentinel.settings["light_location"])
    name = f"sentinel-report-{start}-to-{end}.pdf"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/reports/csv")
def report_csv(start: str, end: str) -> Response:
    first, last = _period(start, end)
    incidents = sentinel.store.incidents(start=first.timestamp(), end=(last + timedelta(days=1)).timestamp(), limit=None)
    name = f"sentinel-incidents-{start}-to-{end}.csv"
    return Response(reports.build_csv(incidents, sentinel.tz), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/zones")
def get_zones() -> list[dict]:
    return sentinel.settings["zones"]


@app.put("/api/zones")
def put_zones(zones: list[dict]) -> list[dict]:
    from .zones import ZoneError

    try:
        return sentinel.set_zones(zones)
    except (ZoneError, SettingsError) as error:
        raise _bad_request(error) from None


@app.post("/api/voice/test")
def voice_test() -> dict:
    text = sentinel.settings["voice_high"]
    if not sentinel.speaker.say(text):
        raise HTTPException(409, sentinel.speaker.last_error or "Still speaking the previous message")
    return {"message": "Speaking the HIGH warning"}


@app.post("/api/sos/simulate")
def sos_simulate() -> dict:
    """Same as pressing the SOS button on the pole (for demos and testing without hardware)."""
    sentinel.hardware.press_sos()
    return {"message": "SOS pressed"}


@app.post("/api/sos/clear")
def sos_clear() -> dict:
    sentinel.clear_sos()
    return {"message": "SOS cleared"}


@app.get("/api/models")
def models() -> list[dict]:
    return [{"id": key, **meta, "downloaded": (ROOT / f"{key}.pt").exists()} for key, meta in MODELS.items()]


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "time": time.time()}
