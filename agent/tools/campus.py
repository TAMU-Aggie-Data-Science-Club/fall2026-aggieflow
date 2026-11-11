"""campus_tools: live campus data.

PLACEHOLDER. Later:
- get_bus_routes    -> AggieSpirit JSON (aggiespirit.ts.tamu.edu/Home/GetActiveRoutes, ...)
- get_garage_counts -> live garage counts on the transport.tamu.edu homepage
Static parking and transit pages are indexed and searched by policy_tools.
"""

from datetime import datetime, timezone

from langchain_core.tools import tool

from agent.state import Passage


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@tool
def get_bus_routes(place: str | None = None) -> list[Passage]:
    """Bus routes running now, optionally near a place or stop (e.g. 'MSC',
    'RELLIS'). Use for questions about which bus to take."""
    near = f" near {place}" if place else ""
    return [{
        "id": "transportation:bus-routes:live",
        "source": "transportation",
        "title": "Active bus routes (placeholder)",
        "text": f"[placeholder] Bus routes running now{near} will appear here.",
        "source_url": "https://aggiespirit.ts.tamu.edu/RouteMap",
        "fetched_at": _now(),
    }]


@tool
def get_garage_counts() -> list[Passage]:
    """Live open-space counts for campus parking garages. Use for 'where can
    I park right now' questions."""
    return [{
        "id": "transportation:garage-counts:live",
        "source": "transportation",
        "title": "Live garage counts (placeholder)",
        "text": "[placeholder] Open spaces for each garage will appear here.",
        "source_url": "https://transport.tamu.edu/",
        "fetched_at": _now(),
    }]


TOOLS = [get_bus_routes, get_garage_counts]
