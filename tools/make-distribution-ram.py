#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Remove developer credentials from a verified maintenance image.

Installer public key is injected per PC run. Host key is generated in RAM on
each boot. The persistent Debian image contains neither of these keys.
"""
import argparse
import gzip
from pathlib import Path
from ram_archive import read_newc,write_newc,regular


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('maintenance',type=Path);p.add_argument('dropbearkey_armhf',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args();repo=Path(__file__).resolve().parents[1]
    if a.output.exists():p.error('Output already exists')
    keygen=a.dropbearkey_armhf.read_bytes()
    if keygen[:5]!=b'\x7fELF\x01' or int.from_bytes(keygen[18:20],'little')!=40:p.error('ARM ELF32 dropbearkey required')
    entries=read_newc(gzip.decompress(a.maintenance.read_bytes()))
    result=[];init_count=0
    for name,fields,data in entries:
        if name.startswith('etc/dropbear/') or name.endswith(('authorized_keys','known_hosts')):
            continue
        if name=='init':
            init_count+=1;text=data.decode()
            if 'STORAGE_RO' not in text or 'blockdev --setro /dev/mmcblk0' not in text:
                raise ValueError('Expected the read-only maintenance init')
            text=text.replace('/sbin/dropbear -F -E',
                ': > /etc/mocha-distribution-ram\n    /usr/bin/dropbearkey -t ecdsa -f /run/installer-host-key >/dev/null 2>&1 || exit 1\n    /sbin/dropbear -F -E')
            text=text.replace('/etc/dropbear/dropbear_ecdsa_host_key','/run/installer-host-key')
            data=text.encode()
        result.append((name,fields,data))
    if init_count!=1:raise ValueError('Maintenance init missing/duplicated')
    # Pick unique inode numbers so cpio cannot interpret additions as hardlinks.
    ino=max(fields[0] for _,fields,_ in result)+1
    additions=[('root/.ssh/authorized_keys',b'',0o100600),
               ('usr/bin/dropbearkey',keygen,0o100755)]
    for name in ('distribution-ram.py','grow-app-offline.py'):
        additions.append(('usr/local/libexec/'+name,(repo/'tools'/name).read_bytes().replace(b'\r\n',b'\n'),0o100755))
    # The maintenance image must already include these parent directories.
    parents={name for name,fields,_ in result if fields[1]&0o170000==0o040000}
    for name in ('usr/local','usr/local/libexec'):
        if name not in parents:
            result.append(regular(name,b'',0o040755,ino+len(additions)+len(parents)))
            parents.add(name)
    for index,(name,data,mode) in enumerate(additions):
        result=[entry for entry in result if entry[0]!=name]
        result.append(regular(name,data,mode,ino+index))
    a.output.write_bytes(gzip.compress(write_newc(result),compresslevel=6,mtime=0))
    print('RAM image contains an empty client-key slot and generates a fresh host key')


if __name__=='__main__':main()
