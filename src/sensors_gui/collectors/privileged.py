"""The privileged collector. It reads from `sensors-guid` over a Unix socket.

This is the client half of ADR 0005. The helper, `sensors_gui.helper.sensors_guid`,
runs as root and holds the two sources that need it: the RAPL CPU energy
counters and the NVMe SMART log. This half runs as the user, holds no
privilege, and never asks for a password.

**The screen works without the helper.** ADR 0005 rule 3: when the socket is
absent, the channels are still discovered — the catalogue is built from files
that any user can read — and every reading carries the error "needs the
helper", so a person can see what is missing and why. Nothing is silently
dropped.

The helper samples the hardware on its own clock, once a second for RAPL and
once a minute for SMART. So this collector asks for everything on every pass
and costs the hardware nothing; the round trip on a Unix socket is far cheaper
than any of the sensors behind it.
"""

from __future__ import annotations

import contextlib
import json
import logging
import socket
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sensors_gui.helper import sensors_guid
from sensors_gui.model import Group, Reading, SensorId, SensorSpec, Unit

logger = logging.getLogger(__name__)

SOURCE = "privileged"

# The message a channel carries while the helper is not running. It names the
# service, because the answer is one command.
NO_HELPER_ERROR = "needs the helper; start it with: systemctl start sensors-guid"

# How long to wait before trying the socket again after a failure. Without it,
# a screen at 10 Hz would try to connect ten times a second for ever.
RECONNECT_INTERVAL = 5.0

# How long to wait for the helper to answer one request. The helper never reads
# hardware inside a request, so an answer that takes longer than this means it
# is wedged, and a wedged helper must not hold up the screen.
REQUEST_TIMEOUT = 2.0


