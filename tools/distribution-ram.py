#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""Destructive installer endpoint, ONLY in the authenticated offline RAM image.

Stock boot/calibration partitions 1-25 are retained except LNX (22), written
last. Supports only the validated 16 GB 016GE2 geometry, never guessed sizes.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

spec=importlib.util.spec_from_file_location('layout',Path(__file__).with_name('grow-app-offline.py'))
layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
DISK='/dev/mmcblk0'
APP='/dev/mmcblk0p26'
UDA='/dev/mmcblk0p29'
STATE=Path('/run/mocha-install-state.json')
DATA_MOUNT=Path('/mnt/mocha-install-data')
DATA_SAFETY_BYTES=256*1024**2
MAX_DATA_BYTES=16*1024**3


def validate_expanded_bytes(value):
    if type(value) is not int or not 0<value<MAX_DATA_BYTES:
        raise ValueError('Invalid expanded data budget')
    return value


def required_data_space(archive_bytes,expanded_bytes):
    return archive_bytes+validate_expanded_bytes(expanded_bytes)+DATA_SAFETY_BYTES


def check_data_space(available,archive_bytes,expanded_bytes):
    required=required_data_space(archive_bytes,expanded_bytes)
    if available<required:
        raise RuntimeError('Insufficient UDA space: available='+str(available)+
            ' required='+str(required)+' (archive='+str(archive_bytes)+
            ' expanded='+str(expanded_bytes)+' safety='+str(DATA_SAFETY_BYTES)+')')
    return required


def run(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True)


def guard():
    if os.geteuid()!=0 or not Path('/etc/mocha-distribution-ram').is_file():
        raise RuntimeError('Distribution RAM environment required')
    if 'rdinit=/init' not in Path('/proc/cmdline').read_text().split():
        raise RuntimeError('RAM boot argument missing')
    return layout.offline()


def plan():
    cid=guard()
    if 'GNU tar' not in run('tar','--version').stdout:
        raise RuntimeError('GNU tar with xattrs/ACL support required before any writes')
    run('xz','--version')
    with open(DISK,'rb',buffering=0) as disk:
        headers,table=layout.read_gpt(disk)
    parts=layout.partition_list(table,headers[0][1][12])
    bounds=[(p['number'],p['name'],p['start'],p['sectors']) for p in parts[-4:]]
    if bounds not in (layout.OLD,layout.NEW):
        raise RuntimeError('Unsupported GPT layout; no writes made')
    lnx=next(p for p in parts if p['number']==22)
    if (lnx['name'],lnx['start'],lnx['sectors'])!=('LNX',393216,40960):
        raise RuntimeError('Unexpected LNX geometry')
    if any(p['start']+p['sectors']>524288 for p in parts if p['number']<=25):
        raise RuntimeError('Protected partitions overlap the target system')
    return {'cid':cid,'disk_bytes':layout.SIZE,'gpt_sha256':layout.digest(table),
            'partitions':parts,'target':layout.NEW,'app_bytes':3*1024**3}


def writable():
    run('blockdev','--setrw',DISK)
    for number in (22,26,27,28,29):run('blockdev','--setrw',DISK+'p'+str(number))


def readonly():
    for number in (22,26,27,28,29):
        subprocess.run(['blockdev','--setro',DISK+'p'+str(number)],capture_output=True)
    subprocess.run(['blockdev','--setro',DISK],capture_output=True)


