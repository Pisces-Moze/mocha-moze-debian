#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""PC installer: verify bundle, RAM boot, backup GPT/LNX, restore, reboot to desktop.

Plan-only by default. --install --erase APP_UDA is the single destructive
choice. Never uses fastboot flash/erase, never writes factory boot partitions.
"""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from ram_archive import personalize

BASE=Path(__file__).resolve().parent


def restrict(path,mode):
    """Best-effort owner-only permission; Windows only maps the read-only bit."""
    try:os.chmod(path,mode)
    except OSError:pass


def report_setup_failure(recovery,folder):
    """Truthful pointer when Transport setup itself failed after creating files."""
    recovery=Path(recovery);key=recovery/'install-key'
    print('\nInstaller setup did not finish; backup directory:',folder,flush=True)
    print('Recovery directory:',recovery,flush=True)
    if key.is_file():
        print('A session key was already written there; it is valid only for the current RAM session.',flush=True)
    else:
        print('No session key was written; power-cycle to factory Fastboot and rerun the installer.',flush=True)
    try:
        state=recovery/'session-state.json'
        state.write_text(json.dumps({'schema':1,'phase':'setup-failed','ram_session':False,
            'backup':str(folder),'updated':time.strftime('%Y-%m-%dT%H:%M:%S%z')})+'\n')
        restrict(state,0o600)
    except OSError:
        print('Warning: could not record the setup-failed state; inspect the directory above.',flush=True)


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_bundle(root,allow_candidate=False):
    manifest=json.loads((root/'bundle.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!=1 or manifest.get('device')!='xiaomi-mocha-16gb':
        raise ValueError('Unsupported bundle schema/device')
    if manifest.get('app_bytes')!=3*1024**3:raise ValueError('Expected exactly 3 GiB APP')
    if manifest.get('release_state')!='verified' and not allow_candidate:
        raise ValueError('This candidate has not passed the desktop/flash acceptance gate')
    names={'loader.img','uImage','mocha.dtb','installer.cpio.gz','APP.img.xz','DATA.tar.xz','LNX.img'}
    if set(manifest['files'])!=names:raise ValueError('Bundle must contain exactly the seven required payloads')
    for name,expected in manifest['files'].items():
        path=root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=expected['bytes'] or digest(path)!=expected['sha256']:
            raise ValueError('Bundle verification failed: '+name)
    if not re.fullmatch('[0-9a-f]{64}',manifest.get('app_raw_sha256','')):
        raise ValueError('Missing raw APP hash')
    expanded=manifest.get('data_expanded_bytes')
    uda=23160832*512  # fixed UDA in the validated 3 GiB APP layout
    if type(expanded) is not int or not 0<expanded<uda:
        raise ValueError('Missing or invalid DATA expanded-space budget; rebuild bundle')
    if manifest['files']['DATA.tar.xz']['bytes']+expanded+256*1024**2>uda-uda//8:
        raise ValueError('DATA peak exceeds the fixed UDA installation budget')
    return manifest


def output(args,timeout=30):
    process=subprocess.run(args,capture_output=True,encoding='utf-8',errors='replace',timeout=timeout)
    if process.returncode:
        message=(process.stdout+process.stderr)[-1200:]
        message=re.sub(r'(otf_key=)\S+',r'\1[redacted]',message)
        raise RuntimeError(message)
    return process.stdout+process.stderr


class Transport:
    def __init__(self,a,work,recovery):
        self.a=a;self.work=work;self.serial=None;self.ram_ready=False
        self.recovery=recovery
        self.recovery.mkdir(parents=True,exist_ok=True);restrict(self.recovery,0o700)
        self.key=self.recovery/'install-key'
        self.known_hosts=self.recovery/'known_hosts'
        self.state=self.recovery/'session-state.json'
        if self.key.exists():
            raise RuntimeError('Recovery directory already contains an install key: '+str(self.recovery))
        self.known_hosts.touch(mode=0o600,exist_ok=True);restrict(self.known_hosts,0o600)
        output([a.ssh_keygen,'-q','-t','ed25519','-N','','-f',str(self.key)])
        for path in (self.key,self.key.with_suffix('.pub'),self.known_hosts):restrict(path,0o600)
        self.ssh=[a.ssh,'-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','ConnectTimeout=8',
            '-o','ServerAliveInterval=5','-o','ServerAliveCountMax=3',
            '-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.known_hosts),
            '-i',str(self.key),'root@172.31.124.2']
        self._write_recovery()

    def reconnect_command_posix(self):
        return shlex.join(self.ssh)

    def reconnect_command_windows(self):
        # PowerShell literals preserve %, &, $, quotes and spaces. Windows CRT
        # quoting (list2cmdline) alone does not protect against cmd expansion.
        return '& '+' '.join("'"+str(arg).replace("'","''")+"'" for arg in self.ssh)

    def reconnect_command(self):
        return self.reconnect_command_windows() if os.name=='nt' else self.reconnect_command_posix()

    def _write_state(self,phase,strict=False):
        try:
            self.state.write_text(json.dumps({'schema':1,'phase':phase,'ram_session':self.ram_ready,
                'backup':str(self.recovery.parent),
                'updated':time.strftime('%Y-%m-%dT%H:%M:%S%z')})+'\n')
            restrict(self.state,0o600)
            return True
        except OSError:
            if strict:raise
            return False

    def _write_recovery(self):
        posix=self.reconnect_command_posix();windows=self.reconnect_command_windows()
        retry='--probe' if getattr(self.a,'probe',False) else '--install --erase APP_UDA'
        if getattr(self.a,'allow_candidate',False):retry+=' --allow-candidate'
        text=('Mocha installer RAM-session recovery\n'
              '====================================\n\n'
              'Only for the current RAM session on this PC. Do not upload, copy or print the private key.\n\n'
              'Private key:   '+str(self.key)+'\n'
              'Public key:    '+str(self.key)+'.pub\n'
              'Known hosts:   '+str(self.known_hosts)+'\n'
              'Session state: '+str(self.state)+'\n\n'
              'If the installer stops after the RAM system booted, keep USB connected and run one of:\n\n'
              'POSIX shell ('+str(self.recovery/'reconnect.sh')+'):\n'
              '  '+posix+'\n\n'
              'Windows PowerShell ('+str(self.recovery/'reconnect.ps1')+'):\n'
              '  '+windows+'\n\n'
              'The RAM system accepts only this session key. If the RAM session is gone, power-cycle\n'
              'to factory Fastboot and rerun the installer with '+retry+'.\n'
              'Delete this recovery directory after the install finishes; it is not reusable.\n')
        (self.recovery/'RECOVERY.txt').write_text(text,encoding='utf-8');restrict(self.recovery/'RECOVERY.txt',0o600)
        script=self.recovery/'reconnect.sh'
        script.write_text('#!/bin/sh\n# Mocha RAM-session recovery only; delete after install.\nexec '+posix+'\n',encoding='utf-8',newline='\n')
        restrict(script,0o700)
        ps_script=self.recovery/'reconnect.ps1'
        ps_script.write_text(windows+'\nexit $LASTEXITCODE\n',encoding='utf-8-sig');restrict(ps_script,0o600)
        self._write_state('prepared',strict=True)

    def failure(self):
        saved=self._write_state('failed')
        operation='RAM probe' if getattr(self.a,'probe',False) else 'Install'
        print('\n'+operation+' did not complete; recovery state was kept for this RAM session only.',flush=True)
        print('Recovery directory:',self.recovery,flush=True)
        if self.ram_ready:
            print('Keep USB connected. Reconnect to the running RAM system with:',flush=True)
            print('  '+self.reconnect_command(),flush=True)
        else:
            print('The RAM system was not reached, so the saved key is not usable yet.',flush=True)
            print('Check the Fastboot connection and follow the retry instructions below.',flush=True)
        print('See',self.recovery/'RECOVERY.txt','; do not upload or print the private key.',flush=True)
        if not saved:print('Warning: could not update the session state file.',flush=True)

    def success(self):
        saved=self._write_state('installed')
        print('Recovery key/known_hosts at',self.recovery,
              'are for this RAM session only; delete that directory after the tablet reboots.',flush=True)
        if not saved:print('Warning: could not update the session state file; inspect the recovery directory.',flush=True)

    def devices(self):
        rows=output([self.a.fastboot,'devices']).strip().splitlines()
        return [line.split()[0] for line in rows if line.strip()]

    def fb(self,*args,timeout=40):
        return output([self.a.fastboot,'-s',self.serial,*args],timeout)

    def oem(self,command,disconnect=False):
        if len(('oem run:'+command).encode())>64:raise ValueError('OEM command too long')
        try:
            self.fb('oem','run:'+command)
        except (RuntimeError,subprocess.TimeoutExpired):
            if disconnect:return
            raise
        try:return self.fb('oem','console')
        except (RuntimeError,subprocess.TimeoutExpired) as error:
            if disconnect or 'Empty console' in str(error):return ''
            raise

    def boot(self,root):
        devices=self.devices()
        if len(devices)!=1:raise RuntimeError('Connect exactly one Mocha in Fastboot')
        self.serial=devices[0]
        if getattr(self.a,'resume_loader',False):
            if 'U-Boot' not in self.fb('getvar','version-bootloader'):
                raise RuntimeError('Expected the already started RAM U-Boot')
        else:
            if 'mocha' not in self.fb('getvar','product').lower():raise RuntimeError('Factory product is not mocha')
            self.fb('boot',str(root/'loader.img'),timeout=60)
            print('RAM loader sent. Waiting for its Fastboot USB interface.',flush=True)
            for _ in range(45):
                devices=self.devices()
                if len(devices)==1:
                    self.serial=devices[0]
                    try:
                        if 'U-Boot' in self.fb('getvar','version-bootloader'):break
                    except RuntimeError:pass
                time.sleep(1)
            else:raise RuntimeError('RAM U-Boot did not enumerate')
        if 'mocha' not in self.fb('getvar','product').lower():raise RuntimeError('RAM product mismatch')
        # The loader must stay in the read-only diagnostics profile, not autoboot.
        environment=self.oem('printenv bootcmd')
        if 'Mocha RAM USB diagnostics' not in environment or 'fastboot usb 0' not in environment:
            raise RuntimeError('Unexpected RAM loader profile')
        personalized=self.work/'installer-personalized.cpio.gz'
        personalize(root/'installer.cpio.gz',personalized,self.key.with_suffix('.pub').read_bytes())
        payloads=[(root/'uImage',0x80007fc0),(personalized,0x88000000),(root/'mocha.dtb',0x8c000000)]
        ranges=sorted((address,address+path.stat().st_size) for path,address in payloads)
        if any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])) or ranges[-1][1]>=0x91000000:
            raise RuntimeError('RAM payload addresses overlap')
        for path,address in payloads:
            self.fb('stage',str(path),timeout=120)
            self.oem(f'cp.b 91000000 {address:x} {path.stat().st_size:x}')
            result=self.oem(f'crc32 {address:x} {path.stat().st_size:x}')
            with path.open('rb') as stream:
                crc=0
                while data:=stream.read(1024*1024):crc=zlib.crc32(data,crc)
            match=re.findall(r'==>\s*([0-9a-fA-F]{8})',result)
            if not match or int(match[-1],16)!=crc:raise RuntimeError('RAM CRC mismatch: '+path.name)
        for command in ('setenv verify yes','setenv fdt_high ffffffff','setenv initrd_high ffffffff',
                        'fdt addr 8c000000','fdt resize 10000','setenv bootargs mem=1700M rdinit=/init'):
            self.oem(command)
        for arg in ('maxcpus=4','console=tty0','panic=30','loglevel=6','clk_ignore_unused',
                    'regulator_ignore_unused','cpuidle.off=1'):
            self.oem('setenv bootargs ${bootargs} '+arg)
        self.oem(f'bootm 80007fc0 88000000:{personalized.stat().st_size:x} 8c000000',disconnect=True)
        for _ in range(60):
            try:
                self.remote('test -f /etc/mocha-distribution-ram')
                self.ram_ready=True;self._write_state('ram-session');return
            except (RuntimeError,subprocess.TimeoutExpired):time.sleep(2)
        raise RuntimeError('RAM USB SSH unavailable; do not format or reboot blindly')

    def remote(self,command,timeout=45):return output(self.ssh+[command],timeout)

    def endpoint(self,action,*args):
        # Arguments are restricted hashes/integers/CID tokens, never shell text.
        words=[action,*args]
        if not all(re.fullmatch('[A-Za-z0-9_.-]+',word) for word in words):raise ValueError('Unsafe installer argument')
        return 'python3 /usr/local/libexec/distribution-ram.py '+' '.join(words)

    def stream(self,command,source):
        process=subprocess.Popen(self.ssh+[command],stdin=subprocess.PIPE)
        try:
            shutil.copyfileobj(source,process.stdin,length=1024*1024)
            process.stdin.close()
            if process.wait()!=0:raise RuntimeError('Restore failed; keep RAM running and inspect the reported phase')
        except BaseException:
            process.kill();process.wait();raise

    def backup(self,folder,plan):
        folder.mkdir(parents=True,exist_ok=True)
        if (folder/'plan.json').exists():raise RuntimeError('Backup directory already contains a plan')
        (folder/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
        # Primary GPT/reserved prefix, tail GPT and original LNX; personal backup
        # files are PC-local. No factory EBT/BCT/boot0/boot1 is ever overwritten.
        reads=[('primary-gpt.bin','dd if=/dev/mmcblk0 bs=512 count=4096'),
               ('secondary-gpt.bin','dd if=/dev/mmcblk0 bs=512 skip=30773248 count=4096'),
               ('LNX-before.img','cat /dev/mmcblk0p22')]
        for name,command in reads:
            with (folder/name).open('xb') as target:
                process=subprocess.run(self.ssh+[command],stdout=target,stderr=subprocess.PIPE,timeout=90)
            if process.returncode:raise RuntimeError('PC backup transfer failed')
            actual=digest(folder/name)
            expected=self.remote(command+' 2>/dev/null | sha256sum').split()[0]
            if actual!=expected:raise RuntimeError('PC backup readback mismatch')
        (folder/'SHA256SUMS').write_text(''.join(digest(folder/name)+'  '+name+'\n' for name,_ in reads))

    def probe(self,folder):
        if self.remote('blockdev --getro /dev/mmcblk0').strip()!='1':
            raise RuntimeError('RAM installer did not keep eMMC read-only')
        plan=json.loads(self.remote(self.endpoint('plan')))
        self.backup(folder,plan)
        if self.remote('blockdev --getro /dev/mmcblk0').strip()!='1':
            raise RuntimeError('eMMC read-only check failed after backup')
        self._write_state('probe-verified',strict=True)
        print('RAM_PROBE_VERIFIED: eMMC read-only, geometry and PC backups checked.',flush=True)
        print('The tablet remains in RAM maintenance. Session files:',self.recovery,flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle',type=Path)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--install',action='store_true')
    mode.add_argument('--probe',action='store_true',
                      help='Boot RAM, verify the read-only plan and save GPT/LNX backups')
    p.add_argument('--resume-loader',action='store_true',
                   help='Resume a read-only probe from the already started RAM U-Boot')
    p.add_argument('--erase',choices=['APP_UDA']);p.add_argument('--allow-candidate',action='store_true')
    p.add_argument('--fastboot',default='fastboot');p.add_argument('--ssh',default='ssh')
    p.add_argument('--ssh-keygen',default='ssh-keygen')
    p.add_argument('--backup',type=Path,default=Path('mocha-backups')/time.strftime('%Y%m%d-%H%M%S'))
    a=p.parse_args()
    if a.resume_loader and not a.probe:p.error('--resume-loader requires --probe')
    if a.install and a.erase!='APP_UDA':p.error('--install requires --erase APP_UDA; APP/UDA/cache data will be lost')
    if a.erase and not a.install:p.error('--erase is only valid with --install')
    root=a.bundle.resolve();manifest=verify_bundle(root,a.allow_candidate)
    print('Verified bundle:',manifest['version'],'APP: 3 GiB; UDA: remaining validated 16 GB layout')
    if not (a.install or a.probe):
        print('PLAN ONLY: no device commands. Install with --install --erase APP_UDA after backing up personal data.');return
    for tool in (a.fastboot,a.ssh,a.ssh_keygen):
        if not shutil.which(tool):p.error('Missing PC prerequisite: '+tool)
    with tempfile.TemporaryDirectory(prefix='mocha-install-') as temporary:
        folder=a.backup.resolve()
        if folder.exists() and any(folder.iterdir()):
            p.error('Backup directory must be new or empty: '+str(folder))
        folder.mkdir(parents=True,exist_ok=True);restrict(folder,0o700)
        recovery=folder/'ram-recovery'
        transport=None
        try:
            transport=Transport(a,Path(temporary),recovery)
            transport.boot(root)
            if a.probe:
                transport.probe(folder)
                return
            plan=json.loads(transport.remote(transport.endpoint('plan')))
            transport.backup(folder,plan)
            print('GPT/LNX backups verified at',folder,flush=True)
            print(transport.remote(transport.endpoint('prepare','--cid',plan['cid'],
                '--gpt-sha256',plan['gpt_sha256'],'--erase','ERASE_APP_UDA'),timeout=180))
            with lzma.open(root/'APP.img.xz','rb') as source:
                transport.stream(transport.endpoint('write-app','--sha256',manifest['app_raw_sha256']),source)
            data=manifest['files']['DATA.tar.xz']
            with (root/'DATA.tar.xz').open('rb') as source:
                transport.stream(transport.endpoint('restore-data','--bytes',str(data['bytes']),
                    '--expanded-bytes',str(manifest['data_expanded_bytes']),'--sha256',data['sha256']),source)
            lnx=manifest['files']['LNX.img']
            with (root/'LNX.img').open('rb') as source:
                transport.stream(transport.endpoint('finalize','--bytes',str(lnx['bytes']),'--sha256',lnx['sha256']),source)
            # Losing SSH here is expected only after all readbacks have succeeded.
            transport.remote('sync; (sleep 2; /bin/busybox reboot -f) >/dev/null 2>&1 </dev/null &')
        except BaseException:
            if transport is not None:transport.failure()
            else:report_setup_failure(recovery,folder)
            raise
        transport.success()
        print('Installed. The tablet will reboot to the desktop (user: mocha, password: mocha).')


if __name__=='__main__':main()
