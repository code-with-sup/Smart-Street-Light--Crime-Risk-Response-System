"""Video deletion keeps the incident, snapshot and other videos intact."""
from sentinel.config import EVIDENCE_DIR
from sentinel import server


def incident(store, name):
    item = store.add_incident(ts=1000, level="HIGH", label="Test", confidence=.8,
        people=1, vehicles=0, reasons=["test"], snapshot=name + ".jpg",
        lat=None, lng=None, alert_status="pending")
    (EVIDENCE_DIR / (name + ".jpg")).write_bytes(b"photo")
    (EVIDENCE_DIR / (name + ".mp4")).write_bytes(b"video")
    store.set_clip(item["id"], name + ".mp4")
    store.update_incident(item["id"], notes="Keep these notes")
    return item["id"]


def test_delete_selected_video_only(client):
    store = server.sentinel.store
    selected = incident(store, "selected")
    other = incident(store, "other")
    try:
        response = client.delete(f"/api/incidents/{selected}/clip")
        assert response.status_code == 200
        assert not (EVIDENCE_DIR / "selected.mp4").exists()
        assert (EVIDENCE_DIR / "selected.jpg").exists()
        assert (EVIDENCE_DIR / "other.mp4").exists()
        saved = store.incident(selected)
        assert saved["clip_url"] is None
        assert saved["notes"] == "Keep these notes"
        assert saved["snapshot_url"]
        assert client.delete(f"/api/incidents/{selected}/clip").status_code == 200
    finally:
        store.delete_incident(selected)
        store.delete_incident(other)


def test_delete_missing_incident(client):
    assert client.delete("/api/incidents/999999999/clip").status_code == 404


def test_missing_file_can_clear_reference(client):
    store = server.sentinel.store
    selected = incident(store, "missing")
    (EVIDENCE_DIR / "missing.mp4").unlink()
    try:
        assert client.delete(f"/api/incidents/{selected}/clip").status_code == 200
        assert store.incident(selected)["clip"] is None
    finally:
        store.delete_incident(selected)
