#!/usr/bin/python3
"""NetworkManager/BlueZ bridge. No shell commands or credentials in argv."""
import ipaddress
import re
import threading
import time
import uuid
from gi.repository import Gio, GLib

NM = 'org.freedesktop.NetworkManager'
NMP = '/org/freedesktop/NetworkManager'
NMS = NMP + '/Settings'
BZ = 'org.bluez'
PROPS = 'org.freedesktop.DBus.Properties'
AGENT = '/org/mocha/OobeAgent'
NM_DEVICE_STATE_ACTIVATED = 100
NM_ACTIVE_CONNECTION_STATE_ACTIVATED = 2
BT_DEADLINE = 105.0  # leave five seconds for bounded cancellation below
AGENT_XML = '''<node><interface name="org.bluez.Agent1">
<method name="Release"/><method name="Cancel"/>
<method name="DisplayPinCode"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
<method name="DisplayPasskey"><arg type="o" direction="in"/><arg type="u" direction="in"/><arg type="q" direction="in"/></method>
<method name="RequestPinCode"><arg type="o" direction="in"/><arg type="s" direction="out"/></method>
<method name="RequestPasskey"><arg type="o" direction="in"/><arg type="u" direction="out"/></method>
<method name="RequestConfirmation"><arg type="o" direction="in"/><arg type="u" direction="in"/></method>
<method name="RequestAuthorization"><arg type="o" direction="in"/></method>
<method name="AuthorizeService"><arg type="o" direction="in"/><arg type="s" direction="in"/></method>
</interface></node>'''


def _variant_value(value):
    return value.unpack() if hasattr(value, 'unpack') else value


def _address_entries(data):
    """Normalize NM AddressData (aa{sv}) or legacy aau into (address, prefix)."""
    result = []
    if not isinstance(data, (list, tuple)):
        return result
    for item in data:
        if isinstance(item, dict):
            address = _variant_value(item.get('address', ''))
            prefix = _variant_value(item.get('prefix', 0))
            result.append((str(address), int(prefix or 0)))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            address = _variant_value(item[0])
            prefix = _variant_value(item[1])
            if isinstance(address, int):
                address = str(ipaddress.IPv4Address(address))
            result.append((str(address), int(prefix or 0)))
    return result


def _usable_ipv4(address, prefix):
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return (ip.version == 4 and 0 < prefix <= 32 and not ip.is_unspecified
            and not ip.is_loopback and not ip.is_link_local and not ip.is_multicast)


def _usable_ipv6(address, prefix):
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if ip.version != 6 or not 0 < prefix <= 128:
        return False
    if ip.is_unspecified or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return False
    return ip.is_global or ip in ipaddress.ip_network('fc00::/7')