def prepare(args):
    current=plan()
    if args.erase!='ERASE_APP_UDA' or current['gpt_sha256']!=args.gpt_sha256 or current['cid']!=args.cid:
        raise RuntimeError('Device identity/GPT/erase acknowledgement mismatch')
    if STATE.exists():raise RuntimeError('Install state already exists; inspect before retry')
    STATE.write_text(json.dumps({'phase':'preparing','cid':args.cid}))
    writable()
    try:
        with open(DISK,'r+b',buffering=0) as disk:
            headers,table=layout.read_gpt(disk)
            revised=layout.replace_bounds(table,headers[0][1][12],layout.NEW)
            changed=revised!=table
            if changed:
                for index in (1,0):
                    sector,fields=headers[index]
                    layout.write_at(disk,fields[10]*512,revised)
                    layout.write_at(disk,fields[5]*512,layout.replace_header_crc(sector,revised))
                    disk.flush();os.fsync(disk.fileno())
                if layout.read_gpt(disk)[1]!=revised:raise RuntimeError('GPT readback mismatch')
                fcntl.ioctl(disk.fileno(),0x125f)
        for n,name,start,count in layout.NEW:
            node=Path('/sys/class/block')/f'mmcblk0p{n}'
            if (int((node/'start').read_text()),int((node/'size').read_text()))!=(start,count):
                raise RuntimeError('Kernel partition reread mismatch')
        # APP is restored as an exact 3 GiB ext4 image in the next phase.
        for number,label in ((28,'mocha-cache'),(29,'mocha-data')):
            run('mkfs.ext4','-F','-L',label,'-O','^64bit,^metadata_csum,^orphan_file',DISK+'p'+str(number))
        if changed:
            with open(DISK+'p27','r+b',buffering=0) as disk:
                layout.write_at(disk,0,b'\0'*(9009*512));os.fsync(disk.fileno())
        STATE.write_text(json.dumps({'phase':'prepared','cid':args.cid}))
    finally:readonly()
    print('GPT_AND_DATA_FORMAT_VERIFIED')


def stream_write(device,size,expected):
    sha=hashlib.sha256();remaining=size
    with open(device,'r+b',buffering=0) as output:
        while remaining:
            data=sys.stdin.buffer.read(min(1024*1024,remaining))
            if not data:raise RuntimeError('Short image stream; leave device in RAM for recovery')
            layout.write_at(output,size-remaining,data);sha.update(data);remaining-=len(data)
        if sys.stdin.buffer.read(1):raise RuntimeError('Oversize image stream')
        output.flush();os.fsync(output.fileno())
    if sha.hexdigest()!=expected:raise RuntimeError('Source image checksum mismatch')
    with open(device,'rb',buffering=0) as stream:
        actual=hashlib.sha256();remaining=size
        while remaining:
            data=stream.read(min(1024*1024,remaining))
            if not data:raise RuntimeError('Short readback')
            actual.update(data);remaining-=len(data)
    if actual.hexdigest()!=expected:raise RuntimeError('Written image readback mismatch')


def write_app(args):
    guard()
    if json.loads(STATE.read_text())['phase']!='prepared':raise RuntimeError('Prepare phase required')
    writable()
    try:stream_write(APP,3*1024**3,args.sha256)
    finally:readonly()
    state=json.loads(STATE.read_text());state['phase']='app-verified';STATE.write_text(json.dumps(state))
    print('APP_3G_READBACK_VERIFIED')


def restore_data(args):
    guard()
    if json.loads(STATE.read_text())['phase']!='app-verified':raise RuntimeError('APP verification required')
    validate_expanded_bytes(getattr(args,'expanded_bytes',None))
    target=DATA_MOUNT;target.mkdir(parents=True,exist_ok=True)
    writable();mounted=False
    try:
        run('mount','-t','ext4',UDA,str(target));mounted=True
        usage=os.statvfs(target)
        check_data_space(usage.f_bavail*usage.f_frsize,args.bytes,args.expanded_bytes)
        archive=target/'.distribution-data.tar.xz'
        sha=hashlib.sha256();remaining=args.bytes
        with archive.open('xb') as stream:
            while remaining:
                data=sys.stdin.buffer.read(min(1024*1024,remaining))
                if not data:raise RuntimeError('Short data archive')
                stream.write(data);sha.update(data);remaining-=len(data)
            stream.flush();os.fsync(stream.fileno())
        if sys.stdin.buffer.read(1) or sha.hexdigest()!=args.sha256:
            raise RuntimeError('Data archive checksum mismatch')
        run('tar','--extract','--xz','--file',str(archive),'--directory',str(target),
            '--numeric-owner','--same-owner','--same-permissions','--xattrs','--xattrs-include=*','--acls')
        archive.unlink();os.sync()
    finally:
        if mounted:run('umount',str(target))
        readonly()
    state=json.loads(STATE.read_text());state['phase']='data-verified';STATE.write_text(json.dumps(state))
    print('DATA_RESTORED_AND_SYNCED')


