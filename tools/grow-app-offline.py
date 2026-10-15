#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Migrate this 16 GB Mocha's APP to 3 GiB from an unmounted RAM session.

Requires a verified private PC backup and a separately boot-tested bridge
initramfs. Does not delete files to make space. Dry-run is the default.
On an interrupted move, keep RAM running and recover from the saved image;
never assume the old UDA remains usable after a partially overlapping copy.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time
import zlib

SIZE = 15758000128
OLD = [(26,'APP',524288,2612431),(27,'AP1',3136719,9009),
       (28,'CAC',3145728,786432),(29,'UDA',3932160,26841088)]
NEW = [(26,'APP',524288,6291456),(27,'AP1',6815744,9009),
       (28,'CAC',6825984,786432),(29,'UDA',7612416,23160832)]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_at(stream, offset, size):
    stream.seek(offset)
    result=bytearray()
    while len(result)<size:
        data=stream.read(size-len(result))
        if not data:raise RuntimeError('Short source read')
        result.extend(data)
    return bytes(result)


def write_at(stream, offset, data):
    stream.seek(offset)
    remaining=memoryview(data)
    while remaining:
        count=stream.write(remaining)
        if not count:raise RuntimeError('Short destination write')
        remaining=remaining[count:]


def move_backwards(stream, source, destination, size, checkpoint, chunk=16*1024**2):
    assert source>=0 and destination>source and size>0 and 0<chunk<=64*1024**2
    remaining=size
    while remaining:
        count=min(chunk,remaining);remaining-=count
        data=read_at(stream,source+remaining,count)
        expected=digest(data)
        write_at(stream,destination+remaining,data)
        stream.flush();os.fsync(stream.fileno())
        assert digest(read_at(stream,destination+remaining,count))==expected, 'Move readback mismatch'
        checkpoint(remaining,count,expected)


