#!/usr/bin/env python3
"""Read-only, shareable Mocha hardware status, without device identities.

Does not collect command lines, MAC/CID/PARTUUID, firmware contents,
environment variables, credentials, or arbitrary journal text.
SPDX-License-Identifier: GPL-2.0-only
"""
import argparse
import gzip
import hashlib
import json
import os
import subprocess
import struct
from pathlib import Path


def read(path):
    try:
        return Path(path).read_text().replace('\0', '').strip()
    except (OSError, UnicodeError):
        return None


def digest(path):
    try:
        with open(path, 'rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    except OSError:
        return None


def command(arguments):
    try:
        result = subprocess.run(arguments, text=True, capture_output=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def build_id(path):
    try:
        data = Path(path).read_bytes()
        if data[:4] != b'\x7fELF' or data[4] not in (1, 2) or data[5] not in (1, 2):
            return None
        endian = '<' if data[5] == 1 else '>'
        if data[4] == 1:
            offset = struct.unpack_from(endian + 'I', data, 28)[0]
            size, count = struct.unpack_from(endian + 'HH', data, 42)
            entry_format = endian + 'IIIIIIII'
            file_offset, file_size = 1, 4
        else:
            offset = struct.unpack_from(endian + 'Q', data, 32)[0]
            size, count = struct.unpack_from(endian + 'HH', data, 54)
            entry_format = endian + 'IIQQQQQQ'
            file_offset, file_size = 2, 5
        for index in range(count):
            entry = struct.unpack_from(entry_format, data, offset + index * size)
            if entry[0] != 4:  # PT_NOTE
                continue
            position = entry[file_offset]
            end = position + entry[file_size]
            while position + 12 <= end:
                name_size, description_size, kind = struct.unpack_from(endian + 'III', data, position)
                position += 12
                name = data[position:position + name_size]
                position += (name_size + 3) & ~3
                description = data[position:position + description_size]
                position += (description_size + 3) & ~3
                if kind == 3 and name.rstrip(b'\0') == b'GNU':
                    return description.hex()
    except (OSError, IndexError, struct.error):
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection-date', required=True, help='date from the operator clock, YYYY-MM-DD')
    parser.add_argument('--boot-method', choices=('unknown', 'cold', 'fastboot'), default='unknown')
    args = parser.parse_args()
    from datetime import date
    date.fromisoformat(args.collection_date)
    drm = []
    for node in sorted(Path('/sys/class/drm').glob('*')):
        if not node.name.startswith(('card', 'renderD')) or '-' in node.name:
            continue
        driver_path = node / 'device/driver'
        drm.append({'node': node.name, 'driver': driver_path.resolve().name if driver_path.exists() else None})
    connectors = []
    for node in sorted(Path('/sys/class/drm').glob('card*-*')):
        connectors.append({'name': node.name, 'status': read(node / 'status'), 'modes': read(node / 'modes')})
    power = []
    for node in sorted(Path('/sys/class/power_supply').glob('*')):
        attributes = ('type', 'status', 'online', 'capacity', 'temp', 'current_now', 'voltage_now',
                      'input_current_limit', 'constant_charge_current', 'constant_charge_voltage')
        power.append({'name': node.name, **{name: read(node / name) for name in attributes}})
    thermal = [{'type': read(node / 'type'), 'temp': read(node / 'temp')}
               for node in sorted(Path('/sys/class/thermal').glob('thermal_zone*'))]
    uart = []
    for node in sorted(Path('/sys/firmware/devicetree/base').glob('serial@*')):
        if (node / 'bluetooth').exists():
            uart.append({'node': node.name, 'status': read(node / 'status'),
                         'compatible': read(node / 'bluetooth/compatible')})
    processes = []
    for entry in Path('/proc').iterdir():
        if entry.name.isdecimal():
            name = read(entry / 'comm')
            if name in ('niri', 'noctalia'):
                processes.append(name)
    filesystems = []
    for path in ('/', '/tmp', '/srv/mocha-data'):
        try:
            stat = os.statvfs(path)
            filesystems.append({'path': path, 'bytes_available': stat.f_bavail * stat.f_frsize})
        except OSError:
            pass
    config = None
    try:
        with gzip.open('/proc/config.gz', 'rt') as stream:
            data = stream.read()
        config = {name: name + '=y' in data.splitlines()
                  for name in ('CONFIG_BINFMT_ELF', 'CONFIG_COREDUMP', 'CONFIG_ELF_CORE')}
    except OSError:
        pass
    result = {
        'schema': 1, 'collection_date': args.collection_date,
        'boot_method': args.boot_method, 'kernelrelease': os.uname().release,
        'pid1': read('/proc/1/comm'), 'cpu_online': read('/sys/devices/system/cpu/online'),
        'live_fdt_sha256': digest('/sys/firmware/fdt'),
        'drm': drm, 'connectors': connectors, 'desktop_processes': sorted(processes),
        'alsa_cards': read('/proc/asound/cards'),
        'bluetooth_hci': sorted(p.name for p in Path('/sys/class/bluetooth').glob('hci*')),
        'bluetooth_uart': uart, 'power_supply': power, 'thermal': thermal,
        'filesystems': filesystems, 'core_dump_config': config,
        'mesa_packages': command(['dpkg-query', '-W', '-f=${binary:Package} ${Version}\n',
                                  'mesa-libgallium', 'libegl-mesa0']),
        'mesa_libgallium': [{'file': library.name, 'sha256': digest(library), 'build_id': build_id(library)}
                           for library in sorted(Path('/usr/lib/arm-linux-gnueabihf').glob('libgallium*.so'))],
        'failed_services': command(['systemctl', '--failed', '--no-legend', '--no-pager']),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