def provision_wifi_nvram(root):
    """Give this installation a stable local MAC without shipping the donor MAC."""
    path=root/'usr/lib/firmware/brcm/brcmfmac4354-sdio.nvidia,mocha.txt'
    if not path.is_file() or path.is_symlink():
        raise RuntimeError('Mocha BCM4354 board NVRAM is missing')
    original=path.read_bytes()
    values=re.findall(rb'(?m)^macaddr=([^\r\n]*)',original)
    if values:
        if len(values)!=1 or not re.fullmatch(rb'02(?::[a-f0-9]{2}){5}',values[0]):
            raise RuntimeError('Unexpected MAC in the distribution NVRAM')
        return
    mac=b'02:'+os.urandom(5).hex(':').encode('ascii')
    fd,name=tempfile.mkstemp(prefix='.mocha-nvram-',dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(fd,'wb') as stream:
            os.fchmod(stream.fileno(),0o644)
            stream.write(original.rstrip()+b'\nmacaddr='+mac+b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def finalize(args):
    guard()
    if json.loads(STATE.read_text())['phase']!='data-verified':raise RuntimeError('Data restore required')
    if not 0<args.bytes<=40960*512:raise RuntimeError('Invalid LNX size')
    # Fail closed before changing the default boot image.
    mount=Path('/mnt/mocha-install-app');mount.mkdir(parents=True,exist_ok=True)
    run('mount','-o','ro,noload',APP,str(mount))
    try:
        for name in ('etc/mocha-internal-debian','etc/mocha/default-login.json','boot/uImage-desktop','boot/mocha-desktop.dtb','boot/initramfs.cpio.gz'):
            if not (mount/name).is_file():raise RuntimeError('Incomplete root image: '+name)
        login=json.loads((mount/'etc/mocha/default-login.json').read_text())
        if login.get('schema')!=1 or login.get('username')!='mocha':
            raise RuntimeError('Unexpected default desktop account')
        if (mount/'var/lib/mocha-oobe/pending').exists():
            raise RuntimeError('Stale first-run gate in root image')
    finally:run('umount',str(mount))
    writable()
    try:
        # The base APP hash has already been verified. Personalize the
        # board NVRAM before the first real boot can probe brcmfmac.
        run('mount','-t','ext4',APP,str(mount))
        try:
            provision_wifi_nvram(mount)
        finally:
            run('umount',str(mount))
        print('WIFI_NVRAM_PERSONALIZED',flush=True)
        stream_write(DISK+'p22',args.bytes,args.sha256)
    finally:readonly()
    state=json.loads(STATE.read_text());state['phase']='complete';STATE.write_text(json.dumps(state))
    os.sync();print('INSTALL_COMPLETE_REBOOT_TO_DESKTOP',flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('plan','prepare','write-app','restore-data','finalize'))
    p.add_argument('--cid');p.add_argument('--gpt-sha256');p.add_argument('--erase')
    p.add_argument('--sha256');p.add_argument('--bytes',type=int);p.add_argument('--expanded-bytes',type=int)
    a=p.parse_args()
    if a.action in ('write-app','restore-data','finalize'):
        if not re.fullmatch('[a-f0-9]{64}',a.sha256 or ''):p.error('SHA256 required')
    if a.action in ('restore-data','finalize') and not 0<(a.bytes or 0)<MAX_DATA_BYTES:p.error('Invalid size')
    if a.action=='restore-data':
        try:validate_expanded_bytes(a.expanded_bytes)
        except ValueError as error:p.error(str(error))
    if a.action=='plan':print(json.dumps(plan()))
    else:globals()[a.action.replace('-','_')](a)


if __name__=='__main__':main()
