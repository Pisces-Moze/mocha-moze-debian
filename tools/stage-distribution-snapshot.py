#!/usr/bin/env python3
"""Stage private archives made by the Mocha offline capture workflow."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path, help='Private capture directory')
    parser.add_argument('output', type=Path, help='New Linux staging directory')
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0:
        parser.error('Linux root required to restore ownership and xattrs')

    source = args.capture.resolve()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        parser.error('Use a new output directory disjoint from the capture')
    manifest = source/'snapshot.json'
    evidence = json.loads(manifest.read_text(encoding='utf-8'))
    if (evidence.get('capture') != 'offline-readonly-app-uda' or
            evidence.get('root_partition_bytes') != 3*1024**3 or
            set(evidence.get('archives', {})) != {'APP', 'UDA'}):
        parser.error('A verified 3 GiB APP offline capture is required')
    capacity = sum(evidence['source']['partitions'][name]['sectors']*512 for name in ('APP', 'UDA'))
    if shutil.disk_usage(output.parent).free < capacity + 1024**3:
        parser.error('Insufficient space to expand APP and UDA')

    partial = Path(tempfile.mkdtemp(prefix=output.name+'.partial-', dir=output.parent))
    for name, target in (('APP', 'APP'), ('UDA', 'DATA')):
        archive = source/(name+'.tar')
        record = evidence['archives'][name]
        if archive.is_symlink() or not archive.is_file() or archive.stat().st_size != record['bytes']:
            raise RuntimeError(f'{name} archive size or type does not match capture')
        folder = partial/target
        folder.mkdir()
        with archive.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != record['sha256']:
                raise RuntimeError(f'{name} archive hash mismatch')
            stream.seek(0)
            command = ['tar', '--extract', '--file=-', '--directory', str(folder),
                       '--numeric-owner', '--same-owner', '--same-permissions',
                       '--acls', '--xattrs', '--xattrs-include=*',
                       '--xattrs-exclude=security.selinux']
            if name == 'UDA':
                # The separate private archive retains legacy Android data.
                # The Debian build needs only its own data subtree.
                command += ['--', './codex-debian-desktop']
            subprocess.run(command, stdin=stream, check=True)
        print('Verified and staged', name, flush=True)
    shutil.copyfile(manifest, partial/'snapshot.json')
    partial.rename(output)
    print('Private build inputs staged at', output)


if __name__ == '__main__':
    main()
