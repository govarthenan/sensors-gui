"""Collectors. Each one reads one kind of sensor source.

See `docs/architecture.md` for the contract that every collector must keep.
"""

from sensors_gui.collectors.base import Collector

__all__ = ["Collector"]
