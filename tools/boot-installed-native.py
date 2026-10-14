#!/usr/bin/env python3
"""Select an already-staged prototype native boot in RAM; never flash."""
import argparse
import hashlib
import re
import subprocess
import time
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--fastboot', default='fastboot')
p.add_argument('--factory-serial', required=True)
p.add_argument('--uboot-serial', required=True)
p.add_argument('--loader', type=Path, required=True)
p.add_argument('--loader-sha256', required=True)
p.add_argument('--loader-profile', choices=('charger-ready', 'ram-diagnostics'), default='charger-ready',
               help='Require the charger-ready loader, or the separately verified RAM diagnostics environment')
p.add_argument('--diagnostic', action='store_true')
p.add_argument('--runtime-candidate', action='store_true',
               help='Load /moze-rt/uImage and mocha.dtb from UDA, mask the desktop and disable CPU idle for the first DVFS trial')
p.add_argument('--resume-loader', action='store_true')
p.add_argument('--log', type=Path, default=Path('artifacts/native-boot.log'))
a = p.parse_args()
if hashlib.sha256(a.loader.read_bytes()).hexdigest() != a.loader_sha256.lower():
    p.error('RAM loader SHA256 does not match')
a.log.parent.mkdir(parents=True, exist_ok=True)
serial = a.factory_serial

def run(args, timeout=30, disconnect=False):
    try:
        result = subprocess.run([a.fastboot, '-s', serial] + args, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if not disconnect:
            raise
        return ''
    output = (result.stdout + result.stderr).decode(errors='replace')
    output = re.sub(r'(otf_key=)[^\s]+', r'\1[REDACTED]', output)
    with a.log.open('a', encoding='utf-8') as log:
        log.write(' '.join(args) + '\n' + output + '\n')
    if result.returncode and not disconnect:
        raise RuntimeError(output[:800])
    return output

def command(value, disconnect=False):
    if len(('oem run:' + value).encode()) > 64:
        raise ValueError('Fastboot OEM command exceeds 64 bytes')
    run(['oem', 'run:' + value], disconnect=disconnect)

if not a.resume_loader:
    if serial not in subprocess.check_output([a.fastboot, 'devices'], timeout=8).decode():
        p.error('factory Fastboot device not found')
    run(['boot', str(a.loader)], timeout=45)
serial = a.uboot_serial
for _ in range(20):
    if serial in subprocess.check_output([a.fastboot, 'devices'], timeout=8).decode():
        break
    time.sleep(1)
version = run(['getvar', 'version-bootloader'])
if 'U-Boot' not in version or '2026.07' not in version:
    raise RuntimeError('expected RAM U-Boot')
if 'mocha' not in run(['getvar', 'product']).lower():
    raise RuntimeError('expected Mocha RAM U-Boot product')
if a.loader_profile == 'charger-ready':
    command('printenv charger_ready')
    if 'charger_ready=1' not in run(['oem', 'console']):
        raise RuntimeError('expected verified prototype RAM loader with charger_ready=1')
else:
    # The project's separately tested RAM profile never writes its environment.
    command('printenv bootcmd')
    environment = run(['oem', 'console'])
    if ('bootcmd=echo Mocha RAM USB diagnostics' not in environment
            or 'fastboot usb 0' not in environment):
        raise RuntimeError('expected verified RAM diagnostics boot environment')
command('mmc dev 0')
command('setenv verify yes')
command('setenv fdt_high ffffffff')
command('setenv initrd_high ffffffff')
files=[('88000000','APP','/boot/initramfs.cpio.gz')]
if a.runtime_candidate:
    files += [('80007fc0','UDA','/moze-rt/uImage'),('8c000000','UDA','/moze-rt/mocha.dtb')]
else:
    files += [('80007fc0','APP','/boot/uImage-native-perf'),('8c000000','APP','/boot/mocha-native-perf.dtb')]
for address, partition, file in files:
    command('ext4load mmc 0#' + partition + ' ' + address + ' ' + file)
    if 'bytes read' not in run(['oem', 'console']):
        raise RuntimeError('eMMC file was not loaded: ' + file)
    if address == '88000000':
        command('setenv rdsize ${filesize}')
command('fdt addr 8c000000')
command('fdt resize 10000')
command('setenv bootargs mem=1700M maxcpus=4')
for argument in ('root=/dev/mmcblk0p26', 'rootfstype=ext4', 'rootwait', 'rw',
                 'console=tty0', 'panic=30', 'loglevel=4', 'clk_ignore_unused',
                 'regulator_ignore_unused', 'mocha_native_performance=1'):
    command('setenv bootargs ${bootargs} ' + argument)
command('setenv m systemd.unit=multi-user.target')
command('setenv bootargs ${bootargs} ${m}')
if a.runtime_candidate:
    command('setenv bootargs ${bootargs} cpuidle.off=1')
if a.diagnostic or a.runtime_candidate:
    units=['user@1000.service', 'mocha-native-gpu-policy.service']
    if a.runtime_candidate: units.append('mocha-desktop-hardware.service')
    for unit in units:
        command('setenv m systemd.mask=' + unit)
        command('setenv bootargs ${bootargs} ${m}')
command('bootm 80007fc0 88000000:${rdsize} 8c000000', disconnect=True)
print('TEMPORARY_NATIVE_DISPATCHED_DEFAULT_BOOT_UNCHANGED; verify actual SSH, kernel and display')
