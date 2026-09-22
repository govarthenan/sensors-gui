"""Comparison spike: the same one live value, in a Qt window through PySide6.

    uv run python lab/exp-0014-gui-framework-spike/spike_qt.py --hz 10 [--all]

This exists so that ADR 0012 compares measured numbers, not opinions. It draws
the same three things as `spike_web.py`: a large number, an arc gauge and a
line over the last 120 samples, with every channel in a grid when `--all` is
given. The sampler runs on a worker thread, because `pass-profile.py` shows
the NVIDIA collector blocks for up to 68 ms.

PySide6 is a development dependency only while this measurement is made. See
the README of this experiment for how to put it back.

Nothing is written to hardware.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import deque

from PySide6.QtCore import QObject, QPointF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from sensors_gui import naming
from sensors_gui.collectors.hwmon import HwmonCollector
from sensors_gui.collectors.nvidia import NvidiaCollector
from sensors_gui.collectors.power_supply import PowerSupplyCollector
from sensors_gui.collectors.privileged import PrivilegedCollector
from sensors_gui.collectors.system import SystemCollector
from sensors_gui.model import SensorSpec
from sensors_gui.registry import Registry
from sensors_gui.sampler import Sampler

SPIKE_LABEL = "Tctl"
ACCENT = QColor("#4cc2ff")
WARM = QColor("#f0a04b")
TRACK = QColor("#273040")
DIM = QColor("#8b949e")
HISTORY = 120


class SampleWorker(QObject):
    """Reads the real sampler on its own thread and reports each pass."""

    ready = Signal(dict, float)

    def __init__(self, hz: float) -> None:
        """Create the worker.

        Args:
            hz: The sample rate.
        """
        super().__init__()
        self.hz = hz
        self.registry = Registry(
            [
                HwmonCollector(),
                NvidiaCollector(),
                PowerSupplyCollector(),
                PrivilegedCollector(),
                SystemCollector(),
            ]
        )
        self.sampler = Sampler(self.registry)
        self.specs: list[SensorSpec] = []
        self.running = True

    def discover(self, stream_all: bool) -> None:
        """Find every sensor and choose the ones this spike shows."""
        self.registry.discover()
        decorated = [naming.friendly(raw) for raw in self.registry.specs()]
        self.specs = decorated if stream_all else ([s for s in decorated if s.label == SPIKE_LABEL] or decorated[:1])

    def loop(self) -> None:
        """Sample at the chosen rate until `running` goes false."""
        period = 1.0 / self.hz
        start = time.monotonic()
        passes = 0
        while self.running:
            began = time.perf_counter()
            sample = self.sampler.sample()
            pass_ms = (time.perf_counter() - began) * 1000
            by_id = sample.by_id()
            values = {spec.id.key: (by_id[spec.id].value if spec.id in by_id else None) for spec in self.specs}
            self.ready.emit(values, pass_ms)
            passes += 1
            time.sleep(max(start + passes * period - time.monotonic(), 0.0))
        self.registry.close()


class Gauge(QWidget):
    """An arc gauge, drawn with the vector painter."""

    def __init__(self) -> None:
        """Create the gauge."""
        super().__init__()
        self.setMinimumSize(260, 145)
        self.fraction = 0.0

    def paintEvent(self, event: object) -> None:  # noqa: N802 - Qt names the method
        """Draw the track and the filled part of the arc."""
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.arcMoveTo(20, 20, 220, 220, 180)
        path.arcTo(20, 20, 220, 220, 180, -180)
        painter.setPen(QPen(TRACK, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawPath(path)
        filled = QPainterPath()
        filled.arcMoveTo(20, 20, 220, 220, 180)
        filled.arcTo(20, 20, 220, 220, 180, -180 * self.fraction)
        painter.setPen(
            QPen(WARM if self.fraction > 0.8 else ACCENT, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawPath(filled)
        painter.end()


class Trace(QWidget):
    """A line over the last 120 samples, with an honest vertical scale."""

    def __init__(self) -> None:
        """Create the chart."""
        super().__init__()
        self.setMinimumSize(520, 150)
        self.values: deque[float] = deque(maxlen=HISTORY)

    def paintEvent(self, event: object) -> None:  # noqa: N802 - Qt names the method
        """Draw the line."""
        _ = event
        if len(self.values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        low, high = min(self.values), max(self.values)
        floor = max(1.0, abs(high) * 0.1)
        if high - low < floor:
            middle = (high + low) / 2
            low, high = middle - floor / 2, middle + floor / 2
        points = [
            QPointF(
                40 + index / (len(self.values) - 1) * (self.width() - 60),
                self.height() - 12 - (value - low) / (high - low) * (self.height() - 30),
            )
            for index, value in enumerate(self.values)
        ]
        painter.setPen(QPen(ACCENT, 2))
        painter.drawPolyline(points)
        painter.setPen(QPen(DIM, 1))
        painter.drawText(4, 14, f"{high:.1f}")
        painter.drawText(4, self.height() - 4, f"{low:.1f}")
        painter.end()


class Window(QMainWindow):
    """The spike window."""

    def __init__(self, specs: list[SensorSpec], hz: float) -> None:
        """Build the window.

        Args:
            specs: Every channel to show. The first one gets the gauge.
            hz: The sample rate, for the label.
        """
        super().__init__()
        self.setWindowTitle("sensors-gui spike (Qt)")
        self.specs = specs
        self.frames = 0
        self.first_at = 0.0
        self.ms_total = 0.0
        self.ms_max = 0.0

        central = QWidget()
        self.setCentralWidget(central)
        column = QVBoxLayout(central)
        row = QHBoxLayout()
        column.addLayout(row)

        self.value = QLabel("—")
        self.value.setFont(QFont("", 40, QFont.Weight.DemiBold))
        self.gauge = Gauge()
        left = QVBoxLayout()
        left.addWidget(QLabel(f"{specs[0].label}  ({specs[0].unit.symbol})"))
        left.addWidget(self.value)
        left.addWidget(self.gauge)
        row.addLayout(left)

        self.trace = Trace()
        row.addWidget(self.trace)

        self.cost = QLabel("—")
        row.addWidget(self.cost)
        row.addStretch(1)

        self.cells: dict[str, QLabel] = {}
        if len(specs) > 1:
            grid = QGridLayout()
            column.addLayout(grid)
            for index, spec in enumerate(specs):
                cell = QLabel("—")
                cell.setToolTip(f"{spec.id.key}\n{spec.origin}")
                name = QLabel(spec.label)
                name.setToolTip(f"{spec.id.key}\n{spec.origin}")
                grid.addWidget(name, index % 45, (index // 45) * 2)
                grid.addWidget(cell, index % 45, (index // 45) * 2 + 1)
                self.cells[spec.id.key] = cell
        column.addStretch(1)
        self.hz = hz

    def on_sample(self, values: dict[str, float | None], pass_ms: float) -> None:
        """Take one pass from the worker and repaint."""
        now = time.perf_counter() * 1000
        first = self.specs[0]
        value = values.get(first.id.key)
        self.value.setText("—" if value is None else f"{value:.1f}")
        low = first.low if first.low is not None else 0.0
        high = first.high if first.high is not None else 100.0
        if value is not None:
            self.gauge.fraction = min(max((value - low) / max(high - low, 1e-9), 0.0), 1.0)
            self.trace.values.append(value)
        self.gauge.update()
        self.trace.update()
        for key, cell in self.cells.items():
            reading = values.get(key)
            cell.setText("—" if reading is None else (f"{reading:.0f}" if abs(reading) >= 1000 else f"{reading:.2f}"))

        self.frames += 1
        self.ms_total += pass_ms
        self.ms_max = max(self.ms_max, pass_ms)
        if not self.first_at:
            self.first_at = now
        rate = 1000 * (self.frames - 1) / (now - self.first_at) if self.frames > 1 else 0.0
        self.cost.setText(
            f"sampler pass {pass_ms:.2f} now, {self.ms_total / self.frames:.2f} mean, {self.ms_max:.2f} max ms\n"
            f"frames {self.frames}\nmeasured rate {rate:.2f} Hz\nchannels {len(self.specs)}"
        )


def main() -> None:
    """Run the Qt spike."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hz", type=float, default=2.0)
    parser.add_argument("--all", action="store_true", dest="stream_all")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    worker = SampleWorker(args.hz)
    worker.discover(args.stream_all)
    window = Window(worker.specs, args.hz)
    worker.ready.connect(window.on_sample)

    thread = QThread()
    worker.moveToThread(thread)
    thread.started.connect(worker.loop)
    thread.start()

    window.resize(2560, 1440)
    window.show()
    code = app.exec()
    worker.running = False
    thread.quit()
    thread.wait(5000)
    sys.exit(code)


if __name__ == "__main__":
    main()
