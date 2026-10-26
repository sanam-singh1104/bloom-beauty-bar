"""The server over the real MCP protocol (in-process). Needs the `mcp` package."""

import asyncio
import json
from datetime import datetime

import pytest

pytest.importorskip("mcp", reason="install mcp-server/requirements.txt to run")

from mcp import Client  # noqa: E402

import server  # noqa: E402
import stats  # noqa: E402


def call(coro_fn):
    async def run():
        async with Client(server.mcp) as client:
            return await coro_fn(client)

    return asyncio.run(run())


def test_exposes_exactly_one_read_only_tool():
    tools = call(lambda client: client.list_tools()).tools

    assert [t.name for t in tools] == ["get_booking_stats"]
    [tool] = tools
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False
    assert "no customer names" in " ".join(tool.description.split())


def test_tool_returns_stats(monkeypatch):
    monkeypatch.setattr(
        stats, "fetch", lambda url: ({1: "Haircut"}, [(1, datetime(2099, 1, 1, 9, 0))])
    )

    result = call(lambda client: client.call_tool("get_booking_stats", {}))

    assert not result.is_error
    data = json.loads(result.content[0].text)
    assert data["upcoming"] == 1
    assert data["upcoming_by_service"] == {"Haircut": 1}


def test_unreachable_api_gives_a_clear_error(monkeypatch):
    def refuse(url):
        raise ConnectionRefusedError("refused")

    monkeypatch.setattr(stats, "fetch", refuse)

    result = call(lambda client: client.call_tool("get_booking_stats", {}))

    assert result.is_error
    assert "Can't reach the Bloom API" in result.content[0].text
