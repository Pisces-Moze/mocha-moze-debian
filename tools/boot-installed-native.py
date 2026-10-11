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
p.add_argument('--diagnostic', action='store_true')
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
if 'U-Boot' not in run(['getvar', 'version-bootloader']):
    raise RuntimeError('expected RAM U-Boot')
command('printenv charger_ready')
if 'charger_ready=1' not in run(['oem', 'console']):
    raise RuntimeError('expected verified prototype RAM loader with charger_ready=1')
for address, file in [('88000000', '/boot/initramfs.cpio.gz'),
                      ('80007fc0', '/boot/uImage-native-perf'),
                      ('8c000000', '/boot/mocha-native-perf.dtb')]:
    command('ext4load mmc 0#APP ' + address + ' ' + file)
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
if a.diagnostic:
    for unit in ('user@1000.service', 'mocha-native-gpu-policy.service'):
        command('setenv m systemd.mask=' + unit)
        command('setenv bootargs ${bootargs} ${m}')
command('bootm 80007fc0 88000000:${rdsize} 8c000000', disconnect=True)
print('TEMPORARY_NATIVE_DISPATCHED_DEFAULT_BOOT_UNCHANGED; verify actual SSH, kernel and display')
