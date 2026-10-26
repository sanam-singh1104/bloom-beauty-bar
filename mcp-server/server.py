"""Bloom Beauty Bar MCP server: one read-only tool, `get_booking_stats`.

Gives an agent booking numbers without giving it the database, the full
bookings API, or customer details. Runs over stdio:

    python mcp-server/server.py

BLOOM_API_URL picks the app to read (default http://localhost:8000).
"""

import os
from datetime import datetime

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

import stats

API_URL = os.environ.get("BLOOM_API_URL", "http://localhost:8000")

mcp = MCPServer(
    "bloom-stats",
    instructions="Read-only booking statistics for Bloom Beauty Bar. "
    "Aggregate counts only; no customer names or contact details.",
)


@mcp.tool(
    annotations=ToolAnnotations(
        title="Booking stats",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
)
def get_booking_stats() -> dict:
    """Current booking statistics for the salon.

    Returns totals (all, upcoming, past), the next booking time, upcoming
    bookings per service, bookings per day for the next 7 days, and services
    with no upcoming bookings. Times are salon local time. Contains no
    customer names or contact details.
    """
    try:
        services, bookings = stats.fetch(API_URL)
    except OSError as exc:  # URLError, timeouts, refused connections
        raise ToolError(
            f"Can't reach the Bloom API at {API_URL} ({exc}). Is the app running "
            "(docker compose up -d backend), or is BLOOM_API_URL set correctly?"
        ) from exc
    return stats.summarize(services, bookings, datetime.now())


if __name__ == "__main__":
    mcp.run()
