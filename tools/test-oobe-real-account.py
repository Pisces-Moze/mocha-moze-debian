#!/usr/bin/env python3
"""Explicit Linux-root fixture: real account utilities in a disposable chroot.

Never runs account utilities against the host root, never contacts systemd or
D-Bus. This checks rename/password/groups, not actual desktop/PAM login.
"""
import ctypes
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock


def main():
    if sys.argv[1:]!=['--fixture'] or sys.platform!='linux' or os.geteuid()!=0:
        raise SystemExit('Requires explicit --fixture in a disposable Linux root build container')
    oobe=Path(__file__).resolve().parent.parent/'oobe'
    sys.path.insert(0,str(oobe))
    from mocha_oobe_state import SetupState
    spec=importlib.util.spec_from_file_location('oobe_real_account',oobe/'mocha-oobe-apply.py')
    app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
    host_passwd=hashlib.sha256(Path('/etc/passwd').read_bytes()).hexdigest()
    help_text=subprocess.check_output(['usermod','--help'],text=True)
    assert '--root' in help_text
    password='Oobe-test-only-2026!'
    result=subprocess.run(['openssl','passwd','-6','-stdin'],input=password+'\n',
                          text=True,capture_output=True,check=True)
    encoded=result.stdout.strip()
    with tempfile.TemporaryDirectory(prefix='mocha-oobe-account-') as directory:
        base=Path(directory).resolve();root=base/'root';root.mkdir()
        assert root.parent==base and root!=Path('/')
        etc=root/'etc';etc.mkdir()
        (etc/'passwd').write_text('root:x:0:0:root:/root:/bin/sh\nmocha:x:1000:1000::/home/mocha:/bin/sh\n')
        (etc/'shadow').write_text('root:!:20000:0:99999:7:::\nmocha:!:20000:0:99999:7:::\n')
        (etc/'shadow').chmod(0o600)
        (etc/'group').write_text('root:x:0:\nmocha:x:1000:\nsudo:x:27:\naudio:x:29:mocha\nvideo:x:44:mocha\ninput:x:998:mocha\n')
        (etc/'gshadow').write_text('root:!::\nmocha:!::\nsudo:!::\naudio:!::mocha\nvideo:!::mocha\ninput:!::mocha\n')
        (etc/'gshadow').chmod(0o600)
        (etc/'nsswitch.conf').write_text('passwd: files\ngroup: files\nshadow: files\n')
        (etc/'login.defs').write_text('ENCRYPT_METHOD SHA512\n')
        (root/'home/mocha').mkdir(parents=True)
        for binary in ('id','getent'):
            source=Path(shutil.which(binary)).resolve()
            target=root/str(source).lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            # Copy only the dependencies declared by this trusted system binary.
            linked=subprocess.check_output(['ldd',str(source)],text=True)
            for name in re.findall(r'(/[\w./+_-]+)',linked):
                library=Path(name)
                if library.is_file():
                    target=root/str(library).lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(library,target)
        state=SetupState(base/'state');state.directory.mkdir()
        state.path('pending').touch()
        data={'username':'oobe-owner','hostname':'fixture-tablet','locale':'zh_CN.UTF-8',
              'timezone':'Asia/Shanghai','password_hash':encoded}
        state.write('request.json',data)
        values={'host':'fixture','locale':'C.UTF-8','timezone':'UTC'}
        calls=[];failure={'password':True}

        def chroot(*args):
            return subprocess.check_output(['chroot',str(root),*args],text=True,timeout=10).strip()

        def account(name=None,uid=None):
            for line in (etc/'passwd').read_text().splitlines():
                fields=line.split(':')
                if (name is not None and fields[0]==name) or (uid is not None and int(fields[2])==uid):
                    return SimpleNamespace(pw_name=fields[0],pw_uid=int(fields[2]),pw_dir=fields[5])
            raise KeyError(name or uid)

        def run(*args,**kwargs):
            calls.append(args)
            if args[0] in ('usermod','chpasswd'):
                assert root.is_relative_to(base) and (etc/'passwd').is_file()
                if args[0]=='chpasswd' and failure['password']:
                    failure['password']=False
                    raise RuntimeError('injected after real rename')
                return subprocess.run([args[0],'--root',str(root),*args[1:]],
                    check=True,timeout=20,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kwargs)
            if args[:2]==('hostnamectl','set-hostname'):values['host']=args[2]
            if args[:2]==('localectl','set-locale'):values['locale']=args[2].split('=',1)[1]
            if args[:2]==('timedatectl','set-timezone'):values['timezone']=args[2]
            return SimpleNamespace(returncode=0)

        def output(*args):
            if args[:2]==('getent','shadow'):return chroot(shutil.which('getent'),*args[1:])
            if args[:2]==('id','-nG'):return chroot(shutil.which('id'),*args[1:])
            if args==('locale','-a'):return 'zh_CN.utf8\nen_US.utf8\nC.utf8'
            if args==('hostnamectl','--static'):return values['host']
            if args[:2]==('localectl','status'):return 'System Locale: LANG='+values['locale']
            if args[:2]==('timedatectl','show'):return values['timezone']
            if '--property=LoadState' in args:return 'loaded'
            if '--property=ActiveState' in args:return 'active'
            raise AssertionError('Unexpected fixture readback')

        # The real account tools use subprocess.run above; do not patch that
        # module globally. Ignore only the application's non-account commands.
        real_raw=app.subprocess.run
        real_which=shutil.which
        def raw(args,**kwargs):
            if args[0] in ('usermod','chpasswd'):
                return real_raw(args,**kwargs)
            if args[0] in ('systemctl','loginctl'):
                calls.append(tuple(args));return SimpleNamespace(returncode=0)
            return real_raw(args,**kwargs)

        with mock.patch.object(app.pwd,'getpwuid',side_effect=lambda uid:account(uid=uid)),\
             mock.patch.object(app.pwd,'getpwnam',side_effect=lambda name:account(name=name)),\
             mock.patch.object(app.shutil,'which',side_effect=lambda command:
                 real_which(command) if command in ('usermod','chpasswd','getent','id') else '/fixture/'+command),\
             mock.patch.object(app,'run',side_effect=run),mock.patch.object(app,'read_output',side_effect=output),\
             mock.patch.object(app.subprocess,'run',side_effect=raw):
            first=app.Apply(state,root)
            try:first.execute()
            except RuntimeError as error:
                if str(error)!='injected after real rename':raise
                first.recover()
            else:raise AssertionError('expected injected password failure')
            assert account(uid=1000).pw_name=='oobe-owner' and state.path('pending').exists()
            assert state.status()['retry'] is True
            data['username']='oobe-owner2';state.write('request.json',data)
            app.Apply(state,root).execute()
        assert account(uid=1000).pw_name=='oobe-owner2'
        assert not state.path('pending').exists() and not state.path('request.json').exists()
        entry=next(line for line in (etc/'shadow').read_text().splitlines() if line.startswith('oobe-owner2:'))
        saved=entry.split(':')[1]
        crypt=ctypes.CDLL('libcrypt.so.1');crypt.crypt.argtypes=[ctypes.c_char_p,ctypes.c_char_p];crypt.crypt.restype=ctypes.c_char_p
        assert hmac.compare_digest(crypt.crypt(password.encode(),saved.encode()),saved.encode())
        assert not hmac.compare_digest(crypt.crypt(b'wrong-password',saved.encode()),saved.encode())
        groups=chroot(shutil.which('id'),'-nG','oobe-owner2').split()
        assert all(name in groups for name in ('sudo','audio','video','input'))
        assert hashlib.sha256(Path('/etc/passwd').read_bytes()).hexdigest()==host_passwd
    print(json.dumps({'real_chroot_rename_retry':'pass','sha512_password_verification':'pass',
                      'hardware_groups_and_sudo':'pass','host_passwd_unchanged':True,
                      'real_systemd_locale_timezone_or_desktop':'not exercised','actual_owner_account_modified':False}))


if __name__=='__main__':main()
