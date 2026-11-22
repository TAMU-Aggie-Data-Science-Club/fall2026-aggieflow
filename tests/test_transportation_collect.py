"""Offline tests for pipeline/collect/transportation.py's URL filter."""

import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "pipeline" / "collect" / "transportation.py"
_spec = importlib.util.spec_from_file_location("transportation_collect", _path)
collect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect)


def test_live_garage_counts_are_skipped():
    assert collect.clean_url("https://transport.tamu.edu/Parking/realtime.aspx") is None


def test_static_parking_pages_are_kept():
    url = "https://transport.tamu.edu/Parking/visitor.aspx"
    assert collect.clean_url(url) == url
