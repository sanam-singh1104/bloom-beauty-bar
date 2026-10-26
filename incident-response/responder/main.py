"""HTTP service: Grafana posts alerts here; each one becomes an investigation.

POST /alerts           Grafana webhook. Answers 202 at once; the work runs after.
                       ?dry_run=true gathers context and writes the prompt but
                       doesn't launch Claude Code.
GET  /incidents        Recent incidents, newest first.
GET  /incidents/{id}   One incident's status and report.
GET  /health

Each incident is a folder under INCIDENTS_DIR: alert.json, context.json,
prompt.md, report.md, claude-output.json, status.json.
"""

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, status

from . import context as telemetry_context
from .alerts import Alert, select_alerts
from .investigate import build_prompt, run_claude

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("responder")


@dataclass
class Settings:
    incidents_dir: Path = Path(os.environ.get("INCIDENTS_DIR", "/incidents"))
    workspace_dir: str = os.environ.get("WORKSPACE_DIR", "/workspace")
    prometheus_url: str = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
    loki_url: str = os.environ.get("LOKI_URL", "http://loki:3100")
    tempo_url: str = os.environ.get("TEMPO_URL", "http://tempo:3200")
    token: str = field(default_factory=lambda: os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""))
    model: str | None = os.environ.get("RESPONDER_CLAUDE_MODEL") or None
    timeout_seconds: int = int(os.environ.get("RESPONDER_TIMEOUT_SECONDS", "900"))
    # Grafana re-sends a firing alert (repeat_interval); don't re-investigate it
    # more often than this.
    cooldown: timedelta = timedelta(minutes=int(os.environ.get("RESPONDER_COOLDOWN_MINUTES", "30")))
    claude_command: list[str] | None = None  # tests swap in a fake CLI


class Responder:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.incidents_dir.mkdir(parents=True, exist_ok=True)
        self._last_launch: dict[str, datetime] = {}
        self._launch_lock = threading.Lock()  # one claim check at a time
        self._claude_lock = threading.Lock()  # one Claude Code session at a time

    def claim(self, alert: Alert, now: datetime) -> bool:
        """True if this alert should be investigated now (not in cooldown)."""
        with self._launch_lock:
            last = self._last_launch.get(alert.fingerprint)
            if last and now - last < self.settings.cooldown:
                return False
            self._last_launch[alert.fingerprint] = now
            return True

    def new_incident(self, alert: Alert, raw: dict, now: datetime) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", alert.name.lower()).strip("-")
        incident_id = f"{now:%Y%m%dT%H%M%SZ}-{slug}-{alert.fingerprint[:8]}"
        folder = self.settings.incidents_dir / incident_id
        folder.mkdir(parents=True, exist_ok=True)
        _write_json(folder / "alert.json", raw)
        self.set_status(incident_id, "received", alert=alert.name, endpoint=alert.endpoint)
        return incident_id

    def set_status(self, incident_id: str, state: str, **extra) -> None:
        path = self.settings.incidents_dir / incident_id / "status.json"
        current = json.loads(path.read_text()) if path.exists() else {"id": incident_id}
        current.update(extra, state=state, updated_at=datetime.now(UTC).isoformat())
        _write_json(path, current)
        log.info("incident %s: %s", incident_id, state)

    def handle(self, incident_id: str, alert: Alert, dry_run: bool) -> None:
        folder = self.settings.incidents_dir / incident_id
        s = self.settings
        try:
            self.set_status(incident_id, "gathering")
            ctx = telemetry_context.gather(
                alert,
                prometheus_url=s.prometheus_url,
                loki_url=s.loki_url,
                tempo_url=s.tempo_url,
                now=datetime.now(UTC),
            )
            _write_json(folder / "context.json", ctx)
            prompt = build_prompt(alert, ctx)
            (folder / "prompt.md").write_text(prompt, encoding="utf-8")
            gathered = {
                "logs": len(ctx["error_logs"]),
                "traces": len(ctx["traces"]),
                "gather_errors": ctx["errors"],
            }

            if dry_run:
                self.set_status(incident_id, "dry_run", **gathered)
                return
            if not s.token:
                self.set_status(
                    incident_id,
                    "skipped",
                    reason="CLAUDE_CODE_OAUTH_TOKEN is not set; context and prompt are saved.",
                    **gathered,
                )
                return

            self.set_status(incident_id, "queued", **gathered)
            with self._claude_lock:
                self.set_status(incident_id, "investigating")
                result = run_claude(
                    prompt,
                    workdir=s.workspace_dir,
                    token=s.token,
                    timeout_seconds=s.timeout_seconds,
                    model=s.model,
                    command=s.claude_command,
                )
            (folder / "report.md").write_text(result.report, encoding="utf-8")
            if result.raw is not None:
                _write_json(folder / "claude-output.json", result.raw)
            extra = {}
            if result.raw:
                extra = {
                    k: result.raw.get(k) for k in ("total_cost_usd", "num_turns") if k in result.raw
                }
            self.set_status(incident_id, "done" if result.ok else "failed", **extra)
            log.info("incident %s report:\n%s", incident_id, result.report)
        except Exception as exc:  # keep the service up; record what broke
            log.exception("incident %s failed", incident_id)
            self.set_status(incident_id, "failed", reason=f"{type(exc).__name__}: {exc}")


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def create_app(settings: Settings | None = None) -> FastAPI:
    responder = Responder(settings or Settings())
    app = FastAPI(title="Bloom incident responder")
    app.state.responder = responder

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "token_configured": bool(responder.settings.token)}

    @app.post("/alerts", status_code=status.HTTP_202_ACCEPTED)
    async def receive_alerts(
        request: Request, background: BackgroundTasks, dry_run: bool = False
    ) -> dict:
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(400, "Body must be a Grafana webhook JSON payload.") from exc
        if not isinstance(payload, dict):
            raise HTTPException(400, "Body must be a Grafana webhook JSON payload.")

        alerts, skipped = select_alerts(payload)
        raw_by_fingerprint = {a.get("fingerprint"): a for a in payload.get("alerts") or []}
        now = datetime.now(UTC)
        incidents = []
        for alert in alerts:
            if not dry_run and not responder.claim(alert, now):
                skipped.append(
                    f"{alert.name}: already investigated in the last {responder.settings.cooldown}"
                )
                continue
            raw = raw_by_fingerprint.get(alert.fingerprint, {})
            incident_id = responder.new_incident(alert, raw, now)
            background.add_task(responder.handle, incident_id, alert, dry_run)
            incidents.append({"id": incident_id, "alert": alert.name, "endpoint": alert.endpoint})
        for reason in skipped:
            log.info("skipped alert: %s", reason)
        return {"incidents": incidents, "skipped": skipped, "dry_run": dry_run}

    @app.get("/incidents")
    def list_incidents(limit: int = 20) -> list[dict]:
        folders = sorted(responder.settings.incidents_dir.iterdir(), reverse=True)
        found = []
        for folder in folders:
            status_file = folder / "status.json"
            if status_file.exists():
                found.append(json.loads(status_file.read_text()))
            if len(found) >= limit:
                break
        return found

    @app.get("/incidents/{incident_id}")
    def get_incident(incident_id: str) -> dict:
        folder = responder.settings.incidents_dir / incident_id
        if not re.fullmatch(r"[\w.-]+", incident_id) or not (folder / "status.json").exists():
            raise HTTPException(404, "Incident not found.")
        report = folder / "report.md"
        return {
            **json.loads((folder / "status.json").read_text()),
            "report": report.read_text(encoding="utf-8") if report.exists() else None,
            "files": sorted(p.name for p in folder.iterdir()),
        }

    return app
