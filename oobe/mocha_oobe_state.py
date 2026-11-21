#!/usr/bin/python3
"""Durable first-run state; no password or hash in progress or UI status."""
import json
import os
from pathlib import Path
import re
import tempfile

STATE = Path('/var/lib/mocha-oobe')
LOCALES = ('zh_CN.UTF-8', 'en_US.UTF-8')
TIMEZONES = ('Asia/Shanghai', 'UTC', 'Europe/London', 'America/New_York', 'Asia/Tokyo')
RESERVED = {'root', 'daemon', 'nobody', 'systemd', '_mocha-setup'}


def valid_name(value):
    return isinstance(value, str) and bool(re.fullmatch('[a-z][a-z0-9_-]{0,30}', value)) and value not in RESERVED


def validate_choices(data):
    if not valid_name(data.get('username')):
        raise ValueError('Invalid username')
    if not isinstance(data.get('hostname'), str) or not re.fullmatch(
            '[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', data['hostname']):
        raise ValueError('Invalid hostname')
    if data.get('locale') not in LOCALES or data.get('timezone') not in TIMEZONES:
        raise ValueError('Unsupported locale or timezone')


def sync_dir(path):
    if os.name != 'posix':
        return  # The production backend runs on Linux; fixtures can run on PC.
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic(path, text, mode=0o600):
    """Unique temp name and durable replacement; stale .new files cannot block retries."""
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        if hasattr(os, 'fchmod'):
            os.fchmod(fd, mode)
        else:
            os.chmod(temporary, mode)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            fd = None
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        Path(temporary).unlink(missing_ok=True)


class SetupState:
    def __init__(self, directory=STATE):
        self.directory = Path(directory)

    def path(self, name):
        return self.directory / name

    def read(self, name, default=None):
        try:
            return json.loads(self.path(name).read_text(encoding='utf-8'))
        except FileNotFoundError:
            return default

    def write(self, name, data):
        atomic(self.path(name), json.dumps(data, ensure_ascii=True) + '\n')

    def checkpoint(self, phase, names=(), error=None):
        previous = self.read('progress.json', {})
        aliases = previous.get('aliases', [])
        if not isinstance(aliases, list) or not all(valid_name(name) for name in aliases):
            raise ValueError('Invalid identity journal')
        aliases = sorted(set(aliases) | set(names))
        if not all(valid_name(name) for name in aliases):
            raise ValueError('Invalid identity journal')
        progress = {'schema': 1, 'phase': phase, 'aliases': aliases}
        if error:
            progress['error'] = error  # Fixed code supplied by caller, not exception text.
        self.write('progress.json', progress)
        return progress

    def status(self):
        progress = self.read('progress.json', {})
        failed = progress.get('phase') == 'failed'
        result = {'phase': progress.get('phase', 'new'), 'retry': failed}
        if failed:
            request = self.read('request.json', {})
            if not isinstance(request, dict):
                request = {}
            result['choices'] = {k: request[k] for k in ('username', 'hostname', 'locale', 'timezone') if k in request}
            result['error'] = '上次设置未完成，请重新确认设置并输入密码。'
        return result
