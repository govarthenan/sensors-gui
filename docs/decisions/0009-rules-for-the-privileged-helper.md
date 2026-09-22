# ADR 0009 — Rules for the code that runs as root

- Date: 2026-09-22
- Status: accepted
- Extends: ADR 0005 (the helper), ADR 0007 (this project writes nothing)

## Context

ADR 0005 decided **that** there would be a privileged helper, and gave it five
rules. It did not say **how** the helper should be built. Building it raised
four questions that each have a wrong answer that looks reasonable:

1. How does it read the NVMe SMART log — with the kernel's admin passthrough
   ioctl, or by running `nvme-cli`?
2. Where does the code live that root executes?
3. What stops the helper from writing, other than the intention not to?
4. What does the screen show when the helper is not running?

The context that makes these worth an ADR is `data/evidence/2026-09-22-thermal-shutdown/`.
A script written with good intentions stopped the CPU radiator fans and the
machine shut itself down at 98 °C. The lesson recorded there is that each of
the four faults looked reasonable on its own. Root code deserves rules written
down in advance, not judgement in the moment.

## Decision

### 1. No ioctl. A fixed argument list, and no shell.

The SMART log is read by running:

```
["/usr/sbin/nvme", "smart-log", "-o", "json", "/dev/nvme0"]
```

Not `NVME_IOCTL_ADMIN_CMD`. The passthrough ioctl carries an opcode, and the
same call that reads log page 02h can, with a different opcode, format the
namespace or write to it. A mistake in a `struct` layout would be a mistake
that reaches the drive. `nvme smart-log` cannot become a write however wrong
the code around it is.

The rules for that call:

- The argument list is fixed in the source. No part of it comes from a client.
- `shell=False`, always. There is no shell to quote for.
- The environment is replaced with `PATH` and `LC_ALL` alone.
- A timeout, so a drive that stops answering cannot wedge the helper.
- The exit code and both output streams are checked. A failure becomes an
  error on the channel, never a zero.

The device node comes from the machine's own `/sys/class/nvme`, never from a
request.

### 2. Root does not execute code from a directory the user can write.

`scripts/install-helper.sh` copies `sensors_guid.py` to
`/usr/local/lib/sensors-gui/`, owned `root:root`, mode `0644`, and the systemd
unit runs that copy. It does not run the file in `~/workbench`, because
anything that could write there could then choose what runs as root.

The cost is that two copies can drift apart. That is handled, not ignored:

- the install script records the SHA-256 of the copy it made;
- the helper reports a `helper_version` in its `describe` answer, and the
  client logs a warning when it does not match its own.

The install script is re-runnable, so the fix for drift is one command.

### 3. The helper may not write, and the system enforces it.

The code writes nothing. That is the intention. The unit makes it true whether
the code is right or not:

| Setting | Effect |
|---|---|
| `ProtectSystem=strict` | The whole filesystem is read-only, except `/run`. |
| `ReadWritePaths=/run` | Only the socket's own directory is writable. |
| `ProtectHome=yes` | The user's files are not visible at all. |
| `ProtectKernelModules=yes` | It cannot load a module. |
| `ProtectKernelTunables=yes` | It cannot change a kernel setting. |
| `PrivateNetwork=yes` | It has no network. |
| `RestrictAddressFamilies=AF_UNIX` | It can hold no other kind of socket. |
| `NoNewPrivileges=yes` | It cannot gain a privilege it did not start with. |
| `CapabilityBoundingSet=` | Five capabilities: the two DAC ones to open the files, `CAP_SYS_ADMIN` for the NVMe admin command, and `CAP_CHOWN` and `CAP_FOWNER` for the socket. |

A rule that a person must remember is weaker than a rule the machine keeps.

### 4. The client asks for the catalogue, never for a path.

The protocol has three commands: `describe`, `read` and `ping`. None of them
takes a path, a device or a file name. A field added to a request is ignored.
The helper builds its catalogue from the machine at start, and a client may
have all of it or none of it.

### 5. The socket is removed only when the helper made it.

The helper unlinks the socket path in two places: before binding, to clear one
left by a helper that died, and on close. Both check that the path **is a
socket**, and the close also checks that this process bound it.

This rule exists because the first version broke it and a test caught it.
`socketserver` calls `server_close()` when `server_bind()` raises, so a bind
that failed on an ordinary file made the root process delete that file. It is
the same shape as fault 1 of the thermal shutdown: a clean-up path that acted
without checking what it was acting on.

### 6. Without the helper, the channels are shown, not hidden.

ADR 0005 rule 3, made concrete. The catalogue is built from `name`, `model` and
`serial`, which any user can read; only the values need root. So the client
builds the same 19 channels by itself when the socket is absent, and every one
of them carries the error

    needs the helper; start it with: systemctl start sensors-guid

A hidden row hides the reason it is missing. A row with a dash and a reason
tells a person what to do.

## Consequences

- The helper depends on `nvme-cli`. If it is not installed, the 15 SMART
  channels say so and everything else still works.
- Running `nvme` costs about 3.0 ms and a process. At once a minute that is
  nothing, and it buys an audited tool in place of the project's own ioctl.
- `CAP_SYS_ADMIN` is a wide capability. It is what an NVMe admin command needs;
  it is bounded by everything in the table above.
- The helper must be reinstalled after the repository's copy changes. The
  version check turns that from a puzzle into a log line.
- A second machine would need its own `--group`. This project has one machine.