class PrivilegedCollector:
    """Read the root-only channels through the `sensors-guid` helper."""

    name = SOURCE

    def __init__(
        self,
        socket_path: Path | str = sensors_guid.DEFAULT_SOCKET_PATH,
        clock: Callable[[], float] = time.monotonic,
        reconnect_interval: float = RECONNECT_INTERVAL,
        timeout: float = REQUEST_TIMEOUT,
        catalogue_source: Callable[[], list[sensors_guid.Channel]] = sensors_guid.discover_channels,
    ) -> None:
        """Create the collector.

        Args:
            socket_path: Where the helper's socket is.
            clock: The source of time. It must not go backwards.
            reconnect_interval: The shortest time between two attempts to
                reach a helper that is not answering.
            timeout: How long to wait for one answer.
            catalogue_source: The call that lists the channels when the helper
                cannot be reached. The default reads this machine. A test
                points it at a temporary tree.
        """
        self.socket_path = Path(socket_path)
        self.clock = clock
        self.reconnect_interval = reconnect_interval
        self.timeout = timeout
        self.catalogue_source = catalogue_source
        self._connection: socket.socket | None = None
        self._stream: Any = None
        self._specs: list[SensorSpec] = []
        self._next_attempt = 0.0
        self._reported_absent = False

    # --- the collector contract ---------------------------------------------

    def discover(self) -> list[SensorSpec]:
        """Find every channel the helper can give.

        The helper is asked first, because it is the authority. When it cannot
        be reached, the same catalogue is built here from the world-readable
        parts of the machine, so that the rows still appear.
        """
        described = self._request({"protocol": sensors_guid.PROTOCOL_VERSION, "command": "describe"})
        if described is not None and described.get("ok"):
            self._warn_on_version_mismatch(described.get("helper_version"))
            channels = [_channel_from_wire(item) for item in described.get("channels", [])]
            channels = [channel for channel in channels if channel is not None]
            logger.info("privileged: the helper gives %d channels", len(channels))
        else:
            channels = self.catalogue_source()
            logger.info(
                "privileged: the helper is not answering on %s; %d channels will show %r",
                self.socket_path,
                len(channels),
                NO_HELPER_ERROR,
            )

        self._specs = [_spec_from_channel(channel) for channel in channels]
        return list(self._specs)

    def read(self) -> list[Reading]:
        """Read every channel found by the last `discover` call. This never raises."""
        if not self._specs:
            return []

        answer = self._request({"protocol": sensors_guid.PROTOCOL_VERSION, "command": "read"})
        now = self.clock()
        if answer is None or not answer.get("ok"):
            error = NO_HELPER_ERROR if answer is None else str(answer.get("error", "the helper refused the request"))
            return [Reading.failed(spec.id, error, read_at=now) for spec in self._specs]

        by_key = {(item.get("device"), item.get("channel")): item for item in answer.get("readings", [])}
        readings: list[Reading] = []
        for spec in self._specs:
            item = by_key.get((spec.id.device, spec.id.channel))
            if item is None:
                readings.append(Reading.failed(spec.id, "the helper did not report this channel", read_at=now))
                continue
            readings.append(_reading_from_wire(spec.id, item, now))
        return readings

    def close(self) -> None:
        """Close the connection to the helper. The hardware is not touched."""
        self._disconnect()
        self._specs = []

    # --- the socket ---------------------------------------------------------

    def _request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Send one request and return the answer, or None when the helper cannot be reached.

        One retry is made on a broken connection, because a helper that has
        been restarted leaves the old connection dead and the next one works.
        """
        for attempt in (1, 2):
            connection = self._connect()
            if connection is None:
                return None
            try:
                connection.sendall((json.dumps(request) + "\n").encode("utf-8"))
                line = self._stream.readline()
            except OSError as exc:
                logger.debug("privileged: the connection failed on attempt %d: %s", attempt, exc)
                self._disconnect()
                continue
            if not line:
                logger.debug("privileged: the helper closed the connection on attempt %d", attempt)
                self._disconnect()
                continue
            try:
                answer = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("privileged: the helper sent something that is not JSON: %s", exc)
                self._disconnect()
                return None
            if isinstance(answer, dict):
                return answer
            logger.warning("privileged: the helper sent JSON that is not an object")
            self._disconnect()
            return None

        self._hold_off()
        return None

    def _connect(self) -> socket.socket | None:
        """Return a live connection, making one if needed, or None when that fails."""
        if self._connection is not None:
            return self._connection
        if self.clock() < self._next_attempt:
            return None

        try:
            connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            connection.settimeout(self.timeout)
            connection.connect(str(self.socket_path))
        except OSError as exc:
            if not self._reported_absent:
                logger.info("privileged: cannot reach the helper at %s: %s", self.socket_path, exc)
                self._reported_absent = True
            self._hold_off()
            return None

        self._connection = connection
        self._stream = connection.makefile("rb")
        self._reported_absent = False
        logger.debug("privileged: connected to %s", self.socket_path)
        return connection

    def _disconnect(self) -> None:
        """Drop the connection, quietly. The next request makes a new one."""
        if self._stream is not None:
            with contextlib.suppress(OSError):
                self._stream.close()
            self._stream = None
        if self._connection is not None:
            with contextlib.suppress(OSError):
                self._connection.close()
            self._connection = None

    def _hold_off(self) -> None:
        """Refuse to try the socket again until the reconnect interval has passed."""
        self._next_attempt = self.clock() + self.reconnect_interval

    def _warn_on_version_mismatch(self, helper_version: object) -> None:
        """Log once when the installed helper is not the one this client was built with.

        The install script copies `sensors_guid.py` out of the repository to
        `/usr/local/lib/sensors-gui/`, so the two can drift apart if the
        repository changes and the install is not repeated. This turns that
        into a line in the log rather than a puzzling missing channel.
        """
        if helper_version is not None and helper_version != sensors_guid.HELPER_VERSION:
            logger.warning(
                "privileged: the installed helper is version %s, this client expects %s; "
                "run scripts/install-helper.sh again",
                helper_version,
                sensors_guid.HELPER_VERSION,
            )


# --- turning the wire format into model objects ------------------------------


def _channel_from_wire(item: object) -> sensors_guid.Channel | None:
    """Build a `Channel` from one entry of a describe answer, or None when it is malformed."""
    if not isinstance(item, dict):
        logger.warning("privileged: a channel in the describe answer is not an object")
        return None
    try:
        return sensors_guid.Channel(
            device=str(item["device"]),
            channel=str(item["channel"]),
            label=str(item["label"]),
            group=str(item["group"]),
            unit=str(item["unit"]),
            low=_optional_float(item.get("low")),
            high=_optional_float(item.get("high")),
            warn=_optional_float(item.get("warn")),
            critical=_optional_float(item.get("critical")),
            origin=str(item.get("origin", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("privileged: a channel in the describe answer is malformed: %s", exc)
        return None


def _spec_from_channel(channel: sensors_guid.Channel) -> SensorSpec:
    """Build a `SensorSpec` from a helper channel.

    `min_interval` is zero on purpose. The helper owns the rate at which the
    hardware is actually read — once a second for RAPL, once a minute for
    SMART — so a second interval here would only add staleness on top of it.
    """
    return SensorSpec(
        id=SensorId(source=SOURCE, device=channel.device, channel=channel.channel),
        label=channel.label,
        group=_group_of(channel.group),
        unit=_unit_of(channel.unit),
        low=channel.low,
        high=channel.high,
        warn=channel.warn,
        critical=channel.critical,
        min_interval=0.0,
        origin=channel.origin,
    )


def _reading_from_wire(sensor_id: SensorId, item: dict[str, Any], now: float) -> Reading:
    """Build a `Reading` from one entry of a read answer.

    The helper reports how old its value is. That age is turned back into a
    time on this side's clock, so that the screen shows the age of the real
    hardware read and not the age of the socket call.
    """
    error = item.get("error")
    age = _optional_float(item.get("age"))
    read_at = now if age is None else now - age

    value = _optional_float(item.get("value"))
    if value is None:
        return Reading.failed(sensor_id, str(error) if error else "the helper gave no value", read_at=read_at)
    return Reading.ok(sensor_id, value, read_at=read_at)


def _optional_float(value: object) -> float | None:
    """Return the value as a float, or None when it is absent or not a number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _group_of(name: str) -> Group:
    """Return the `Group` with this name, or `OTHER` when the name is not known."""
    try:
        return Group(name)
    except ValueError:
        logger.warning("privileged: the helper used an unknown group %r", name)
        return Group.OTHER


def _unit_of(name: str) -> Unit:
    """Return the `Unit` with this name, or `NONE` when the name is not known."""
    try:
        return Unit(name)
    except ValueError:
        logger.warning("privileged: the helper used an unknown unit %r", name)
        return Unit.NONE
