"""The privileged helper, `sensors-guid`. See ADR 0005 and ADR 0009.

This package holds exactly one module, `sensors_guid`, and that module uses
only the standard library. Two rules make that necessary:

1. The module runs as **root** under systemd. Every import it makes is code
   that runs as root, so it makes none outside the standard library.
2. The install script copies `sensors_guid.py` on its own to
   `/usr/local/lib/sensors-gui/`, so that root never runs code from a
   directory the user can write. A file that imported its neighbours could
   not be copied alone.

The client side is `sensors_gui.collectors.privileged`. It imports this module
for the protocol constants and the channel catalogue, which costs nothing:
importing it starts no server and reads no sensor.
"""
