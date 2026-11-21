#!/usr/bin/env python3
"""Offline capacity tests for DATA restore; no devices, streams or containers."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


@contextlib.contextmanager
def scratch():
    base=os.environ.get('MOCHA_TEST_TMPDIR')
    if base:
        path=Path(base)/('data-capacity-'+os.urandom(6).hex())
        path.mkdir(parents=True)
        try: yield path
        finally: shutil.rmtree(path,ignore_errors=True)
    else:
        with tempfile.TemporaryDirectory() as directory: yield Path(directory)


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,HERE/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def load_ram():
    sys.modules.setdefault('fcntl',types.ModuleType('fcntl'))
    return load('distribution_ram_capacity','distribution-ram.py')


class CountingBytesIO(io.BytesIO):
    def __init__(self,value):
        super().__init__(value);self.reads=0
    def read(self,*args,**kwargs):
        self.reads+=1;return super().read(*args,**kwargs)


class FakeStdin:
    def __init__(self,value):self.buffer=CountingBytesIO(value)


class CapacityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=load('build_distribution_capacity','build-distribution.py')
        cls.ram=load_ram()
        cls.flash=load('flash_distribution_capacity','flash-distribution.py')

    def test_pc_rejects_missing_or_oversize_budget_before_transport(self):
        with scratch() as directory:
            files={}
            for name in ('loader.img','uImage','mocha.dtb','installer.cpio.gz','APP.img.xz','DATA.tar.xz','LNX.img'):
                (directory/name).write_bytes(b'x')
                files[name]={'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}
            manifest={'schema':1,'device':'xiaomi-mocha-16gb','release_state':'verified',
                      'app_bytes':3*1024**3,'app_raw_sha256':'0'*64,'files':files}
            def verify():
                (directory/'bundle.json').write_text(json.dumps(manifest))
                return self.flash.verify_bundle(directory)
            with self.assertRaisesRegex(ValueError,'expanded-space'):verify()
            manifest['data_expanded_bytes']=True
            with self.assertRaisesRegex(ValueError,'expanded-space'):verify()
            manifest['data_expanded_bytes']=self.build.uda_bytes()-1
            with self.assertRaisesRegex(ValueError,'peak exceeds'):verify()
            manifest['data_expanded_bytes']=1024
            self.assertEqual(verify()['data_expanded_bytes'],1024)

    def test_expanded_estimate_rounds_blocks_counts_dirs_and_dedups_hardlinks(self):
        with scratch() as directory:
            (directory/'a').write_bytes(b'x')
            (directory/'b').write_bytes(b'y'*4097)
            os.link(directory/'a',directory/'c')
            (directory/'d').mkdir();(directory/'d/e').write_bytes(b'')
            base,margin=self.build.expanded_estimate(directory)
        self.assertEqual(base,8192+12288+4096+4096+4096)
        self.assertEqual(margin,64*1024**2)
        self.assertEqual(base+margin,67141632)

    def test_capacity_is_checked_against_fixed_uda_and_uses_same_expanded_budget(self):
        uda=self.build.uda_bytes()
        self.assertEqual(uda,23160832*512)
        plan=self.build.capacity_plan(1000,2000,uda=uda)
        self.assertEqual(plan['capacity_required_bytes'],3000+self.ram.DATA_SAFETY_BYTES)
        self.assertEqual(plan['uda_usable_bytes'],uda-uda//8)
        with self.assertRaises(RuntimeError):
            self.build.capacity_plan(uda-1,1000,uda=uda)
        base,margin=self.build.expanded_estimate(HERE)
        expanded=base+margin
        self.assertEqual(self.build.capacity_plan(123,expanded,uda=uda)['data_expanded_bytes'],expanded)

    def test_ram_space_budget_rejects_invalid_values_and_requires_peak(self):
        ram=self.ram
        for invalid in (None,-1,0,16*1024**3):
            with self.assertRaises(ValueError):ram.validate_expanded_bytes(invalid)
        required=ram.required_data_space(1000,2000)
        self.assertEqual(required,1000+2000+ram.DATA_SAFETY_BYTES)
        ram.check_data_space(required,1000,2000)
        with self.assertRaises(RuntimeError):ram.check_data_space(required-1,1000,2000)

    def _restore(self,directory,available,payload,expanded):
        ram=self.ram
        state=directory/'state.json';state.write_text(json.dumps({'phase':'app-verified'}))
        mount=directory/'mnt';mount.mkdir()
        calls=[];stdin=FakeStdin(payload)
        self.last_stdin=stdin;self.last_calls=calls
        def fake_run(*args):calls.append(args)
        args=SimpleNamespace(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),
                             expanded_bytes=expanded)
        with mock.patch.object(ram,'STATE',state),mock.patch.object(ram,'DATA_MOUNT',mount),\
             mock.patch.object(ram,'guard',lambda:None),mock.patch.object(ram,'run',fake_run),\
             mock.patch.object(ram,'writable',lambda:None),mock.patch.object(ram,'readonly',lambda:None),\
             mock.patch.object(ram.os,'statvfs',create=True,
                               return_value=SimpleNamespace(f_bavail=available,f_frsize=1)),\
             mock.patch.object(ram.os,'sync',new=lambda:None,create=True),\
             mock.patch.object(sys,'stdin',stdin):
            ram.restore_data(args)
        return state,mount,calls,stdin

    def test_restore_refuses_before_reading_when_space_is_insufficient(self):
        ram=self.ram;payload=b'archive-data';expanded=4096*1024
        with scratch() as directory:
            required=ram.required_data_space(len(payload),expanded)
            with self.assertRaises(RuntimeError):
                self._restore(directory,required-1,payload,expanded)
            self.assertFalse((directory/'mnt/.distribution-data.tar.xz').exists())
            self.assertEqual(self.last_stdin.buffer.reads,0)
            self.assertFalse(any(call[0]=='tar' for call in self.last_calls))

    def test_restore_passes_and_advances_phase_when_space_is_sufficient(self):
        ram=self.ram;payload=b'archive-data';expanded=4096*1024
        with scratch() as directory:
            required=ram.required_data_space(len(payload),expanded)
            state,mount,calls,stdin=self._restore(directory,required,payload,expanded)
            self.assertEqual(json.loads(state.read_text())['phase'],'data-verified')
            self.assertFalse((mount/'.distribution-data.tar.xz').exists())
            self.assertTrue(any(call[0]=='tar' for call in calls))
            self.assertGreater(stdin.buffer.reads,0)

    def test_restore_rejects_invalid_expanded_budget_before_mounting(self):
        ram=self.ram
        with scratch() as directory:
            with self.assertRaises(ValueError):
                self._restore(directory,10**12,b'x',0)


if __name__=='__main__':
    unittest.main()
