from types import SimpleNamespace

import pytest

from app.telemetry import route_label


def route(path):
    return SimpleNamespace(path=path)


@pytest.mark.parametrize(
    "scope, expected",
    [
        (
            {"path": "/api/bookings/42", "route": route("/api/bookings/{booking_id}")},
            "/api/bookings/{booking_id}",
        ),
        ({"path": "/api/bookings", "route": route("/api/bookings")}, "/api/bookings"),
        ({"path": "/api/nope"}, "/api/*"),
        ({"path": "/manage.html", "route": route("")}, "static"),
        ({"path": "/"}, "static"),
    ],
)
def test_route_label_uses_templates_not_raw_paths(scope, expected):
    assert route_label(scope) == expected
