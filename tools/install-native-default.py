#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""Promote the cold-boot-tested native files on APP, retaining a data backup.

This changes ordinary /boot files, never LNX, GPT or the factory bootloader.
Native GPU/display helpers must be installed before requesting a reboot.
"""
import argparse, hashlib, os, pathlib, shutil, subprocess, time

KERNEL_SHA='d8bc8736b124aad1ccecf097cf480d9df5be4fb9aab55bafc486e94625367e81'
DTB_SHA='11e4916155e564fb2b884be6df191288997ecbad8d7863de681884718b3fab88'
BACKLIGHT_SHA='5cb1c425c994e60cb5cb38a82a6ed946179a3fd55fa3d254bba317a4f36e1f10'
PREFIX=pathlib.Path('/srv/mocha-data/codex-debian-desktop')
NATIVE=PREFIX/'native-performance-20261011'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def atomic(path,text,mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.new');temp.write_text(text);temp.chmod(mode);temp.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    assert os.geteuid()==0
    assert subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()=='armhf'
    kernel=pathlib.Path('/boot/uImage-native-perf');dtb=pathlib.Path('/boot/mocha-native-perf.dtb')
    assert digest(kernel)==KERNEL_SHA and digest(dtb)==DTB_SHA
    assert digest(NATIVE/'mocha_miui_backlight.ko')==BACKLIGHT_SHA
    assert (NATIVE/'modules/lib/modules/6.12.111-moze.1-native').is_dir()
    assert pathlib.Path('/usr/local/libexec/mocha-tablet-current/niri').is_file()
    assert pathlib.Path('/usr/local/libexec/mocha-tablet-current/mesa/dri/tegra_dri.so').is_file()
    assert pathlib.Path('/usr/local/libexec/mocha-tablet-current/mesa/dri/nouveau_dri.so').is_file()
    assert os.stat(kernel).st_dev==os.stat('/boot/uImage-desktop').st_dev
    print('Verified cold-boot native kernel, DTB, modules and persistent desktop bundle')
    if not args.apply:return
    dropin=pathlib.Path('/etc/systemd/system/mocha-native-gpu-policy.service.d/installed-native.conf')
    assert not dropin.exists(), 'Already installed; use the existing backup rather than overwriting it'
    backup=PREFIX/'backups'/('native-default-'+time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    files=[pathlib.Path('/boot/uImage-desktop'),pathlib.Path('/boot/mocha-desktop.dtb'),NATIVE/'hardware-loader',pathlib.Path('/usr/local/libexec/mocha-backlight-candidate')]
    for path in files:
        target=backup/path.relative_to('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
    (backup/'SHA256SUMS').write_text(''.join(digest(backup/p.relative_to('/'))+'  '+str(p.relative_to('/'))+'\n' for p in files))
    atomic(NATIVE/'hardware-loader','''#!/bin/sh
set -eu
prefix=/srv/mocha-data/codex-debian-desktop
case "$(uname -r)" in
 6.12.111-moze.1-native) ;;
 *-native-runtime) echo 'Load release-matched trial modules through the trial service' >&2; exit 1 ;;
 *) exec "$prefix/native-debug4/hardware-loader" ;;
esac
candidate=$prefix/native-performance-20261011
modprobe -d "$candidate/modules" nouveau
modprobe -d "$candidate/modules" brcmfmac
udevadm settle --timeout=15
[ -d /sys/module/mocha_miui_backlight ] || insmod "$candidate/mocha_miui_backlight.ko"
''',0o755)
    atomic(pathlib.Path('/usr/local/libexec/mocha-backlight-candidate'),'''#!/bin/sh
set -eu
[ ! -d /sys/module/mocha_miui_backlight ] || exit 0
case "$(uname -r)" in
 6.12.111-moze.1-native) insmod /srv/mocha-data/codex-debian-desktop/native-performance-20261011/mocha_miui_backlight.ko ;;
 *-native-runtime) echo 'Load the release-matched trial backlight' >&2; exit 1 ;;
 *) dt=/sys/firmware/devicetree/base/i2c@7000c000/backlight@2c/compatible
    [ -f "$dt" ] || exit 0
    grep -q xiaomi,mocha-miui-lp8556 "$dt" || exit 0
    insmod /srv/mocha-data/codex-debian-desktop/hardware-service-candidate/mocha_miui_backlight.ko ;;
esac
''',0o755)
    atomic(dropin,'''[Unit]
ConditionKernelCommandLine=
[Service]
ExecCondition=/bin/sh -c 'case "$(uname -r)" in *-native*) exit 0;; *) exit 1;; esac'
''')
    # Link the verified files on the same filesystem: no second kernel copy is
    # required on the nearly full APP partition. Rename is atomic per file.
    for source,target in ((kernel,pathlib.Path('/boot/uImage-desktop')),(dtb,pathlib.Path('/boot/mocha-desktop.dtb'))):
        temp=target.with_name(target.name+'.native-new');temp.unlink(missing_ok=True)
        os.link(source,temp);temp.replace(target)
    assert digest(pathlib.Path('/boot/uImage-desktop'))==KERNEL_SHA
    assert digest(pathlib.Path('/boot/mocha-desktop.dtb'))==DTB_SHA
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','mocha-native-gpu-policy.service'],check=True)
    os.sync()
    (backup/'restore.sh').write_text('''#!/bin/sh
set -eu
backup=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$backup"
sha256sum -c SHA256SUMS
cp -a boot/uImage-desktop /boot/uImage-desktop.restore
cp -a boot/mocha-desktop.dtb /boot/mocha-desktop.dtb.restore
mv /boot/uImage-desktop.restore /boot/uImage-desktop
mv /boot/mocha-desktop.dtb.restore /boot/mocha-desktop.dtb
cp -a srv/mocha-data/codex-debian-desktop/native-performance-20261011/hardware-loader /srv/mocha-data/codex-debian-desktop/native-performance-20261011/hardware-loader
cp -a usr/local/libexec/mocha-backlight-candidate /usr/local/libexec/mocha-backlight-candidate
rm -f /etc/systemd/system/mocha-native-gpu-policy.service.d/installed-native.conf
systemctl daemon-reload
sync
''')
    print('Default native files installed. Reboot acceptance remains pending. Backup:',backup)

if __name__=='__main__':main()
