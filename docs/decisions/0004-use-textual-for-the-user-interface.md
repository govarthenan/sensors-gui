# ADR 0004 — Build the user interface with Textual

- Date: 2026-09-16
- Status: accepted
- Decided by: Gova

## Context

Four options were compared: Qt through PySide6, GTK4 with libadwaita, a local
web user interface, and a terminal user interface with Textual.

## Decision

Use **Textual**. The application runs in a terminal.

Gova chose this option.

## Consequences

- The application is light. It has no system package dependency, no X11 or
  Wayland dependency, and it works over SSH.
- The whole stack stays in Python and installs through `uv`.
- The layout must work in a character grid. Graphs use sparklines, bar meters
  and the `textual-plotext` widget, not smooth vector charts.
- Colour is limited to what the terminal gives. The design must work with a
  256-colour palette and must stay readable in a small window.
- There is no system tray icon and no desktop notification widget. If Gova
  wants an alarm on the desktop, the application calls `notify-send`.
- The name `sensors-gui` stays, although the interface is a TUI.
- Textual can also serve the same application in a browser with
  `textual serve`. That gives a web view later at no extra design cost.
