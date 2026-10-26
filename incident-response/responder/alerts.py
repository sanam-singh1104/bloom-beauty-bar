"""Pick out the alerts this responder handles from a Grafana webhook payload."""

from dataclasses import dataclass
from datetime import UTC, datetime

# alertname label -> the endpoint it watches if the alert has no `endpoint` label.
HANDLED_ALERTS = {"Booking creation server errors": "POST /api/bookings"}


@dataclass(frozen=True)
class Alert:
    name: str
    fingerprint: str
    endpoint: str  # e.g. "POST /api/bookings"
    starts_at: datetime
    summary: str
    window: str
    dashboard_url: str
    labels: dict
    annotations: dict
    values: dict

    @property
    def method(self) -> str:
        return self.endpoint.split(" ", 1)[0]

    @property
    def route(self) -> str:
        return self.endpoint.split(" ", 1)[-1]


def _parse_time(value: str | None) -> datetime:
    try:
        parsed = datetime.fromisoformat(value or "")
    except ValueError:
        return datetime.now(UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def select_alerts(payload: dict) -> tuple[list[Alert], list[str]]:
    """Firing alerts we handle, and a reason for each alert we skip."""
    handled, skipped = [], []
    for raw in payload.get("alerts") or []:
        labels = raw.get("labels") or {}
        annotations = raw.get("annotations") or {}
        name = labels.get("alertname", "?")
        if raw.get("status") != "firing":
            skipped.append(f"{name}: status is {raw.get('status')!r}, not firing")
            continue
        if name not in HANDLED_ALERTS:
            skipped.append(f"{name}: not an alert this responder handles")
            continue
        handled.append(
            Alert(
                name=name,
                fingerprint=raw.get("fingerprint") or name,
                endpoint=labels.get("endpoint") or HANDLED_ALERTS[name],
                starts_at=_parse_time(raw.get("startsAt")),
                summary=annotations.get("summary", ""),
                window=annotations.get("window", "5m"),
                dashboard_url=annotations.get("dashboard_url") or raw.get("dashboardURL", ""),
                labels=labels,
                annotations=annotations,
                values=raw.get("values") or {},
            )
        )
    return handled, skipped