class Networks:
    def __init__(self, emit):
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.emit = emit
        self.selected_device = None
        self.pending = None
        self.scan_adapter = None
        self.scanning_allowed = False
        self.last_scan = 0
        self.bt_lock = threading.Lock()
        self.bt_generation = 0
        self.registration = self.bus.register_object(
            AGENT, Gio.DBusNodeInfo.new_for_xml(AGENT_XML).interfaces[0], self.agent, None, None)
        self.agent_registered = False

    def call(self, destination, path, interface, method, signature=None, args=(), timeout=12000):
        result = self.bus.call_sync(destination, path, interface, method,
                                    GLib.Variant(signature, args) if signature else None,
                                    None, Gio.DBusCallFlags.NONE, timeout, None)
        return result.unpack()

    def get(self, dest, path, interface, prop):
        return self.call(dest, path, PROPS, 'Get', '(ss)', (interface, prop))[0]

    def set(self, dest, path, interface, prop, value):
        return self.call(dest, path, PROPS, 'Set', '(ssv)', (interface, prop, value))

    def objects(self):
        return self.call(BZ, '/', 'org.freedesktop.DBus.ObjectManager', 'GetManagedObjects')[0]

    def adapter(self):
        return next((p for p, values in self.objects().items() if BZ+'.Adapter1' in values), None)

    def wifi_device(self):
        devices = self.call(NM, NMP, NM, 'GetDevices')[0]
        return next((p for p in devices if self.get(NM, p, NM+'.Device', 'DeviceType') == 2), None)

    def _device_addresses(self, device, config_property, interface, family):
        try:
            path = self.get(NM, device, NM+'.Device', config_property)
            if not path or path == '/':
                return []
            data = self.get(NM, path, interface, 'AddressData')
        except GLib.Error:
            return []
        usable = _usable_ipv4 if family == 4 else _usable_ipv6
        return [address for address, prefix in _address_entries(data)
                if usable(address, prefix)]

    def wifi_connection(self, device=None):
        """Return a validated Wi-Fi connection; never infer it from the AP alone."""
        device = device or self.wifi_device()
        if not device:
            return None
        try:
            if int(self.get(NM, device, NM+'.Device', 'State')) != NM_DEVICE_STATE_ACTIVATED:
                return None
            active = self.get(NM, device, NM+'.Device', 'ActiveConnection')
            if not active or active == '/':
                return None
            if int(self.get(NM, active, NM+'.Connection.Active', 'State')) != NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
                return None
            ipv4 = self._device_addresses(device, 'Ip4Config', NM+'.IP4Config', 4)
            ipv6 = self._device_addresses(device, 'Ip6Config', NM+'.IP6Config', 6)
            if not ipv4 and not ipv6:
                return None
            active_ap = self.get(NM, device, NM+'.Device.Wireless', 'ActiveAccessPoint')
            if not active_ap or active_ap == '/':
                return None
            raw_ssid = self.get(NM, active_ap, NM+'.AccessPoint', 'Ssid')
            try:
                ssid = bytes(_variant_value(raw_ssid)).decode('utf-8')
            except (TypeError, UnicodeError):
                return None
            if not ssid:
                return None
            return {'connected': ssid, 'ipv4': ipv4, 'ipv6': ipv6}
        except (GLib.Error, TypeError, ValueError):
            return None

    def _delete_wifi_profile(self, connection_uuid):
        """Delete only the profile created by the failed attempt (UUID match)."""
        try:
            paths = self.call(NM, NMS, NM+'.Settings', 'ListConnections')[0]
        except GLib.Error:
            return
        for path in paths or []:
            try:
                settings = self.call(NM, path, NM+'.Settings.Connection', 'GetSettings')[0]
            except GLib.Error:
                continue
            connection = settings.get('connection', {}) if isinstance(settings, dict) else {}
            if _variant_value(connection.get('uuid')) != connection_uuid:
                continue
            try:
                self.call(NM, path, NM+'.Settings.Connection', 'Delete')
            except GLib.Error:
                pass
            return

    def snapshot(self):
        wifi = {'on': False, 'available': False, 'connected': None, 'networks': [], 'ipv4': [], 'ipv6': []}
        bluetooth = {'on': False, 'devices': []}
        # One unavailable radio must not prevent using the other radio.
        try:
            wifi['on'] = bool(self.get(NM, NMP, NM, 'WirelessEnabled'))
            device = self.wifi_device()
            wifi['available'] = bool(device)
            status = self.wifi_connection(device) if device else None
            if status:
                wifi['connected'] = status['connected']
                wifi['ipv4'] = status['ipv4']
                wifi['ipv6'] = status['ipv6']
            if device and wifi['on']:
                wireless = NM+'.Device.Wireless'
                if time.monotonic()-self.last_scan > 20:
                    self.last_scan = time.monotonic()
                    try:
                        self.call(NM, device, wireless, 'RequestScan', '(a{sv})', ({},))
                    except GLib.Error:
                        pass  # NM may throttle scans; cached results remain valid.
                by_ssid = {}
                for path in self.call(NM, device, wireless, 'GetAllAccessPoints')[0]:
                    ap = self.call(NM, path, PROPS, 'GetAll', '(s)', (NM+'.AccessPoint',))[0]
                    raw = bytes(ap['Ssid'])
                    try:
                        ssid = raw.decode('utf-8')
                    except UnicodeError:
                        continue
                    if not ssid:
                        continue
                    entry = {'ssid': ssid, 'secured': bool(ap['Flags'] & 1),
                             'strength': max(1, min(3, (int(ap['Strength'])+32)//33))}
                    if ssid not in by_ssid or entry['strength'] > by_ssid[ssid]['strength']:
                        by_ssid[ssid] = entry
                wifi['networks'] = sorted(by_ssid.values(), key=lambda n: -n['strength'])[:32]
        except GLib.Error:
            pass
        try:
            objects = self.objects()
            adapter = next((p for p, v in objects.items() if BZ+'.Adapter1' in v), None)
            bluetooth['on'] = bool(adapter and objects[adapter][BZ+'.Adapter1']['Powered'])
            if bluetooth['on']:
                if self.scanning_allowed and not self.scan_adapter:
                    try:
                        self.call(BZ, adapter, BZ+'.Adapter1', 'StartDiscovery')
                        self.scan_adapter = adapter
                    except GLib.Error:
                        # BlueZ returns InProgress when another client already
                        # owns discovery. That must not hide the device list:
                        # keep reading the object manager and retry next snapshot.
                        pass
                    if not self.scanning_allowed:
                        self.stop_scan()
                for path, values in objects.items():
                    device = values.get(BZ+'.Device1')
                    if not device or not device.get('Name'):
                        continue
                    name = device.get('Alias', device['Name'])
                    bluetooth['devices'].append({'id': path, 'name': name,
                        'type': '已配对' if device.get('Paired') else '蓝牙设备',
                        'initial': name[:1], 'connected': bool(device.get('Connected')) and
                        bool(device.get('ServicesResolved', True))})
                bluetooth['devices'] = bluetooth['devices'][:32]
        except GLib.Error:
            pass
        return {'wifi': wifi, 'bluetooth': bluetooth}

    def stop_scan(self):
        self.scanning_allowed = False
        if self.scan_adapter:
            adapter, self.scan_adapter = self.scan_adapter, None
            try:
                self.call(BZ, adapter, BZ+'.Adapter1', 'StopDiscovery')
            except GLib.Error:
                pass
        return {}

    def start_scan(self):
        self.scanning_allowed = True
        return {}

    def radio(self, radio, on):
        if type(on) is not bool or radio not in ('wifi', 'bluetooth'):
            raise ValueError('Invalid radio')
        if radio == 'wifi':
            self.set(NM, NMP, NM, 'WirelessEnabled', GLib.Variant('b', on))
        else:
            adapter = self.adapter()
            if not adapter:
                raise ValueError('No Bluetooth adapter')
            if not on:
                self.stop_scan()
            self.set(BZ, adapter, BZ+'.Adapter1', 'Powered', GLib.Variant('b', on))
        return {}

    def wifi_connect(self, ssid, password):
        if not isinstance(ssid, str) or not 1 <= len(ssid.encode()) <= 32:
            raise ValueError('Invalid SSID')
        # WPA-PSK permits either an 8-63 character passphrase or the raw
        # 256-bit key encoded as 64 hexadecimal characters (NM may store it).
        if not isinstance(password, str) or (len(password) > 63 and
                not re.fullmatch(r'[0-9a-fA-F]{64}', password)):
            raise ValueError('Invalid Wi-Fi password')
        current = self.wifi_connection()
        if current and current['connected'] == ssid:
            return {}
        device = self.wifi_device()
        if not device:
            raise ValueError('No Wi-Fi adapter')
        access_point = None
        for path in self.call(NM, device, NM+'.Device.Wireless', 'GetAllAccessPoints')[0]:
            if bytes(self.get(NM, path, NM+'.AccessPoint', 'Ssid')) == ssid.encode():
                access_point = path
                break
        if access_point is None:
            raise ValueError('Network disappeared')
        v = GLib.Variant
        connection_uuid = str(uuid.uuid4())
        settings = {
            'connection': {'id': v('s', ssid), 'uuid': v('s', connection_uuid),
                           'type': v('s', '802-11-wireless'), 'autoconnect': v('b', True)},
            '802-11-wireless': {'ssid': v('ay', ssid.encode()), 'mode': v('s', 'infrastructure')},
            'ipv4': {'method': v('s', 'auto')}, 'ipv6': {'method': v('s', 'auto')}}
        if self.get(NM, access_point, NM+'.AccessPoint', 'Flags') & 1:
            if len(password) < 8:
                raise ValueError('Password required')
            settings['802-11-wireless-security'] = {'key-mgmt': v('s', 'wpa-psk'), 'psk': v('s', password)}
        try:
            result = self.call(NM, NMP, NM, 'AddAndActivateConnection',
                               '(a{sa{sv}}oo)', (settings, device, access_point), timeout=35000)
            active = result[1]
            deadline = time.monotonic()+35
            while time.monotonic() < deadline:
                status = self.get(NM, active, NM+'.Connection.Active', 'State')
                if status == NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
                    observed = self.wifi_connection(device)
                    if observed and observed['connected'] == ssid and self.get(
                            NM, device, NM+'.Device', 'ActiveConnection') == active:
                        return {}
                elif status in (3, 4):
                    break
                time.sleep(.5)
            raise ValueError('Connection not activated with a usable IP address')
        except BaseException:
            # Only the UUID created above is removed; existing profiles stay.
            self._delete_wifi_profile(connection_uuid)
            raise
        finally:
            password = ''
            settings.clear()

    def _bt_timeout(self, deadline):
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Bluetooth operation timed out')
        return max(1, int(remaining*1000))

    def _bt_call(self, deadline, destination, path, interface, method,
                 signature=None, args=(), timeout=None):
        remaining = self._bt_timeout(deadline)
        return self.call(destination, path, interface, method, signature, args,
                         timeout=min(timeout, remaining) if timeout is not None else remaining)

    def _bt_get(self, deadline, device, prop):
        return self._bt_call(deadline, BZ, device, PROPS, 'Get', '(ss)',
                             (BZ+'.Device1', prop))[0]

    def _bt_set(self, deadline, device, prop, value):
        return self._bt_call(deadline, BZ, device, PROPS, 'Set', '(ssv)',
                             (BZ+'.Device1', prop, value))

    def _bt_objects(self, deadline):
        return self._bt_call(deadline, BZ, '/', 'org.freedesktop.DBus.ObjectManager',
                             'GetManagedObjects')[0]

    def _bt_services_resolved(self, deadline, device):
        try:
            return bool(_variant_value(self._bt_get(deadline, device, 'ServicesResolved')))
        except GLib.Error as error:
            if Gio.DBusError.get_remote_error(error) == 'org.freedesktop.DBus.Error.UnknownProperty':
                return None
            raise

    def _bt_wait(self, deadline, device, want_connected):
        confirmations = 0
        while True:
            if time.monotonic() >= deadline:
                return False
            connected = bool(_variant_value(self._bt_get(deadline, device, 'Connected')))
            confirmed = connected == want_connected
            if confirmed and want_connected:
                services = self._bt_services_resolved(deadline, device)
                confirmed = services is None or services
            if confirmed:
                confirmations += 1
                if confirmations >= 2:
                    return True
            else:
                confirmations = 0
            time.sleep(min(.25, max(0.0, deadline-time.monotonic())))

    def _bt_cancel_pairing(self, device):
        deadline = time.monotonic()+5
        try:
            self._bt_call(deadline, BZ, device, BZ+'.Device1', 'CancelPairing')
        except (GLib.Error, TimeoutError):
            pass

    def _cleanup_pairing(self, generation):
        if generation != self.bt_generation:
            return False
        self.cancel_pairing()
        return False

    def bluetooth_connect(self, device, disconnect):
        if type(disconnect) is not bool:
            raise ValueError('Invalid disconnect')
        if not self.bt_lock.acquire(False):
            raise ValueError('Bluetooth operation already in progress')
        try:
            self.bt_generation += 1
            generation = self.bt_generation
            deadline = time.monotonic()+BT_DEADLINE
            objects = self._bt_objects(deadline)
            if not isinstance(device, str) or BZ+'.Device1' not in objects.get(device, {}):
                raise ValueError('Unknown device')
            if disconnect:
                self._bt_call(deadline, BZ, device, BZ+'.Device1', 'Disconnect')
                if not self._bt_wait(deadline, device, False):
                    raise ValueError('Bluetooth disconnect not confirmed')
                return {}
            self.selected_device = device
            try:
                if not bool(_variant_value(objects[device][BZ+'.Device1'].get('Paired'))):
                    if not self.agent_registered:
                        self._bt_call(deadline, BZ, '/org/bluez', BZ+'.AgentManager1',
                                      'RegisterAgent', '(os)', (AGENT, 'KeyboardDisplay'))
                        self.agent_registered = True
                    try:
                        self._bt_call(deadline, BZ, device, BZ+'.Device1', 'Pair')
                    except BaseException:
                        self._bt_cancel_pairing(device)
                        raise
                self._bt_set(deadline, device, 'Trusted', GLib.Variant('b', True))
                if not bool(_variant_value(self._bt_get(deadline, device, 'Connected'))):
                    self._bt_call(deadline, BZ, device, BZ+'.Device1', 'Connect')
                if not self._bt_wait(deadline, device, True):
                    raise ValueError('Bluetooth connection not confirmed')
                return {}
            finally:
                self.selected_device = None
                GLib.idle_add(self._cleanup_pairing, generation)
        finally:
            self.bt_lock.release()

    def cancel_pairing(self):
        if self.pending:
            _, invocation, _, timer = self.pending
            self.pending = None
            GLib.source_remove(timer)
            invocation.return_dbus_error('org.bluez.Error.Canceled', 'Pairing ended')
        self.emit('pairing-clear', {})
        return False

    def agent(self, bus, sender, path, interface, method, parameters, invocation):
        # Only the actual system BlueZ owner may call this local agent.
        owner = self.call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                          'org.freedesktop.DBus', 'GetNameOwner', '(s)', (BZ,))[0]
        args = parameters.unpack()
        if sender != owner:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Unexpected caller')
        elif method in ('Cancel', 'Release'):
            self.cancel_pairing()
            invocation.return_value(None)
        elif not args or args[0] != self.selected_device:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'No selected device')
        elif method in ('DisplayPinCode', 'DisplayPasskey'):
            code = str(args[1]) if method == 'DisplayPinCode' else f'{args[1]:06d}'
            self.emit('pairing-code', {'code': code})
            invocation.return_value(None)
        elif method in ('RequestPinCode', 'RequestPasskey', 'RequestConfirmation',
                        'RequestAuthorization', 'AuthorizeService'):
            self.cancel_pairing()
            token = uuid.uuid4().hex
            timer = GLib.timeout_add_seconds(60, self._cleanup_pairing, self.bt_generation)
            self.pending = (token, invocation, method, timer)
            self.emit('pairing-request', {'token': token, 'method': method,
                      'code': f'{args[1]:06d}' if method == 'RequestConfirmation' else ''})
        else:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Unsupported request')

    def pairing_reply(self, token, value):
        if not self.pending or self.pending[0] != token:
            raise ValueError('Pairing expired')
        _, invocation, method, timer = self.pending
        self.pending = None
        GLib.source_remove(timer)
        if value is False:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Declined')
        elif method == 'RequestPinCode' and isinstance(value, str) and 1 <= len(value) <= 16:
            invocation.return_value(GLib.Variant('(s)', (value,)))
        elif method == 'RequestPasskey' and isinstance(value, str) and value.isascii() and value.isdigit() and len(value) <= 6:
            invocation.return_value(GLib.Variant('(u)', (int(value),)))
        elif method not in ('RequestPinCode', 'RequestPasskey') and value is True:
            invocation.return_value(None)
        else:
            invocation.return_dbus_error('org.bluez.Error.Rejected', 'Invalid answer')
        self.emit('pairing-clear', {})
        return {}