def read_gpt(stream):
    headers=[];tables=[]
    assert read_at(stream,510,2)==b'\x55\xaa'
    for lba in (1,SIZE//512-1):
        sector=read_at(stream,lba*512,512)
        fields=struct.unpack_from('<8s4I4Q16sQ3I',sector)
        assert fields[0]==b'EFI PART' and fields[1]==0x10000 and fields[2]==92 and fields[4]==0
        header=bytearray(sector[:92]);header[16:20]=b'\0'*4
        assert zlib.crc32(header)==fields[3]
        assert fields[5]==lba and fields[6]==(SIZE//512-1 if lba==1 else 1)
        assert fields[7]==4096 and fields[8]==30773247
        assert 0<fields[11]<=4096 and 128<=fields[12]<=1024
        assert fields[10]*512+fields[11]*fields[12]<=SIZE
        table=read_at(stream,fields[10]*512,fields[11]*fields[12])
        assert zlib.crc32(table)==fields[13]
        headers.append((sector,fields));tables.append(table)
    assert headers[0][1][7:10]==headers[1][1][7:10]
    assert headers[0][1][11:]==headers[1][1][11:] and tables[0]==tables[1]
    return headers,tables[0]


def partition_list(table, width):
    result=[]
    for offset in range(0,len(table),width):
        entry=table[offset:offset+width]
        if entry[:16]==b'\0'*16:continue
        start,end=struct.unpack_from('<QQ',entry,32)
        assert 4096<=start<=end<=30773247
        result.append({'number':offset//width+1,
                       'name':entry[56:128].decode('utf-16-le').rstrip('\0'),
                       'start':start,'sectors':end-start+1})
    return result


def replace_bounds(table, width, partitions):
    result=bytearray(table)
    for number,name,start,sectors in partitions:
        offset=(number-1)*width
        assert table[offset+56:offset+128].decode('utf-16-le').rstrip('\0')==name
        struct.pack_into('<QQ',result,offset+32,start,start+sectors-1)
    return bytes(result)


def replace_header_crc(sector, table):
    result=bytearray(sector)
    struct.pack_into('<I',result,88,zlib.crc32(table))
    result[16:20]=b'\0'*4
    struct.pack_into('<I',result,16,zlib.crc32(result[:92]))
    return bytes(result)


def offline():
    base=Path('/sys/class/block')
    assert os.geteuid()==0 and (base/'mmcblk0/device/name').read_text().strip()=='016GE2'
    assert int((base/'mmcblk0/size').read_text())*512==SIZE
    nodes=[p for p in base.glob('mmcblk0*') if p.is_dir()]
    numbers={(p/'dev').read_text().strip() for p in nodes}
    assert not any(line.split()[2] in numbers for line in Path('/proc/self/mountinfo').read_text().splitlines()), 'eMMC mounted'
    assert not any(list((node/'holders').iterdir()) for node in nodes), 'eMMC has holders'
    return (base/'mmcblk0/device/cid').read_text().strip()


def command(args, check=True):
    result=subprocess.run(args,env={**os.environ,'LC_ALL':'C'},capture_output=True,text=True)
    if check and result.returncode:raise RuntimeError(' '.join(args)+'\n'+result.stdout+result.stderr)
    return result


def filesystem(device):
    report=command(['dumpe2fs','-h',device]).stdout
    values=dict(line.split(':',1) for line in report.splitlines() if ':' in line)
    return {key:value.strip() for key,value in values.items()}


def fsck(device):
    result=command(['e2fsck','-f','-p',device],check=False)
    assert result.returncode in (0,1), result.stdout+result.stderr
    assert filesystem(device)['Filesystem state']=='clean'


def main():
    import fcntl
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup-evidence',required=True,type=Path)
    parser.add_argument('--expected-gpt-sha256',required=True)
    parser.add_argument('--bridge-sha256',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    assert all(re.fullmatch('[0-9a-f]{64}',value) for value in (args.expected_gpt_sha256,args.bridge_sha256))
    cid=offline()
    assert command(['blockdev','--getro','/dev/mmcblk0']).stdout.strip()=='1'
    evidence=json.loads(args.backup_evidence.read_text())
    assert evidence['verification']=='SOURCE_AND_PC_READBACK_AND_BOTH_GPT_COPIES_VERIFIED'
    assert evidence['snapshot']['cid']==cid and evidence['snapshot']['sizes']['mmcblk0']==SIZE
    assert evidence['images']['mmcblk0']['bytes']==SIZE
    assert re.fullmatch('[0-9a-f]{64}',evidence['images']['mmcblk0']['sha256'])
    assert evidence['bridge_boot_verified'] is True
    assert evidence['bridge_sha256']==args.bridge_sha256
    with open('/dev/mmcblk0','rb',buffering=0) as stream:
        headers,table=read_gpt(stream)
    assert digest(table)==args.expected_gpt_sha256
    parts=partition_list(table,headers[0][1][12])
    assert parts==evidence['partitions']
    assert [(p['number'],p['name'],p['start'],p['sectors']) for p in parts[-4:]]==OLD
    with tempfile.TemporaryDirectory(prefix='mocha-bridge-') as temporary:
        extracted=Path(temporary)/'initramfs.cpio.gz'
        command(['debugfs','-R',f'dump /boot/initramfs.cpio.gz {extracted}','/dev/mmcblk0p26'])
        assert digest(extracted.read_bytes())==args.bridge_sha256
    uda=filesystem('/dev/mmcblk0p29');app=filesystem('/dev/mmcblk0p26')
    assert int(uda['Block size'])==int(app['Block size'])==4096
    target_blocks=NEW[-1][3]*512//4096
    used=int(uda['Block count'])-int(uda['Free blocks'])
    assert used+256*1024**2//4096<target_blocks, 'UDA needs more free space; no files are deleted by this tool'
    print(json.dumps({'mode':'apply' if args.apply else 'dry-run','app_bytes':3*1024**3,
                      'uda_bytes':NEW[-1][3]*512,'uda_used_bytes':used*4096}),flush=True)
    if not args.apply:return
    state=Path('/tmp/mocha-system3g-state.json')
    assert not state.exists(), 'Previous migration state exists; inspect before any retry'
    state.write_text(json.dumps({'phase':'starting','backup_sha256':evidence['images']['mmcblk0']['sha256']}))
    targets=['/dev/mmcblk0']+[f'/dev/mmcblk0p{n}' for n in (26,27,28,29)]
    try:
        offline()
        for device in targets:command(['blockdev','--setrw',device])
        fsck('/dev/mmcblk0p29')
        command(['resize2fs','/dev/mmcblk0p29',str(target_blocks)])
        fsck('/dev/mmcblk0p29')
        uda_after=filesystem('/dev/mmcblk0p29')
        assert int(uda_after['Block count'])==target_blocks and uda_after['Filesystem UUID']==uda['Filesystem UUID']
        descriptor=os.open('/dev/mmcblk0',os.O_RDWR|os.O_SYNC)
        with os.fdopen(descriptor,'r+b',buffering=0) as stream:
            before=read_gpt(stream)
            assert before[1]==table
            for index in (3,1,2):
                number,name,start,sectors=NEW[index]
                old_start=OLD[index][2]
                last_report=[0.0]
                def checkpoint(remaining,count,sha):
                    state.write_text(json.dumps({'phase':'moving','partition':name,'remaining':remaining,
                                                 'chunk_bytes':count,'chunk_sha256':sha}))
                    now=time.monotonic()
                    if now-last_report[0]>=15 or not remaining:
                        print(f'{name}: moved and verified {1-remaining/(sectors*512):.1%}',flush=True)
                        last_report[0]=now
                move_backwards(stream,old_start*512,start*512,sectors*512,checkpoint)
            next_table=replace_bounds(table,headers[0][1][12],NEW)
            # Preserve all GUIDs, attributes, names and unchanged partitions.
            for index in (1,0):
                sector,fields=headers[index]
                write_at(stream,fields[10]*512,next_table)
                write_at(stream,fields[5]*512,replace_header_crc(sector,next_table))
                stream.flush();os.fsync(stream.fileno())
            assert read_gpt(stream)[1]==next_table
            fcntl.ioctl(stream.fileno(),0x125f)  # BLKRRPART, no mounted partitions.
        for number,name,start,sectors in NEW:
            node=Path('/sys/class/block')/f'mmcblk0p{number}'
            assert int((node/'start').read_text())==start and int((node/'size').read_text())==sectors
        fsck('/dev/mmcblk0p26')
        command(['resize2fs','/dev/mmcblk0p26'])
        fsck('/dev/mmcblk0p26');fsck('/dev/mmcblk0p29')
        app_after=filesystem('/dev/mmcblk0p26')
        assert int(app_after['Block count'])*4096==3*1024**3
        assert app_after['Filesystem UUID']==app['Filesystem UUID']
        assert filesystem('/dev/mmcblk0p29')['Filesystem UUID']==uda['Filesystem UUID']
        state.write_text(json.dumps({'phase':'complete','app_bytes':3*1024**3,'uda_bytes':NEW[-1][3]*512}))
        os.sync()
        print('SYSTEM3G_MIGRATION_AND_FILESYSTEM_CHECKS_COMPLETE',flush=True)
    finally:
        for device in reversed(targets):command(['blockdev','--setro',device],check=False)
        os.sync()


if __name__=='__main__':main()
