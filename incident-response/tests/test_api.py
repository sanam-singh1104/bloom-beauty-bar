from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from responder import context as telemetry_context
from responder.main import Settings, create_app

FAKE_CONTEXT = {
    "alert": {},
    "request_counts_by_status": {"500": 2},
    "error_logs": [{"message": "Unhandled error: OperationalError"}],
    "traces": [],
    "errors": [],
}


@pytest.fixture
def make_client(tmp_path, monkeypatch, fake_claude):
    monkeypatch.setattr(telemetry_context, "gather", lambda alert, **kw: FAKE_CONTEXT)

    def make(token="tok", **overrides):
        settings = Settings(
            incidents_dir=tmp_path / "incidents",
            workspace_dir=str(tmp_path),
            token=token,
            claude_command=fake_claude(),
            **overrides,
        )
        return TestClient(create_app(settings))

    return make


def only_incident(client, response):
    """The one incident a POST created (background work has finished by now)."""
    assert response.status_code == 202
    [incident] = response.json()["incidents"]
    return client.get(f"/incidents/{incident['id']}").json()


def test_firing_alert_is_investigated(make_client, payload):
    client = make_client()

    incident = only_incident(client, client.post("/alerts", json=payload))

    assert incident["state"] == "done"
    assert incident["endpoint"] == "POST /api/bookings"
    assert incident["report"] == "## Summary\nAll good."
    assert incident["num_turns"] == 3
    assert incident["files"] == [
        "alert.json",
        "claude-output.json",
        "context.json",
        "prompt.md",
        "report.md",
        "status.json",
    ]
    assert client.get("/incidents").json()[0]["id"] == incident["id"]


def test_dry_run_gathers_but_does_not_launch(make_client, payload, tmp_path):
    client = make_client()

    incident = only_incident(client, client.post("/alerts?dry_run=true", json=payload))

    assert incident["state"] == "dry_run"
    assert incident["logs"] == 1
    assert incident["report"] is None
    assert "prompt.md" in incident["files"]
    assert not (tmp_path / "stdin.txt").exists()  # the fake CLI never ran


def test_without_token_context_is_saved_and_launch_skipped(make_client, payload):
    client = make_client(token="")

    incident = only_incident(client, client.post("/alerts", json=payload))

    assert incident["state"] == "skipped"
    assert "CLAUDE_CODE_OAUTH_TOKEN" in incident["reason"]
    assert "prompt.md" in incident["files"]
    assert client.get("/health").json() == {"status": "ok", "token_configured": False}


def test_repeat_notifications_are_not_reinvestigated(make_client, payload):
    client = make_client()

    first = client.post("/alerts", json=payload).json()
    second = client.post("/alerts", json=payload).json()

    assert len(first["incidents"]) == 1
    assert second["incidents"] == []
    assert "already investigated" in second["skipped"][0]


def test_zero_cooldown_allows_reinvestigation(make_client, payload):
    client = make_client(cooldown=timedelta(0))
    client.post("/alerts", json=payload)
    assert len(client.post("/alerts", json=payload).json()["incidents"]) == 1


def test_other_alerts_are_acknowledged_and_ignored(make_client, payload):
    client = make_client()
    payload["alerts"][0]["labels"]["alertname"] = "TestAlert"

    response = client.post("/alerts", json=payload)

    assert response.status_code == 202
    assert response.json()["incidents"] == []
    assert client.get("/incidents").json() == []


def test_bad_body_is_400(make_client):
    client = make_client()
    assert client.post("/alerts", content=b"not json").status_code == 400
    assert client.post("/alerts", json=[1, 2]).status_code == 400


def test_unknown_incident_is_404(make_client):
    client = make_client()
    assert client.get("/incidents/nope").status_code == 404
    assert client.get("/incidents/..%2F..%2Fetc").status_code == 404


def test_a_crash_while_handling_is_recorded(make_client, payload, monkeypatch):
    def boom(alert, **kw):
        raise RuntimeError("tempo exploded")

    monkeypatch.setattr(telemetry_context, "gather", boom)
    client = make_client()

    incident = only_incident(client, client.post("/alerts", json=payload))

    assert incident["state"] == "failed"
    assert incident["reason"] == "RuntimeError: tempo exploded"
