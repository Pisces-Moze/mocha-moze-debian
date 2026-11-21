#!/usr/bin/env python3
"""Offline OOBE network tests with fake Gio/GLib; never opens a system bus."""
import importlib.util
import sys
import threading
import types
import unittest
from unittest import mock
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_network_module():
    if 'gi' not in sys.modules:
        class FakeError(Exception):
            pass
        def fake_variant(signature, value=None):
            return value
        glib = types.SimpleNamespace(
            Error=FakeError, Variant=fake_variant,
            source_remove=lambda *_args: False,
            timeout_add_seconds=lambda *_args: 0,
            idle_add=lambda *_args: 0)
        gio = types.SimpleNamespace(
            BusType=types.SimpleNamespace(SYSTEM=1),
            bus_get_sync=lambda *_args: None,
            DBusCallFlags=types.SimpleNamespace(NONE=0))
        gio.DBusError=types.SimpleNamespace(get_remote_error=lambda error:getattr(error,'remote_name',None))
        gi = types.ModuleType('gi')
        repository = types.ModuleType('gi.repository')
        repository.Gio = gio
        repository.GLib = glib
        gi.repository = repository
        sys.modules['gi'] = gi
        sys.modules['gi.repository'] = repository
    spec = importlib.util.spec_from_file_location('oobe_network_tested', HERE.parent/'oobe'/'mocha_oobe_network.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blank_network(module):
    network = module.Networks.__new__(module.Networks)
    network.emit = lambda *_args: None
    network.selected_device = None
    network.pending = None
    network.scan_adapter = None
    network.scanning_allowed = False
    network.last_scan = 0
    network.agent_registered = False
    network.bt_lock = threading.Lock()
    network.bt_generation = 0
    return network


class WifiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_network_module()
        cls.nm = cls.module.NM
        cls.bz = cls.module.BZ

    def test_dhcp_incomplete_is_not_connected(self):
        network = blank_network(self.module)
        values = {
            ('/wifi', self.nm+'.Device', 'State'): 100,
            ('/wifi', self.nm+'.Device', 'ActiveConnection'): '/active',
            ('/active', self.nm+'.Connection.Active', 'State'): 1,
            ('/wifi', self.nm+'.Device.Wireless', 'ActiveAccessPoint'): '/ap',
            ('/ap', self.nm+'.AccessPoint', 'Ssid'): b'home',
            ('/wifi', self.nm+'.Device', 'Ip4Config'): '/ip4',
            ('/wifi', self.nm+'.Device', 'Ip6Config'): '/',
        }
        network.wifi_device = lambda: '/wifi'
        network.get = lambda _dest, path, iface, prop: values[(path, iface, prop)]
        network._device_addresses = lambda *_args: []
        self.assertIsNone(network.wifi_connection())

    def test_existing_verified_connection_is_reused(self):
        network = blank_network(self.module)
        network.wifi_connection = lambda device=None: {
            'connected': 'home', 'ipv4': ['192.168.1.10'], 'ipv6': []}
        calls = []
        network.call = lambda *args, **kwargs: calls.append((args, kwargs))
        self.assertEqual(network.wifi_connect('home', 'password123'), {})
        self.assertEqual(network.wifi_connect('home', 'ab'*32), {})
        with self.assertRaises(ValueError):network.wifi_connect('home', 'g'*64)
        self.assertFalse(any(args[3] == 'AddAndActivateConnection' for args, _ in calls))

    def test_activated_without_address_is_rejected_but_ula_ipv6_is_usable(self):
        m=self.module;network=blank_network(m)
        values={('/wifi',m.NM+'.Device','State'):100,
                ('/wifi',m.NM+'.Device','ActiveConnection'):'/active',
                ('/active',m.NM+'.Connection.Active','State'):2,
                ('/wifi',m.NM+'.Device','Ip4Config'):'/ip4',
                ('/wifi',m.NM+'.Device','Ip6Config'):'/ip6',
                ('/ip4',m.NM+'.IP4Config','AddressData'):[],
                ('/ip6',m.NM+'.IP6Config','AddressData'):[{'address':'fe80::1','prefix':64}],
                ('/wifi',m.NM+'.Device.Wireless','ActiveAccessPoint'):'/ap',
                ('/ap',m.NM+'.AccessPoint','Ssid'):b'home'}
        network.get=lambda dest,path,iface,prop:values[(path,iface,prop)]
        self.assertIsNone(network.wifi_connection('/wifi'))
        values[('/ip6',m.NM+'.IP6Config','AddressData')]=[{'address':'fd12::10','prefix':64}]
        self.assertEqual(network.wifi_connection('/wifi')['ipv6'],['fd12::10'])

    def test_another_connection_cannot_satisfy_the_requested_ssid(self):
        m=self.module;network=blank_network(m);statuses=iter([None,{'connected':'other'}]);deleted=[]
        network.wifi_connection=lambda device=None:next(statuses)
        network.wifi_device=lambda:'/wifi'
        def get(dest,path,iface,prop):
            if prop=='Ssid':return b'home'
            if prop=='Flags':return 1
            if path=='/active' and prop=='State':return 2
            raise AssertionError((path,prop))
        def call(dest,path,iface,method,signature=None,args=(),timeout=12000):
            if method=='GetAllAccessPoints':return (['/ap'],)
            if method=='AddAndActivateConnection':return ('/new','/active')
            raise AssertionError(method)
        network.get=get;network.call=call;network._delete_wifi_profile=lambda value:deleted.append(value)
        with mock.patch.object(m.time,'monotonic',side_effect=[0,1,36]),mock.patch.object(m.time,'sleep'):
            with self.assertRaises(ValueError):network.wifi_connect('home','password123')
        self.assertEqual(len(deleted),1)

    def test_failure_deletes_only_own_uuid(self):
        network = blank_network(self.module)
        network.wifi_connection = lambda device=None: None
        network.wifi_device = lambda: '/wifi'
        captured = {}
        deleted = []
        def get(_dest, path, iface, prop):
            if (path, prop) == ('/ap', 'Ssid'):
                return b'home'
            if (path, prop) == ('/ap', 'Flags'):
                return 1
            if (path, iface) == ('/active', self.nm+'.Connection.Active') and prop == 'State':
                return 4
            raise AssertionError((path, iface, prop))
        def call(_dest, path, iface, method, signature=None, args=(), timeout=12000):
            if method == 'GetAllAccessPoints':
                return (['/ap'],)
            if method == 'AddAndActivateConnection':
                captured['uuid'] = args[0]['connection']['uuid']
                return ('/conn/new', '/active')
            if method == 'ListConnections':
                self.assertEqual((path,iface),('/org/freedesktop/NetworkManager/Settings',self.nm+'.Settings'))
                return (['/conn/other', '/conn/new'],)
            if method == 'GetSettings':
                if path == '/conn/other':
                    return ({'connection': {'uuid': 'other-uuid'}},)
                return ({'connection': {'uuid': captured['uuid']}},)
            if method == 'Delete':
                self.assertEqual((path,iface,signature,args),('/conn/new',self.nm+'.Settings.Connection',None,()))
                deleted.append(path)
                return (None,)
            raise AssertionError((path, method, args))
        network.get = get
        network.call = call
        with self.assertRaises(ValueError):
            network.wifi_connect('home', 'password123')
        self.assertEqual(deleted, ['/conn/new'])


class BluetoothTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_network_module()
        cls.bz = cls.module.BZ

    def test_connect_verifies_connected_and_services(self):
        network = blank_network(self.module)
        calls = []
        connected_reads = []
        def call(_dest, path, iface, method, signature=None, args=(), timeout=12000):
            calls.append((method, timeout))
            if method == 'GetManagedObjects':
                return ({'/dev/bt': {self.bz+'.Device1': {'Paired': False}}},)
            if method == 'RegisterAgent':
                return (None,)
            if method == 'Pair' or method == 'Connect' or method == 'Set':
                return (None,)
            if method == 'Get':
                prop = args[1]
                if prop == 'Connected':
                    connected_reads.append(timeout)
                    return (len(connected_reads) > 1,)
                if prop == 'ServicesResolved':
                    return (True,)
            raise AssertionError((path, method, args))
        network.call = call
        self.assertEqual(network.bluetooth_connect('/dev/bt', False), {})
        methods = [method for method, _ in calls]
        self.assertIn('Pair', methods)
        self.assertIn('Connect', methods)
        self.assertTrue(all(timeout is None or timeout <= 110000 for _, timeout in calls))

    def test_parallel_operation_is_rejected(self):
        network = blank_network(self.module)
        network.bt_lock.acquire()
        try:
            with self.assertRaises(ValueError):
                network.bluetooth_connect('/dev/bt', False)
        finally:
            network.bt_lock.release()

    def test_expired_deadline_prevents_another_dbus_call_and_caps_explicit_timeout(self):
        m=self.module;network=blank_network(m);network.call=mock.Mock(return_value=())
        with mock.patch.object(m.time,'monotonic',return_value=10):
            with self.assertRaises(TimeoutError):
                network._bt_call(9,m.BZ,'/dev/bt',m.BZ+'.Device1','Connect')
            network.call.assert_not_called()
            network._bt_call(11,m.BZ,'/dev/bt',m.BZ+'.Device1','Connect',timeout=5000)
        self.assertEqual(network.call.call_args.kwargs['timeout'],1000)

    def test_services_query_failure_is_not_treated_as_a_missing_property(self):
        m=self.module;network=blank_network(m)
        error=m.GLib.Error('query failed');error.remote_name='org.freedesktop.DBus.Error.AccessDenied'
        network._bt_get=mock.Mock(side_effect=error)
        with self.assertRaises(m.GLib.Error):network._bt_services_resolved(100,'/dev/bt')
        error.remote_name='org.freedesktop.DBus.Error.UnknownProperty'
        self.assertIsNone(network._bt_services_resolved(100,'/dev/bt'))

    def test_stale_pairing_cleanup_does_not_clear_newer_operation(self):
        network = blank_network(self.module)
        class Invocation:
            def return_dbus_error(self, *_args):
                raise AssertionError('old invocation must not be cancelled')
        network.pending = ('old', Invocation(), 'RequestConfirmation', 1)
        network.bt_generation = 2
        network._cleanup_pairing(1)
        self.assertIsNotNone(network.pending)
        network.pending = ('new', types.SimpleNamespace(return_dbus_error=lambda *_args: None),
                           'RequestConfirmation', 2)
        network.bt_generation = 2
        network._cleanup_pairing(2)
        self.assertIsNone(network.pending)

    def test_snapshot_lists_devices_when_discovery_is_already_running(self):
        # BlueZ InProgress (another client owns discovery) must not suppress the
        # device list; first-time pairing depends on the scan list being visible.
        m=self.module;network=blank_network(m)
        error=m.GLib.Error('in progress');error.remote_name='org.bluez.Error.InProgress'
        def call(_dest,path,iface,method,signature=None,args=(),timeout=12000):
            if method=='StartDiscovery':
                raise error
            raise AssertionError((path,iface,method,args))
        network.call=call
        def get(*_args):
            raise m.GLib.Error('wifi unavailable')
        network.get=get
        network.wifi_device=lambda: None
        adapter='/adapter';device='/dev/bt'
        network.objects=lambda:{adapter:{m.BZ+'.Adapter1':{'Powered':True}},
            device:{m.BZ+'.Device1':{'Name':'ThinkBook Mouse','Paired':True,
                                     'Connected':True,'ServicesResolved':True}}}
        network.scanning_allowed=True
        snapshot=network.snapshot()
        self.assertEqual(snapshot['bluetooth']['devices'][0]['name'],'ThinkBook Mouse')
        self.assertTrue(snapshot['bluetooth']['devices'][0]['connected'])
        self.assertIsNone(network.scan_adapter)


if __name__ == '__main__':
    unittest.main()
