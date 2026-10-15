#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""Install an already RAM-tested Android-header U-Boot into the named LNX slot.

Dry-run first to obtain the current partition digest. Private full-slot backup,
expected old/new hashes and readback are mandatory. GPT and boot0 are untouched.
"""
import argparse, hashlib, json, os, shutil, struct, subprocess, time
from pathlib import Path

PREFIX = Path('/srv/mocha-data/codex-debian-desktop')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--expected-current-sha256')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    assert os.geteuid() == 0
    assert subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip() == 'armhf'
    image_path = args.image.resolve()
    assert image_path.is_relative_to(PREFIX)
    image = image_path.read_bytes()
    assert len(args.sha256) == 64 and digest(image) == args.sha256
    fields = struct.unpack_from('<8s10I16s', image)
    assert fields[0] == b'ANDROID!' and fields[8] == 2048
    assert fields[2] == 0x10008000 and fields[3] == fields[5] == 0
    assert fields[-1].rstrip(b'\0') == b'Mocha-Moze-UBoot'
    assert 128 * 1024 < fields[1] < 8 * 1024 * 1024
    assert len(image) == 2048 + ((fields[1] + 2047) // 2048) * 2048
    candidates = []
    for node in Path('/sys/class/block').glob('mmcblk0p*'):
        properties = dict(line.split('=', 1) for line in (node/'uevent').read_text().splitlines() if '=' in line)
        if properties.get('PARTNAME') == 'LNX':
            candidates.append((node, Path('/dev') / properties['DEVNAME']))
    assert len(candidates) == 1, 'LNX must be uniquely identified by GPT name'
    node, device = candidates[0]
    size = int((node/'size').read_text()) * 512
    assert len(image) < size <= 64 * 1024 * 1024
    major_minor = (node/'dev').read_text().strip()
    assert all(line.split()[2] != major_minor for line in Path('/proc/self/mountinfo').read_text().splitlines())
    assert not list((node/'holders').iterdir())
    capacities = [int(path.read_text()) for path in Path('/sys/class/power_supply').glob('*/capacity')]
    assert capacities and min(capacities) >= 40
    original = device.read_bytes()
    assert len(original) == size and original[:8] == b'ANDROID!'
    original_hash = digest(original)
    print(json.dumps({'partition': node.name, 'bytes': size, 'current_sha256': original_hash,
                      'image_sha256': digest(image), 'apply': args.apply}), flush=True)
    if not args.apply:
        return
    assert args.expected_current_sha256 == original_hash, 'Partition changed since reviewed dry-run'
    assert shutil.disk_usage(PREFIX).free > size + 4 * 1024 * 1024
    backup = PREFIX/'backups'/('lnx-default-'+time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(mode=0o700)
    saved = backup/'LNX.bin'
    with saved.open('xb') as stream:
        stream.write(original); stream.flush(); os.fsync(stream.fileno())
    saved.chmod(0o600)
    assert digest(saved.read_bytes()) == original_hash
    expected = digest(image + original[len(image):])
    (backup/'metadata.json').write_text(json.dumps({'partition': node.name, 'bytes': size,
        'original_sha256': original_hash, 'image_sha256': digest(image),
        'expected_partition_sha256': expected}, indent=2)+'\n')
    (backup/'restore.py').write_text('''#!/usr/bin/python3
from pathlib import Path
import hashlib,json,os
base=Path(__file__).resolve().parent
meta=json.loads((base/'metadata.json').read_text())
node=Path('/sys/class/block')/meta['partition']
assert os.geteuid()==0 and node.name.startswith('mmcblk0p')
assert 'PARTNAME=LNX' in (node/'uevent').read_text().splitlines()
assert int((node/'size').read_text())*512==meta['bytes']
assert all(line.split()[2]!=(node/'dev').read_text().strip() for line in Path('/proc/self/mountinfo').read_text().splitlines())
assert not list((node/'holders').iterdir())
original=(base/'LNX.bin').read_bytes()
assert len(original)==meta['bytes'] and hashlib.sha256(original).hexdigest()==meta['original_sha256']
device=Path('/dev')/node.name
with os.fdopen(os.open(device,os.O_RDWR|os.O_SYNC),'r+b',buffering=0) as stream:
 assert hashlib.sha256(stream.read()).hexdigest()==meta['expected_partition_sha256']
 stream.seek(0);view=memoryview(original)
 while view:
  count=stream.write(view);assert count and count>0;view=view[count:]
 os.fsync(stream.fileno());stream.seek(0)
 assert hashlib.sha256(stream.read()).hexdigest()==meta['original_sha256']
os.sync()
print('Original LNX restored and verified')
''')
    os.sync()
    descriptor = os.open(device, os.O_RDWR | os.O_SYNC)
    try:
        with os.fdopen(descriptor, 'r+b', buffering=0) as stream:
            assert digest(stream.read()) == original_hash
            stream.seek(0)
            view = memoryview(image)
            while view:
                count = stream.write(view)
                assert count and count > 0
                view = view[count:]
            os.fsync(stream.fileno())
            stream.seek(0)
            assert digest(stream.read()) == expected, 'Readback mismatch; keep backup and do not reboot'
    except Exception:
        print('INSTALL_FAILED_BACKUP', backup, flush=True)
        raise
    os.sync()
    print('LNX_INSTALLED_READBACK_VERIFIED', backup, flush=True)

if __name__ == '__main__':
    main()
