"""Validate loader profiles and command boundaries without invoking Fastboot."""
import hashlib
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('boot-installed-native.py')


class BootTest(unittest.TestCase):
    def exercise(self, profile=None, environment=None, product='mocha', version='U-Boot 2026.07'):
        commands = []
        last_command = ''

        def run(argv, **kwargs):
            nonlocal last_command
            args = argv[3:]
            commands.append(args)
            output = ''
            if args == ['getvar', 'version-bootloader']:
                output = version
            elif args == ['getvar', 'product']:
                output = product
            elif args[:1] == ['oem'] and args[1].startswith('run:'):
                last_command = args[1][4:]
            elif args == ['oem', 'console']:
                if last_command.startswith('printenv'):
                    output = environment if environment is not None else 'charger_ready=1'
                elif last_command.startswith('ext4load'):
                    output = '1024 bytes read'
            return subprocess.CompletedProcess(argv, 0, stdout=output.encode(), stderr=b'')

        with tempfile.TemporaryDirectory() as directory:
            loader = Path(directory) / 'loader.img'
            loader.write_bytes(b'isolated test loader')
            argv = [str(SCRIPT), '--factory-serial', 'factory-test', '--uboot-serial', 'ram-test',
                    '--loader', str(loader), '--loader-sha256', hashlib.sha256(loader.read_bytes()).hexdigest(),
                    '--log', str(Path(directory) / 'boot.log')]
            if profile:
                argv += ['--loader-profile', profile]
            with patch.object(sys, 'argv', argv), patch('subprocess.run', side_effect=run), \
                    patch('subprocess.check_output', return_value=b'factory-test\tfastboot\nram-test\tfastboot\n'), \
                    patch('builtins.print'):
                try:
                    runpy.run_path(str(SCRIPT), run_name='__main__')
                except RuntimeError:
                    return commands, False
        return commands, True

    def test_default_keeps_charger_guard(self):
        commands, passed = self.exercise()
        self.assertTrue(passed)
        self.assertIn(['oem', 'run:printenv charger_ready'], commands)

    def test_diagnostics_profile_and_ram_only_commands(self):
        commands, passed = self.exercise('ram-diagnostics',
                                       'bootcmd=echo Mocha RAM USB diagnostics - data cache disabled; fastboot usb 0')
        self.assertTrue(passed)
        for args in commands:
            self.assertIn(args[0], ('boot', 'getvar', 'oem'))
            if args[0] == 'oem' and args[1].startswith('run:'):
                self.assertLessEqual(len(('oem ' + args[1]).encode()), 64)
                self.assertNotIn('saveenv', args[1])
        self.assertIn(['oem', 'run:setenv verify yes'], commands)
        self.assertIn(['oem', 'run:setenv fdt_high ffffffff'], commands)
        self.assertEqual(commands[-1], ['oem', 'run:bootm 80007fc0 88000000:${rdsize} 8c000000'])

    def test_reject_wrong_loader_before_loading_emmc(self):
        cases = [dict(environment='charger_ready=0'),
                 dict(profile='ram-diagnostics', environment='bootcmd=run boot_debian'),
                 dict(product='other-board'), dict(version='U-Boot 2025.01')]
        for arguments in cases:
            with self.subTest(arguments=arguments):
                commands, passed = self.exercise(**arguments)
                self.assertFalse(passed)
                self.assertFalse(any('ext4load' in ' '.join(args) for args in commands))
                self.assertFalse(any('bootm' in ' '.join(args) for args in commands))


if __name__ == '__main__':
    unittest.main()
