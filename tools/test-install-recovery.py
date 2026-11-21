#!/usr/bin/env python3
"""Offline tests for persisted RAM-session recovery state.

Never runs fastboot/ssh/ssh-keygen: module-level `output` is replaced by a fake
that only writes the requested key files. No device or network access.
"""
import contextlib
import importlib.util
import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
PRIVATE=b'FAKE-PRIVATE-KEY-CONTENT-DO-NOT-LEAK'


@contextlib.contextmanager
def scratch():
    """Temporary directory; MOCHA_TEST_TMPDIR avoids restricted sandbox temp roots."""
    base=os.environ.get('MOCHA_TEST_TMPDIR')
    if base:
        path=Path(base)/('install-recovery-'+os.urandom(6).hex())
        path.mkdir(parents=True)
        try: yield path
        finally: shutil.rmtree(path,ignore_errors=True)
    else:
        with tempfile.TemporaryDirectory() as directory: yield Path(directory)


def load_flash():
    spec=importlib.util.spec_from_file_location('flash_distribution_recovery',HERE/'flash-distribution.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class RecoveryStateTests(unittest.TestCase):
    def setUp(self):
        self.mod=load_flash()
        self.calls=[]
        def fake_output(args,timeout=30):
            argv=[str(value) for value in args];self.calls.append(argv)
            if '-f' in argv:
                key=Path(argv[argv.index('-f')+1])
                key.write_bytes(PRIVATE)
                key.with_suffix('.pub').write_bytes(b'ssh-ed25519 FAKE-TEST-KEY\n')
            return ''
        self.mod.output=fake_output
        self.a=SimpleNamespace(ssh='ssh',ssh_keygen='ssh-keygen',fastboot='fastboot')

    def transport(self,work,recovery):
        transport=self.mod.Transport(self.a,Path(work),Path(recovery))
        self.assertEqual(self.calls[0][-1],str(Path(recovery)/'install-key'))
        return transport

    def test_probe_never_enters_the_write_sequence(self):
        with scratch() as directory:
            folder=Path(directory).resolve()/'backup'
            transport=mock.Mock()
            transport.endpoint.return_value='plan-only'
            transport.remote.side_effect=['1','{"app_bytes":3221225472}','1']
            probe=self.mod.Transport.probe
            transport.probe.side_effect=lambda target:probe(transport,target)
            argv=['flash-distribution.py',str(directory),'--probe','--backup',str(folder)]
            with mock.patch.object(sys,'argv',argv), \
                 mock.patch.object(self.mod,'verify_bundle',return_value={'version':'fixture'}), \
                 mock.patch.object(self.mod.shutil,'which',return_value='fixture'), \
                 mock.patch.object(self.mod,'Transport',return_value=transport), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.mod.main()
            transport.endpoint.assert_called_once_with('plan')
            transport.backup.assert_called_once_with(folder,{'app_bytes':3221225472})
            self.assertEqual(transport.remote.call_args_list,[
                mock.call('blockdev --getro /dev/mmcblk0'),mock.call('plan-only'),
                mock.call('blockdev --getro /dev/mmcblk0')])
            transport.stream.assert_not_called()
            transport._write_state.assert_called_once_with('probe-verified',strict=True)

    def test_non_utf8_fastboot_diagnostic_is_readable(self):
        result=load_flash().output([sys.executable,'-c',
                                    "import sys;sys.stderr.buffer.write(b'booting \\xff')"])
        self.assertIn('booting',result)

    def test_recovery_files_survive_temporary_workdir_and_use_persistent_paths(self):
        with scratch() as directory:
            recovery=Path(directory)/'mocha-backups'/'run1'/'ram-recovery'
            with scratch() as temporary:
                work=Path(temporary)
                transport=self.transport(work,recovery)
                for name in ('install-key','install-key.pub','known_hosts','RECOVERY.txt',
                             'reconnect.sh','reconnect.ps1','session-state.json'):
                    self.assertTrue((recovery/name).is_file(),name)
                command=transport.reconnect_command()
                self.assertIn(str(recovery/'install-key'),command)
                self.assertIn(str(recovery/'known_hosts'),command)
                self.assertNotIn(str(work),command)
                for name in ('RECOVERY.txt','reconnect.sh','reconnect.ps1'):
                    self.assertNotIn(PRIVATE.decode(),(recovery/name).read_text(encoding='utf-8-sig'))
            self.assertFalse(work.exists())
            self.assertTrue((recovery/'install-key').is_file())
            self.assertTrue((recovery/'RECOVERY.txt').is_file())
            state=json.loads((recovery/'session-state.json').read_text())
            self.assertEqual(state['phase'],'prepared')
            self.assertFalse(state['ram_session'])
            self.assertNotIn(PRIVATE.decode(),(recovery/'session-state.json').read_text())
            if os.name=='posix':
                self.assertEqual(stat.S_IMODE(recovery.stat().st_mode),0o700)
                self.assertEqual(stat.S_IMODE((recovery/'install-key').stat().st_mode),0o600)
                self.assertEqual(stat.S_IMODE((recovery/'reconnect.sh').stat().st_mode),0o700)

    def test_failure_before_ram_keeps_key_but_does_not_offer_a_command(self):
        with scratch() as directory:
            recovery=Path(directory)/'ram-recovery'
            with scratch() as temporary:
                transport=self.transport(temporary,recovery)
                out=io.StringIO()
                with contextlib.redirect_stdout(out):transport.failure()
            text=out.getvalue()
            self.assertIn(str(recovery),text)
            self.assertIn('Fastboot',text)
            self.assertNotIn(PRIVATE.decode(),text)
            self.assertNotIn('root@172.31.124.2',text)
            self.assertEqual(json.loads((recovery/'session-state.json').read_text())['phase'],'failed')

    def test_failure_after_ram_prints_a_command_with_persistent_paths_only(self):
        with scratch() as directory:
            recovery=Path(directory)/'ram-recovery'
            with scratch() as temporary:
                transport=self.transport(temporary,recovery)
                transport.ram_ready=True
                out=io.StringIO()
                with contextlib.redirect_stdout(out):transport.failure()
            text=out.getvalue()
            self.assertIn(str(recovery),text)
            self.assertIn(str(recovery/'install-key'),text)
            self.assertIn('root@172.31.124.2',text)
            self.assertNotIn(PRIVATE.decode(),text)
            state=json.loads((recovery/'session-state.json').read_text())
            self.assertEqual(state['phase'],'failed')
            self.assertTrue(state['ram_session'])

    def test_success_notice_is_session_only_and_never_prints_key_material(self):
        with scratch() as directory:
            recovery=Path(directory)/'ram-recovery'
            with scratch() as temporary:
                transport=self.transport(temporary,recovery)
                transport.ram_ready=True
                out=io.StringIO()
                with contextlib.redirect_stdout(out):transport.success()
            text=out.getvalue()
            self.assertIn(str(recovery),text)
            self.assertIn('delete',text.lower())
            self.assertNotIn(PRIVATE.decode(),text)
            self.assertNotIn('root@172.31.124.2',text)
            self.assertEqual(json.loads((recovery/'session-state.json').read_text())['phase'],'installed')

    def test_shell_scripts_preserve_argv_with_awkward_paths(self):
        with scratch() as directory:
            recovery=Path(directory)/"mo cha'session $key% &"/'ram-recovery'
            with scratch() as temporary:
                transport=self.transport(temporary,recovery)
                posix=transport.reconnect_command_posix()
                windows=transport.reconnect_command_windows()
                self.assertEqual(shlex.split(posix),transport.ssh)
                self.assertNotEqual(posix,windows)
                sh_line=(recovery/'reconnect.sh').read_text(encoding='utf-8').splitlines()[-1]
                self.assertTrue(sh_line.startswith('exec '))
                self.assertEqual(shlex.split(sh_line[len('exec '):]),transport.ssh)
                ps_text=(recovery/'reconnect.ps1').read_text(encoding='utf-8-sig')
                self.assertTrue(ps_text.startswith(windows+'\n'))
                powershell=shutil.which('powershell') or shutil.which('pwsh')
                if powershell:
                    recorder=Path(directory)/'record-argv.py'
                    recorder.write_text('import json,sys;print(json.dumps(sys.argv[1:]))')
                    saved=transport.ssh
                    transport.ssh=[sys.executable,str(recorder),*saved]
                    command=transport.reconnect_command_windows()
                    result=subprocess.run([powershell,'-NoProfile','-NonInteractive','-Command',command],
                        capture_output=True,text=True,check=True,timeout=20)
                    self.assertEqual(json.loads(result.stdout),saved)
                    transport.ssh=saved
                text=(recovery/'RECOVERY.txt').read_text()
                self.assertIn('POSIX shell',text)
                self.assertIn('Windows PowerShell',text)

    def test_scratch_default_branch_uses_tempfile_without_recursion(self):
        created=[]
        class FakeTemp:
            def __init__(self,*args,**kwargs):created.append((args,kwargs))
            def __enter__(self):return '/tmp/fake-workdir'
            def __exit__(self,*exc):return False
        with mock.patch.object(tempfile,'TemporaryDirectory',FakeTemp), \
             mock.patch.dict(os.environ,{'MOCHA_TEST_TMPDIR':''}):
            with scratch() as path:self.assertEqual(path,Path('/tmp/fake-workdir'))
        self.assertEqual(len(created),1)

    def test_setup_failure_after_key_written_reports_recovery_dir(self):
        with scratch() as directory:
            backup=Path(directory)/'backup';backup.mkdir()
            recovery=backup/'ram-recovery'
            with scratch() as temporary:
                with mock.patch.object(self.mod.Transport,'_write_state',side_effect=OSError('state denied')):
                    with self.assertRaises(OSError):
                        self.mod.Transport(self.a,Path(temporary),recovery)
                self.assertTrue((recovery/'install-key').is_file())
                self.assertTrue((recovery/'reconnect.sh').is_file())
                out=io.StringIO()
                with contextlib.redirect_stdout(out):self.mod.report_setup_failure(recovery,backup)
            text=out.getvalue()
            self.assertIn(str(recovery),text)
            self.assertIn('session key was already written',text)
            self.assertNotIn(PRIVATE.decode(),text)
            state=json.loads((recovery/'session-state.json').read_text())
            self.assertEqual(state['phase'],'setup-failed')
            self.assertFalse(state['ram_session'])


if __name__=='__main__':
    unittest.main()
