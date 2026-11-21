#!/usr/bin/python3
"""Disposable real-systemd OnFailure test; never operates on owner accounts.

Run from a staging directory containing oobe/{apply,state,unit} sources.
All apply account/desktop commands are denied or mapped to named dummy units.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

PREFIX = 'mocha-oobe-recovery-probe-20261101-'
BASE = Path(__file__).resolve().parent
SOURCE = BASE / 'oobe' if (BASE/'oobe').is_dir() else BASE.parent/'oobe'
REAL_RUN = subprocess.run


def is_root():
    # Windows has no geteuid; refuse explicitly instead of raising AttributeError.
    return hasattr(os, 'geteuid') and os.geteuid() == 0


def command(*args, **kwargs):
    return REAL_RUN(args, check=True, timeout=20, **kwargs)


def worker(directory, operation):
    sys.path.insert(0, str(SOURCE))
    from mocha_oobe_state import SetupState
    spec = importlib.util.spec_from_file_location('probe_apply', SOURCE/'mocha-oobe-apply.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = Path(directory)
    state = SetupState(root/'state')
    name = 'probeuser'
    module.pwd.getpwuid = lambda uid: SimpleNamespace(pw_name=name, pw_uid=1000)
    module.STATE = state.directory

    def safe_run(args, **kwargs):
        args = tuple(args)
        if args in (('loginctl','terminate-user','1000'), ('systemctl','stop','user@1000.service')):
            return SimpleNamespace(returncode=0)
        if args == ('systemctl','daemon-reload'):
            return command(*args)
        mapping = {'mocha-oobe-backend.service':PREFIX+'backend.service',
                   'mocha-oobe-session.service':PREFIX+'session.service',
                   'mocha-desktop.service':PREFIX+'desktop.service'}
        if args[:1] == ('systemctl',) and all(
                item in mapping or item in ('systemctl','restart','stop','--no-block') for item in args):
            return command(*(mapping.get(item,item) for item in args))
        raise AssertionError('Blocked unexpected command')

    def output(*args):
        if args == ('systemctl','show','mocha-desktop.service','--property=LoadState','--value'):
            return 'loaded'
        if args[:2] == ('systemctl','show') and args[2] in (
                'mocha-oobe-backend.service','mocha-oobe-session.service'):
            target = PREFIX + ('backend.service' if 'backend' in args[2] else 'session.service')
            return command('systemctl','show',target,'--property=ActiveState','--value',capture_output=True,text=True).stdout.strip()
        raise AssertionError('Blocked unexpected readback')

    module.run = lambda *args, **kw: safe_run(args, **kw)
    module.read_output = output
    module.subprocess.run = safe_run

    class Probe(module.Apply):
        def __init__(self):
            super().__init__(state, root/'root')

        def configure(self, data):
            state.checkpoint('account-renamed', ('mocha','probeuser'))
            if operation == 'fail':
                raise RuntimeError('fixture failure after rename')
            state.write('handoff-ready.json', {'request_sha256':hashlib.sha256(state.path('request.json').read_bytes()).hexdigest()})
            os.kill(os.getpid(), signal.SIGKILL)

    module.Apply = Probe
    sys.argv = [str(SOURCE/'mocha-oobe-apply.py')] + (['--recover'] if operation=='recover' else [])
    module.main()


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        return worker(sys.argv[2], sys.argv[3])
    if sys.argv[1:] != ['--fixture'] or not is_root():
        raise SystemExit('Explicit root --fixture required')
    passwd_before = hashlib.sha256(Path('/etc/passwd').read_bytes()).digest()
    owner_pending = Path('/var/lib/mocha-oobe/pending').exists()
    assert not owner_pending, 'Run only on initialized owner system'
    unitdir = Path('/run/systemd/system')
    names = [PREFIX+part+'.service' for part in ('apply','recover','backend','session','desktop')]
    assert not any((unitdir/name).exists() for name in names)
    with tempfile.TemporaryDirectory(prefix=PREFIX,dir='/run') as directory:
        root = Path(directory)
        state = root/'state';state.mkdir(mode=0o700)
        fake = root/'root/etc/systemd/system/mocha-oobe-session.service'
        fake.parent.mkdir(parents=True)
        fake.write_text('[Service]\nUser=mocha\n')
        (state/'pending').touch()
        request = {'username':'probeuser','hostname':'probe-tablet','locale':'zh_CN.UTF-8',
                   'timezone':'Asia/Shanghai','password_hash':'$6$fixture$notARealPasswordHash'}
        request_bytes = (json.dumps(request)+'\n').encode()
        (state/'request.json').write_bytes(request_bytes)
        for part in ('backend','session','desktop'):
            (unitdir/(PREFIX+part+'.service')).write_text(
                '[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/bin/true\n')
        def install(part, operation):
            original = (SOURCE/('mocha-oobe-'+part+'.service')).read_text()
            original = original.replace('/var/lib/mocha-oobe',str(state))
            original = original.replace('mocha-oobe-apply.service',PREFIX+'apply.service')
            original = original.replace('mocha-oobe-recover.service',PREFIX+'recover.service')
            line = f'ExecStart=/usr/bin/python3 {Path(__file__).resolve()} --worker {root} {operation}'
            original = '\n'.join(line if item.startswith('ExecStart=') else item for item in original.splitlines())+'\n'
            (unitdir/(PREFIX+part+'.service')).write_text(original)
        try:
            install('recover','recover')
            for operation in ('fail','kill'):
                install('apply', operation)
                for leaf in ('progress.json','handoff-ready.json'):
                    (state/leaf).unlink(missing_ok=True)
                command('systemctl','daemon-reload')
                REAL_RUN(['systemctl','reset-failed',*names],check=False,capture_output=True)
                REAL_RUN(['systemctl','start',PREFIX+'apply.service'],check=False,capture_output=True,timeout=20)
                deadline = time.monotonic()+15
                while time.monotonic()<deadline:
                    progress = json.loads((state/'progress.json').read_text()) if (state/'progress.json').exists() else {}
                    active = [REAL_RUN(['systemctl','is-active',PREFIX+p+'.service'],capture_output=True,text=True,timeout=5).stdout.strip()
                              for p in ('backend','session')] if progress.get('phase')=='failed' else []
                    if active == ['active','active']:break
                    time.sleep(.2)
                assert progress['phase']=='failed'
                assert (state/'pending').is_file() and (state/'request.json').read_bytes()==request_bytes
                assert not (state/'handoff-ready.json').exists()
                assert 'User=probeuser' in fake.read_text()
                override = root/'root/run/systemd/system/mocha-oobe-session.service.d/90-recovery-user.conf'
                assert override.read_text()=='[Service]\nUser=probeuser\n'
                assert active==['active','active']
                result = command('systemctl','show',PREFIX+'apply.service','--property=Result','--value',capture_output=True,text=True).stdout.strip()
                print(f'PASS actual OnFailure {operation}: result={result}; private request preserved; dummy UI/backend active',flush=True)
                command('systemctl','stop',*(PREFIX+p+'.service' for p in ('backend','session','recover')))
        finally:
            REAL_RUN(['systemctl','stop',*names],check=False,capture_output=True,timeout=20)
            for name in names:(unitdir/name).unlink(missing_ok=True)
            command('systemctl','daemon-reload')
            REAL_RUN(['systemctl','reset-failed',*names],check=False,capture_output=True)
    assert hashlib.sha256(Path('/etc/passwd').read_bytes()).digest()==passwd_before
    assert Path('/var/lib/mocha-oobe/pending').exists()==owner_pending
    print('PASS owner account/pending unchanged; disposable systemd units removed')


if __name__=='__main__':main()
