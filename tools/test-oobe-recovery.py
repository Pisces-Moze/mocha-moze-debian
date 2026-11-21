#!/usr/bin/env python3
"""Fault-injection tests. Never alters accounts, passwords, services or radios."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest import mock

OOBE=Path(__file__).resolve().parent.parent/'oobe'
sys.path.insert(0,str(OOBE))
from mocha_oobe_state import SetupState, atomic


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,OOBE/file)
    module=importlib.util.module_from_spec(spec)
    if os.name=='nt':
        pwd=ModuleType('pwd');pwd.getpwuid=lambda _:None;pwd.getpwnam=lambda _:None
        with mock.patch.dict(sys.modules,{'pwd':pwd}):spec.loader.exec_module(module)
    else:spec.loader.exec_module(module)
    return module


apply=load('oobe_apply_recovery','mocha-oobe-apply.py')
backend=load('oobe_backend_recovery','mocha-oobe-backend.py')
REQUEST={'username':'alice','hostname':'my-tablet','locale':'zh_CN.UTF-8',
         'timezone':'Asia/Shanghai','password_hash':'$6$fixture$notARealPasswordHash'}


class Fixture:
    def __init__(self,root):
        self.root=Path(root);self.state=SetupState(self.root/'state');self.state.directory.mkdir()
        self.state.path('pending').touch();self.state.write('request.json',REQUEST)
        self.name='mocha';self.password=None;self.host='mocha';self.locale='C.UTF-8';self.zone='UTC'
        self.calls=[];self.fail=None;self.target_loaded=True;self.niri_ready=True
        for rel,text in {'etc/hosts':'127.0.1.1 mocha\n',
                         'etc/systemd/system/mocha-oobe-session.service':'[Service]\nUser=mocha\n',
                         'etc/polkit-1/rules.d/49-mocha-oobe-network.rules':'subject.user !== "mocha"',
                         'usr/local/libexec/helper':"pwd.getpwnam('mocha')\n"}.items():
            p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)

    def account(self,name):
        if name!=self.name:raise KeyError(name)
        return SimpleNamespace(pw_name=self.name,pw_uid=1000,pw_dir='/home/canonical')

    def run(self,*args,**kwargs):
        self.calls.append(args)
        if self.fail and self.fail(args):raise RuntimeError('injected operation failure')
        if args[:2]==('usermod','--login'):self.name=args[2]
        if args[:2]==('chpasswd','--encrypted'):self.password=kwargs['input'].split(':',1)[1].strip()
        if args[:2]==('hostnamectl','set-hostname'):self.host=args[2]
        if args[:2]==('localectl','set-locale'):self.locale=args[2].split('=',1)[1]
        if args[:2]==('timedatectl','set-timezone'):self.zone=args[2]
        return SimpleNamespace(returncode=0)

    def output(self,*args):
        if args==('locale','-a'):return 'C.utf8\nzh_CN.utf8\nen_US.utf8'
        if args[:2]==('getent','shadow'):return self.name+':'+str(self.password)+':0::::::'
        if args[:2]==('id','-nG'):return self.name+' sudo audio video input'
        if args==('hostnamectl','--static'):return self.host
        if args[:2]==('timedatectl','show'):return self.zone
        if args[:2]==('localectl','status'):return 'System Locale: LANG='+self.locale
        if '--property=LoadState' in args:return 'loaded' if self.target_loaded else 'not-found'
        if '--property=ActiveState' in args:return 'active'
        raise AssertionError('Unexpected readback '+repr(args))

    def raw_run(self,args,**kwargs):
        self.calls.append(tuple(args))
        return SimpleNamespace(returncode=0 if 'niri.service' not in args or self.niri_ready else 1)

    @contextlib.contextmanager
    def patched(self):
        with mock.patch.object(apply.pwd,'getpwuid',lambda _:self.account(self.name)),\
             mock.patch.object(apply.pwd,'getpwnam',self.account),\
             mock.patch.object(apply.shutil,'which',lambda _:True),\
             mock.patch.object(apply,'run',self.run),\
             mock.patch.object(apply,'read_output',self.output),\
             mock.patch.object(apply.subprocess,'run',self.raw_run):
            yield apply.Apply(self.state,self.root)


class RecoveryTests(unittest.TestCase):
    def test_failed_atomic_replace_keeps_old_state_and_cleans_unique_temporary(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'request.json';p.write_text('old');(Path(d)/'request.json.new').write_text('stale')
            atomic(p,'new')
            self.assertEqual(p.read_text(),'new')
            with mock.patch('mocha_oobe_state.os.replace',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):atomic(p,'incomplete')
            self.assertEqual(p.read_text(),'new')
            self.assertEqual(sorted(x.name for x in Path(d).iterdir()),['request.json','request.json.new'])

    def test_partial_rename_recovers_ui_then_retry_rewrites_all_historical_aliases(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);f.fail=lambda a:a[0]=='chpasswd'
            with f.patched() as app:
                with self.assertRaises(RuntimeError):app.execute()
                app.recover()
            self.assertEqual(f.name,'alice')
            self.assertTrue(f.state.path('pending').exists())
            self.assertEqual(f.state.status()['phase'],'failed')
            public=json.dumps(f.state.status())
            self.assertNotIn('password_hash',public);self.assertNotIn(REQUEST['password_hash'],public)
            self.assertIn('User=alice',(f.root/'run/systemd/system/mocha-oobe-session.service.d/90-recovery-user.conf').read_text())
            request=dict(REQUEST,username='bob');f.state.write('request.json',request);f.fail=None
            with f.patched() as app:app.execute()
            self.assertEqual(f.name,'bob');self.assertFalse(f.state.path('pending').exists())
            self.assertFalse(f.state.path('request.json').exists())
            self.assertIn('User=bob',(f.root/'etc/systemd/system/mocha-oobe-session.service').read_text())
            self.assertIn("pwd.getpwnam('bob')",(f.root/'usr/local/libexec/helper').read_text())
            self.assertEqual(f.state.read('progress.json')['aliases'],['alice','bob','mocha'])

    def test_desktop_failure_preserves_request_and_reopens_setup_instead_of_committing(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);f.fail=lambda a:a[:3]==('systemctl','start','mocha-desktop.service')
            with f.patched() as app:
                with self.assertRaises(RuntimeError):app.execute()
                app.recover()
            for name in ('pending','request.json'):self.assertTrue(f.state.path(name).exists())
            for name in ('complete.json','handoff-ready.json'):self.assertFalse(f.state.path(name).exists())
            self.assertIn(('systemctl','restart','--no-block','mocha-oobe-backend.service','mocha-oobe-session.service'),f.calls)

    def test_crash_after_configuration_resumes_handoff_without_reinstalling_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d)
            with f.patched() as app,mock.patch.object(app,'handoff',side_effect=SystemExit('power loss')):
                with self.assertRaises(SystemExit):app.execute()
            self.assertTrue(f.state.path('pending').exists());self.assertTrue(f.state.path('handoff-ready.json').exists())
            f.calls.clear()
            with f.patched() as app:app.execute()
            self.assertFalse(any(call[0] in ('usermod','chpasswd') for call in f.calls))
            self.assertFalse(f.state.path('pending').exists())

    def test_changed_request_cannot_reuse_a_stale_ready_marker(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);f.name='alice'
            f.state.write('handoff-ready.json',{'request_sha256':'0'*64})
            with f.patched() as app:
                with self.assertRaisesRegex(ValueError,'does not match'):app.execute()
            self.assertTrue(f.state.path('pending').exists())

    def test_successful_commands_with_wrong_readback_do_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);actual=f.output
            with f.patched() as app,mock.patch.object(apply,'read_output',
                side_effect=lambda *a:'wrong-host' if a==('hostnamectl','--static') else actual(*a)):
                with self.assertRaisesRegex(RuntimeError,'Hostname verification'):app.execute()
            self.assertFalse(f.state.path('complete.json').exists());self.assertTrue(f.state.path('pending').exists())

    def test_getty_active_without_niri_is_not_a_completed_desktop(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);f.target_loaded=False;f.niri_ready=False
            with f.patched() as app,mock.patch.object(apply.time,'monotonic',side_effect=[0,0,31]),\
                 mock.patch.object(apply.time,'sleep'):
                with self.assertRaisesRegex(RuntimeError,'Desktop did not'):app.execute()
            self.assertTrue(f.state.path('pending').exists());self.assertFalse(f.state.path('complete.json').exists())

    def test_committed_desktop_is_not_torn_down_on_cleanup_flush_failure(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d)
            with f.patched() as app,mock.patch.object(apply,'STATE',f.state.directory),\
                 mock.patch.object(apply.os,'geteuid',return_value=0,create=True),\
                 mock.patch.object(apply,'Apply',return_value=app),\
                 mock.patch.object(sys,'argv',['mocha-oobe-apply.py']),\
                 mock.patch.object(apply,'sync_dir',side_effect=OSError('flush failed')),\
                 mock.patch.object(app,'recover') as recover,contextlib.redirect_stdout(io.StringIO()):
                apply.main();recover.assert_not_called()
            self.assertTrue(app.committed);self.assertFalse(f.state.path('pending').exists())

    def test_separate_failure_handler_stops_a_partially_started_desktop(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);f.name='alice'
            f.state.write('handoff-ready.json',{'request_sha256':'interrupted'})
            with f.patched() as app:app.recover()
            self.assertIn(('systemctl','stop','mocha-desktop.service'),f.calls)
            self.assertEqual(f.state.read('progress.json')['phase'],'failed')
            self.assertFalse(f.state.path('handoff-ready.json').exists())


class Client:
    def __init__(self,request,broken_ack=False):
        self.data=(json.dumps(request)+'\n').encode();self.sent=[];self.broken_ack=broken_ack
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def settimeout(self,*a):pass
    def getsockopt(self,*a):return struct.pack('3i',123,1000,1000)
    def recv(self,*a):data,self.data=self.data,b'';return data
    def sendall(self,data):
        if self.broken_ack:raise BrokenPipeError()
        self.sent.append(json.loads(data))


class Server:
    def __init__(self,client):self.client=client;self.accepts=0
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def bind(self,path):Path(path).touch()
    def listen(self,*a):pass
    def accept(self):
        self.accepts+=1
        if self.accepts>1:raise StopIteration()
        return self.client,None


class BackendTests(unittest.TestCase):
    def execute(self,f,client,run):
        server=Server(client)
        with mock.patch.object(backend,'STATE',f.state.directory),\
             mock.patch.object(backend,'SOCKET',str(f.root/'socket')),\
             mock.patch.object(backend.os,'geteuid',return_value=0,create=True),\
             mock.patch.object(backend.os,'chown',create=True),\
             mock.patch.object(backend.pwd,'getpwnam',f.account),\
             mock.patch.object(backend.socket,'socket',return_value=server),\
             mock.patch.object(backend.socket,'AF_UNIX',1,create=True),\
             mock.patch.object(backend.socket,'SO_PEERCRED',17,create=True),\
             mock.patch.object(backend.subprocess,'run',side_effect=run):
            try:backend.main()
            except StopIteration:pass
        return server

    def test_failed_request_does_not_autoreplay_and_status_never_exposes_hash(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);f.state.checkpoint('failed',('mocha',))
            client=Client({'action':'status'})
            self.execute(f,client,lambda *a,**k:self.fail('must not queue apply'))
            self.assertTrue(client.sent[0]['data']['retry'])
            self.assertNotIn('password_hash',json.dumps(client.sent));self.assertNotIn(REQUEST['password_hash'],json.dumps(client.sent))

    def test_missing_hasher_keeps_listener_available_for_retry(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);f.state.path('request.json').unlink()
            req={k:v for k,v in REQUEST.items() if k!='password_hash'};req['password']='test-only-password'
            client=Client(req)
            def missing(*a,**k):raise FileNotFoundError('openssl')
            server=self.execute(f,client,missing)
            self.assertEqual(server.accepts,2);self.assertFalse(client.sent[0]['ok'])
            self.assertNotIn(req['password'],json.dumps(client.sent))

    def test_lost_ack_after_queued_apply_never_accepts_another_transaction(self):
        with tempfile.TemporaryDirectory() as d:
            f=Fixture(d);f.state.path('request.json').unlink();calls=[]
            req={k:v for k,v in REQUEST.items() if k!='password_hash'};req['password']='test-only-password'
            def run(args,**kwargs):
                calls.append(args)
                return SimpleNamespace(stdout=REQUEST['password_hash'])
            server=self.execute(f,Client(req,broken_ack=True),run)
            self.assertEqual(server.accepts,1)
            self.assertEqual(f.state.read('progress.json')['phase'],'accepted')
            self.assertEqual(sum('mocha-oobe-apply.service' in a for a in calls),1)


if __name__=='__main__':unittest.main()
