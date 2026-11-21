#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build a private candidate distribution from an offline APP/UDA snapshot.

Existing images and source filesystems are never modified. Production status
is intentionally NOT assigned by this builder; physical acceptance is separate.
"""
import argparse
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def run(*args):return subprocess.run(args,check=True)


def check_build_tools():
    """Fail before copying snapshots or creating any build output."""
    commands=('rsync','tar','xz','bash','python3','dpkg-query','openssl',
              'truncate','mkfs.ext4','e2fsck')
    missing=[name for name in commands if shutil.which(name) is None]
    if missing:
        raise RuntimeError('Build host missing required tools: '+', '.join(missing))


DATA_BLOCK=4096
DATA_MARGIN_MIN=64*1024**2
DATA_MARGIN_PCT=3
DATA_SAFETY_BYTES=256*1024**2
UDA_RESERVE_DEN=8  # fixed 12.5% for ext4 metadata, journal and reserved blocks


def expanded_estimate(tree):
    """Estimate extracted DATA footprint: block-rounded sizes, dir/inode overhead,
    hardlink-deduplicated, plus a conservative margin."""
    unique={};base=0;dirs=0;symlinks=0
    for path in Path(tree).rglob('*'):
        if path.is_symlink():symlinks+=1;continue
        if path.is_dir():dirs+=1;continue
        if not path.is_file():continue
        stat=path.stat();key=(stat.st_dev,stat.st_ino)
        if stat.st_nlink>1:
            if key in unique:
                base+=DATA_BLOCK  # a second name still consumes directory space
                continue
            unique[key]=stat.st_size
        base+=((stat.st_size+DATA_BLOCK-1)//DATA_BLOCK)*DATA_BLOCK+DATA_BLOCK
    base+=dirs*DATA_BLOCK+symlinks*DATA_BLOCK
    margin=max(DATA_MARGIN_MIN,base*DATA_MARGIN_PCT//100)
    return base,margin


def uda_bytes():
    """Fixed UDA partition size from the validated 3 GiB APP layout."""
    spec=importlib.util.spec_from_file_location('mocha_layout',Path(__file__).with_name('grow-app-offline.py'))
    if spec is None or spec.loader is None:raise RuntimeError('layout module unavailable')
    layout=importlib.util.module_from_spec(spec);spec.loader.exec_module(layout)
    uda=next((sectors*512 for number,name,start,sectors in layout.NEW if name=='UDA'),None)
    if uda is None:raise RuntimeError('layout has no UDA partition')
    return uda


def capacity_plan(archive_bytes,expanded_bytes,uda=None):
    """Check the true peak (archive + extracted tree) against the fixed UDA."""
    uda=uda_bytes() if uda is None else uda
    usable=uda-uda//UDA_RESERVE_DEN
    required=archive_bytes+expanded_bytes+DATA_SAFETY_BYTES
    if required>usable:
        raise RuntimeError('DATA peak exceeds fixed UDA: archive='+str(archive_bytes)+
            ' expanded='+str(expanded_bytes)+' required='+str(required)+' usable='+str(usable))
    return {'uda_bytes':uda,'uda_reserve_bytes':uda//UDA_RESERVE_DEN,'uda_usable_bytes':usable,
            'data_archive_bytes':archive_bytes,'data_expanded_bytes':expanded_bytes,
            'data_safety_bytes':DATA_SAFETY_BYTES,
            'capacity_required_bytes':required,'capacity_margin_bytes':usable-required}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--app-copy',type=Path,required=True)
    p.add_argument('--data-copy',type=Path,required=True)
    p.add_argument('--offline-evidence',type=Path,required=True)
    p.add_argument('--loader',type=Path,required=True)
    p.add_argument('--ram-kernel',type=Path,required=True)
    p.add_argument('--ram-dtb',type=Path,required=True)
    p.add_argument('--installer',type=Path,required=True)
    p.add_argument('--lnx',type=Path,required=True,help='clean built Android-wrapped U-Boot, never a raw partition backup')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--version',default='2026.10-candidate')
    a=p.parse_args()
    if os.geteuid()!=0:p.error('Linux root required for ext4/xattrs/ownership')
    check_build_tools()
    evidence=json.loads(a.offline_evidence.read_text())
    if evidence.get('capture')!='offline-readonly-app-uda' or evidence.get('root_partition_bytes')!=3*1024**3:
        p.error('A fresh offline snapshot with a 3 GiB APP is required')
    repo=Path(__file__).resolve().parents[1]
    output=a.output.resolve()
    if output.exists():p.error('Output must be a new directory')
    for source in (a.app_copy,a.data_copy):
        if source.resolve()==Path('/') or source.resolve().is_relative_to(output) or output.is_relative_to(source.resolve()):
            p.error('Staging/output must be disjoint from source filesystems')
    if shutil.disk_usage(output.parent).free<20*1024**3:p.error('At least 20 GiB build space required')
    if a.lnx.stat().st_size>8*1024**2 or a.lnx.read_bytes()[:8]!=b'ANDROID!':
        p.error('LNX must be a clean built Android boot container smaller than 8 MiB')
    output.mkdir(mode=0o700)
    work=output/'private-work';work.mkdir(mode=0o700)
    root=work/'APP';data=work/'DATA';root.mkdir();data.mkdir()
    run('rsync','-aHAX','--numeric-ids','--one-file-system',str(a.app_copy.resolve())+'/',str(root)+'/')
    run('rsync','-aHAX','--numeric-ids','--one-file-system',
        '--exclude=backups/','--exclude=llm-models/','--exclude=mocha-llm*/',
        str(a.data_copy.resolve())+'/',str(data)+'/')
    (root/'.mocha-export-copy').write_text('OFFLINE_COPY_NOT_LIVE\n')
    run('python3',str(repo/'tools/prepare-distribution.py'),'--root',str(root),'--data',str(data))
    required=('gstreamer1.0-gl','gstreamer1.0-plugins-good',
              'gstreamer1.0-plugins-bad','python3-gi','locales','openssl',
              'openssh-client','passwd','sudo','polkitd','network-manager',
              'bluez','tzdata','systemd')
    for package in required:
        status=subprocess.run(['dpkg-query','--admindir='+str(root/'var/lib/dpkg'),
                               '-W','-f=${Status}',package],capture_output=True,text=True)
        if status.returncode or status.stdout.strip()!='install ok installed':
            raise RuntimeError('Missing desktop runtime dependency in source copy: '+package)
    # The snapshot must carry the known lightweight hardware-decodable variant.
    if not any(data.rglob('ymcymcymc-vde-cavlc-gop30-1536w-30fps.mp4')):
        raise RuntimeError('Required GOP30 wallpaper missing; original is deliberately excluded')
    if any(path.is_file() and path.suffix.lower() in ('.gguf','.safetensors') for tree in (root,data) for path in tree.rglob('*')):
        raise RuntimeError('Model weights remain in staging')
    private_profile_files={'sessionstore.jsonlz4','recovery.jsonlz4','recovery.baklz4',
                           'cookies.sqlite','places.sqlite','key4.db','logins.json'}
    if any(path.is_file() and path.name in private_profile_files
           for tree in (root,data) for path in tree.rglob('*')):
        raise RuntimeError('Browser profile data remains in distribution staging')
    data_bytes=sum(path.stat().st_size for path in data.rglob('*') if path.is_file() and not path.is_symlink())
    if not (root/'usr/local/bin/niri').exists() and not (root/'usr/local/bin/niri').is_symlink():
        raise RuntimeError('Packaged Niri entrypoint missing')
    image=output/'image';image.mkdir()
    app_image=work/'APP.img'
    run('bash',str(repo/'tools/make-app-image.sh'),str(root),str(app_image),str(3*1024**3))
    raw_sha=digest(app_image)
    with app_image.open('rb') as source,lzma.open(image/'APP.img.xz','wb',preset=6) as target:
        shutil.copyfileobj(source,target,length=1024*1024)
    finish_candidate(a,repo,output,raw_sha,data_bytes)


def finish_candidate(a,repo,output,raw_sha,data_bytes):
    data=output/'private-work/DATA'
    image=output/'image'
    # Bound compression memory independently of the CPU count exposed by Docker.
    run('tar','--create','--use-compress-program=xz -T2 -3','--file',str(image/'DATA.tar.xz'),'--directory',str(data),
        '--numeric-owner','--xattrs','--acls','.')
    archive_bytes=(image/'DATA.tar.xz').stat().st_size
    expanded_base,expanded_margin=expanded_estimate(data)
    expanded_bytes=expanded_base+expanded_margin
    capacity=capacity_plan(archive_bytes,expanded_bytes)
    for name,source in [('loader.img',a.loader),('uImage',a.ram_kernel),('mocha.dtb',a.ram_dtb),
                        ('installer.cpio.gz',a.installer),('LNX.img',a.lnx)]:
        shutil.copy2(source,image/name)
    files={path.name:{'bytes':path.stat().st_size,'sha256':digest(path)} for path in image.iterdir()}
    manifest={'schema':1,'version':a.version,'device':'xiaomi-mocha-16gb','app_bytes':3*1024**3,
        'release_state':'candidate','app_raw_sha256':raw_sha,'files':files,
        'data_source_bytes':data_bytes,'data_expanded_base_bytes':expanded_base,
        'data_expanded_margin_bytes':expanded_margin,**capacity,
        'includes_models':False,'first_boot':'desktop-autologin',
        'default_username':'mocha','default_password':'mocha',
        'acceptance_required':['fresh-device-layout','desktop-login','change-default-password',
                               'lock-unlock','audio-bluetooth','wallpaper-decode','reboot']}
    (image/'bundle.json').write_text(json.dumps(manifest,indent=2)+'\n')
    tools=output/'tools';tools.mkdir()
    for name in ('flash-distribution.py','ram_archive.py','Install-Mocha.cmd'):
        shutil.copy2(repo/'tools'/name,tools/name)
    shutil.copy2(repo/'docs/DISTRIBUTION.md',output/'README.md')
    shutil.copy2(repo/'LICENSE',output/'LICENSE')
    print('Private candidate created at',output)
    print('Not release-ready: inspect sanitized contents and perform the acceptance gate before publishing.')


if __name__=='__main__':main()
