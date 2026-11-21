#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""ExecStop: wait for this service's OOBE compositor before client cleanup."""
import os
from pathlib import Path
import select
import signal
import subprocess
import sys

PROC = Path('/proc')
CGROUP = Path('/sys/fs/cgroup')
CONFIG = b'/etc/mocha/oobe.kdl'


def service_group(unit='mocha-oobe-session.service'):
    """Use MainPID's scope: PAMName=login can move it into a logind scope."""
    pid = int(subprocess.check_output([
        'systemctl', 'show', unit,
        '--property=MainPID', '--value'], text=True, timeout=5).strip())
    if pid <= 1:
        raise RuntimeError('cannot identify the active OOBE session leader')
    for line in (PROC/str(pid)/'cgroup').read_text().splitlines():
        if line.startswith('0::'):
            relative = line[3:]
            if not relative.startswith('/') or relative == '/' or '..' in relative.split('/'):
                raise RuntimeError('refusing an unscoped OOBE stop')
            return CGROUP/relative.lstrip('/')
    raise RuntimeError('OOBE stop requires unified cgroup v2')


def compositor_fds(group):
    """Pin each matching process before checking its identity to avoid PID reuse."""
    handles = []
    try:
        for members in sorted(set([group/'cgroup.procs', *group.glob('**/cgroup.procs')])):
            try:
                pids = members.read_text().split()
            except FileNotFoundError:
                continue
            for value in pids:
                pid = int(value)
                try:
                    fd = os.pidfd_open(pid)
                except ProcessLookupError:
                    continue
                try:
                    process = PROC/str(pid)
                    executable = (process/'exe').resolve(strict=True)
                    args = (process/'cmdline').read_bytes().split(b'\0')
                    if executable.name != 'niri':
                        os.close(fd)
                        continue
                    if not any(a == b'--config' and b == CONFIG for a, b in zip(args, args[1:])):
                        raise RuntimeError('unexpected niri configuration in OOBE cgroup')
                except FileNotFoundError:
                    os.close(fd)
                    continue
                except BaseException:
                    os.close(fd)
                    raise
                handles.append(fd)
        return handles
    except BaseException:
        for fd in handles:
            os.close(fd)
        raise


def stop_compositors(group):
    handles = compositor_fds(group)
    try:
        # Only the dedicated compositor is signalled here. systemd cleans up
        # dbus and the retained welcome client after ExecStop returns.
        for fd in handles:
            try:
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for fd in handles:
            if not select.select([fd], [], [], 10)[0]:
                raise RuntimeError('OOBE compositor did not exit before cleanup')
        print(f'OOBE compositor exit confirmed ({len(handles)} process(es))', flush=True)
    finally:
        for fd in handles:
            os.close(fd)


if __name__ == '__main__':
    stop_compositors(service_group(sys.argv[1] if len(sys.argv) > 1 else 'mocha-oobe-session.service'))
