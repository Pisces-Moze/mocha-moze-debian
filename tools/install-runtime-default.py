#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""Install the RAM-tested runtime kernel and matched hardware helpers on APP.

Existing desktop/user data stay in place. A backup restores the previous boot
files and service helpers. This tool does not write the LNX or GPT partitions.
"""
import argparse,gzip,hashlib,json,os,pwd,shutil,subprocess,time
from pathlib import Path

RELEASE='6.12.111-moze.1-native-runtime'
PREFIX=Path('/srv/mocha-data/codex-debian-desktop')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def atomic(path,data,mode=0o644):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.runtime-new')
    with temp.open('wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    temp.chmod(mode);temp.replace(path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--uimage-sha256',required=True)
    parser.add_argument('--dtb-sha256',required=True)
    parser.add_argument('--backlight-sha256',required=True)
    parser.add_argument('--policy',type=Path,required=True)
    parser.add_argument('--policy-unit',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    assert os.geteuid()==0 and os.uname().release==RELEASE
    assert subprocess.check_output(['dpkg','--print-architecture'],text=True).strip()=='armhf'
    bundle=args.bundle.resolve()
    assert bundle.is_relative_to(PREFIX) and bundle.is_dir()
    for filename,value in (('uImage',args.uimage_sha256),('mocha.dtb',args.dtb_sha256),('mocha_miui_backlight.ko',args.backlight_sha256)):
        assert len(value)==64 and digest(bundle/filename)==value,filename
    subprocess.run(['sha256sum','--quiet','-c','SHA256SUMS'],cwd=bundle,check=True)
    config=gzip.decompress(Path('/proc/config.gz').read_bytes()).decode()
    assert 'CONFIG_CMDLINE="cpuidle.off=1"' in config and 'CONFIG_CMDLINE_EXTEND=y' in config
    assert 'cpuidle.off=1' in Path('/proc/cmdline').read_text().split()
    assert Path('/sys/firmware/devicetree/base/mmc@700b0000/keep-power-in-suspend').exists()
    assert (bundle/f'modules/lib/modules/{RELEASE}').is_dir()
    assert Path('/usr/local/libexec/mocha-tablet-current/niri').is_file()
    node=Path('/sys/devices/system/cpu/cpufreq/policy0')
    request=int((node/'scaling_cur_freq').read_text())*1000
    measured=int(Path('/sys/kernel/debug/tegra_dfll_fcpu/rate').read_text())
    assert request>0 and abs(request-measured)<=max(25500000,request//10)
    assert shutil.disk_usage('/boot').free>(bundle/'uImage').stat().st_size+2*1024*1024
    print('Verified running runtime profile, SDIO capability, DFLL feedback and bundle hashes')
    if not args.apply:return
    override=Path('/etc/systemd/system/mocha-desktop-hardware.service.d/zzz-installed-runtime.conf')
    assert not override.exists(),'Already installed; use the recorded backup'
    backup=PREFIX/'backups'/('runtime-default-'+time.strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True)
    user=pwd.getpwnam('mocha')
    preferences=Path(user.pw_dir)/'.config/mocha/runtime.json'
    targets=[Path('/boot/uImage-desktop'),Path('/boot/mocha-desktop.dtb'),
             Path('/usr/local/libexec/mocha-backlight-candidate'),
             Path('/usr/local/libexec/mocha-runtime-hardware'),override,
             Path('/usr/local/libexec/mocha-runtime-policy.py'),
             Path('/etc/systemd/system/mocha-runtime-policy.service'),preferences]
    record=[]
    modules=Path('/lib/modules')/RELEASE
    assert modules.is_symlink()
    record.append({'path':str(modules),'exists':True,'symlink':str(modules.readlink())})
    for target in targets:
        exists=target.exists() or target.is_symlink()
        entry={'path':str(target),'exists':exists}
        if exists:
            saved=backup/target.relative_to('/')
            saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,saved)
            entry.update(sha256=digest(saved),mode=target.stat().st_mode&0o777,
                         uid=target.stat().st_uid,gid=target.stat().st_gid)
        record.append(entry)
    atomic(backup/'files.json',(json.dumps(record,indent=2)+'\n').encode())
    atomic(backup/'restore.py',('''#!/usr/bin/python3
from pathlib import Path
import hashlib,json,os,shutil,subprocess
base=Path(__file__).resolve().parent
for item in json.loads((base/'files.json').read_text()):
 target=Path(item['path'])
 if 'symlink' in item:
  temporary=target.with_name(target.name+'.restore')
  temporary.unlink(missing_ok=True);temporary.symlink_to(item['symlink']);temporary.replace(target)
  continue
 if item['exists']:
  source=base/target.relative_to('/')
  assert hashlib.sha256(source.read_bytes()).hexdigest()==item['sha256']
  temporary=target.with_name(target.name+'.restore')
  shutil.copy2(source,temporary);temporary.chmod(item['mode'])
  os.chown(temporary,item['uid'],item['gid']);temporary.replace(target)
 else:target.unlink(missing_ok=True)
subprocess.run(['systemctl','disable','mocha-runtime-policy.service'],check=False)
subprocess.run(['systemctl','daemon-reload'],check=True)
os.sync()
print('Previous default restored; reboot is needed to run it')
''').encode(),0o755)
    # The current framebuffer needs only backlight in the charging target.
    old_backlight=backup/'usr/local/libexec/mocha-backlight-candidate'
    atomic(Path('/usr/local/libexec/mocha-backlight-candidate'),f'''#!/bin/sh
set -eu
case "$(uname -r)" in
 {RELEASE}) [ -d /sys/module/mocha_miui_backlight ] || insmod {bundle}/mocha_miui_backlight.ko ;;
 *) exec {old_backlight} ;;
esac
'''.encode(),0o755)
    atomic(Path('/usr/local/libexec/mocha-runtime-hardware'),f'''#!/bin/sh
set -eu
case "$(uname -r)" in
 {RELEASE}) modprobe -d {bundle}/modules nouveau
              modprobe -d {bundle}/modules brcmfmac
              /usr/local/libexec/mocha-backlight-candidate ;;
 *) exec {PREFIX}/native-performance-20261011/hardware-loader ;;
esac
'''.encode(),0o755)
    atomic(override,b'[Service]\nExecStart=\nExecStart=/usr/local/libexec/mocha-runtime-hardware\n')
    atomic(Path('/usr/local/libexec/mocha-runtime-policy.py'),args.policy.read_bytes(),0o755)
    atomic(Path('/etc/systemd/system/mocha-runtime-policy.service'),args.policy_unit.read_bytes())
    preference={'cpu_max_mhz':1020,'swappiness':80}
    try:
        previous=json.loads(preferences.read_text())
        if type(previous.get('cpu_max_mhz')) is int and 600<=previous['cpu_max_mhz']<=1020:preference['cpu_max_mhz']=previous['cpu_max_mhz']
        if type(previous.get('swappiness')) is int and 10<=previous['swappiness']<=100:preference['swappiness']=previous['swappiness']
    except (OSError,ValueError,AttributeError):pass
    parent_new=not preferences.parent.exists()
    atomic(preferences,(json.dumps(preference,indent=2)+'\n').encode())
    if parent_new:os.chown(preferences.parent,user.pw_uid,user.pw_gid)
    os.chown(preferences,user.pw_uid,user.pw_gid)
    temporary=modules.with_name(modules.name+'.installed-new')
    temporary.unlink(missing_ok=True);temporary.symlink_to(bundle/f'modules/lib/modules/{RELEASE}')
    temporary.replace(modules)
    for source,target in ((bundle/'uImage',Path('/boot/uImage-desktop')),
                          (bundle/'mocha.dtb',Path('/boot/mocha-desktop.dtb'))):
        temporary=target.with_name(target.name+'.runtime-new')
        shutil.copy2(source,temporary)
        assert digest(temporary)==digest(source)
        temporary.replace(target)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','mocha-runtime-policy.service'],check=True)
    diagnostic=Path('/usr/local/libexec/mocha-runtime-diagnostic.py')
    diagnostic_unit=Path('/etc/systemd/system/mocha-runtime-diagnostic.service')
    if diagnostic.exists() and diagnostic_unit.exists() and 'ROOT_DIAGNOSTIC_REACHED' in diagnostic.read_text():
        shutil.copy2(diagnostic,backup/'temporary-diagnostic.py')
        shutil.copy2(diagnostic_unit,backup/'temporary-diagnostic.service')
        subprocess.run(['systemctl','disable','--now','mocha-runtime-diagnostic.service'],check=True)
        diagnostic.unlink();diagnostic_unit.unlink()
        subprocess.run(['systemctl','daemon-reload'],check=True)
    os.sync()
    print('RUNTIME_DEFAULT_INSTALLED_REBOOT_ACCEPTANCE_PENDING',backup)

if __name__=='__main__':main()
