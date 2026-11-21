#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply first-run choices, with a durable journal and recoverable handoff."""
import hashlib
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import time
from mocha_oobe_state import STATE, SetupState, atomic, sync_dir, validate_choices

IDENTITY_ROOTS = ('etc/systemd/system', 'etc/polkit-1/rules.d', 'usr/local/libexec', 'usr/local/sbin')


def run(*args, **kwargs):
    return subprocess.run(args, check=True, timeout=60, **kwargs)


def read_output(*args):
    return subprocess.check_output(args, text=True, timeout=20).strip()


class Apply:
    def __init__(self, state=None, root=Path('/')):
        self.state = state or SetupState()
        self.root = Path(root)
        self.desktop_attempted = False
        self.desktop = None
        self.committed = False

    def path(self, path):
        return self.root / path

    def rewrite_identities(self, aliases, name):
        for directory in IDENTITY_ROOTS:
            for path in self.path(directory).rglob('*'):
                if not path.is_file() or path.is_symlink() or path.stat().st_size > 1024 * 1024:
                    continue
                try:
                    text = path.read_text(encoding='utf-8')
                except UnicodeError:
                    continue
                revised = text
                for old in aliases:
                    if old == name:
                        continue
                    for before, after in (
                        (f'User={old}\n', f'User={name}\n'),
                        (f'-u {old} ', f'-u {name} '), (f'--user {old} ', f'--user {name} '),
                        (f'-l {old} ', f'-l {name} '), (f'--autologin {old} ', f'--autologin {name} '),
                        (f'subject.user == "{old}"', f'subject.user == "{name}"'),
                        (f'subject.user === "{old}"', f'subject.user === "{name}"'),
                        (f'subject.user !== "{old}"', f'subject.user !== "{name}"'),
                        (f"pwd.getpwnam('{old}')", f"pwd.getpwnam('{name}')"),
                        (f'pwd.getpwnam("{old}")', f'pwd.getpwnam("{name}")')):
                        revised = revised.replace(before, after)
                if revised != text:
                    atomic(path, revised, path.stat().st_mode & 0o777)

    def preflight(self, data):
        validate_choices(data)
        if not isinstance(data.get('password_hash'), str) or not re.fullmatch(r'\$6\$[./a-zA-Z0-9$]+', data['password_hash']):
            raise ValueError('Invalid password hash')
        account = pwd.getpwuid(1000)
        try:
            if pwd.getpwnam(data['username']).pw_uid != 1000:
                raise ValueError('Username belongs to another account')
        except KeyError:
            pass
        for command in ('locale', 'localedef', 'systemctl', 'loginctl', 'usermod',
                        'chpasswd', 'hostnamectl', 'localectl', 'timedatectl', 'ssh-keygen', 'getent', 'id'):
            if not shutil.which(command):
                raise RuntimeError('Missing first-run dependency')
        locales = read_output('locale', '-a').lower().replace('-', '')
        if data['locale'].lower().replace('-', '') not in locales.splitlines():
            run('localedef', '--no-archive', '-i', data['locale'].split('.')[0], '-f', 'UTF-8', data['locale'])
        return account.pw_name

    def configure(self, data):
        old = self.preflight(data)
        name = data['username']
        progress = self.state.checkpoint('stopping-session', (old, name))
        # ExecStop kills niri before its waylandsink clients, never the reverse.
        run('systemctl', 'stop', 'mocha-oobe-session.service')
        subprocess.run(['loginctl', 'terminate-user', '1000'], check=False, timeout=30)
        run('systemctl', 'stop', 'user@1000.service')
        if old != name:
            run('usermod', '--login', name, old)
        self.state.checkpoint('account-renamed')
        run('chpasswd', '--encrypted', input=name + ':' + data['password_hash'] + '\n', text=True)
        run('usermod', '--append', '--groups', 'sudo', name)
        # Rewrite all aliases, including names from partially applied attempts.
        self.rewrite_identities(progress['aliases'], name)
        self.state.checkpoint('identity-configured')
        run('hostnamectl', 'set-hostname', data['hostname'])
        atomic(self.path('etc/hosts'), '127.0.0.1 localhost\n127.0.1.1 ' + data['hostname'] +
               '\n::1 localhost ip6-localhost ip6-loopback\n', 0o644)
        run('localectl', 'set-locale', 'LANG=' + data['locale'])
        run('timedatectl', 'set-timezone', data['timezone'])
        run('ssh-keygen', '-A')
        self.verify_settings(data)
        self.state.checkpoint('configured')

    def verify_settings(self, data):
        if pwd.getpwnam(data['username']).pw_uid != 1000:
            raise RuntimeError('Account verification failed')
        shadow = read_output('getent', 'shadow', data['username']).split(':')
        if len(shadow) < 2 or shadow[1] != data['password_hash']:
            raise RuntimeError('Password installation verification failed')
        if 'sudo' not in read_output('id', '-nG', data['username']).split():
            raise RuntimeError('Account groups verification failed')
        if read_output('hostnamectl', '--static') != data['hostname']:
            raise RuntimeError('Hostname verification failed')
        if read_output('timedatectl', 'show', '--property=Timezone', '--value') != data['timezone']:
            raise RuntimeError('Timezone verification failed')
        if not re.search(r'(?:^|\s)LANG=' + re.escape(data['locale']) + r'(?:\s|$)',
                         read_output('localectl', 'status', '--no-pager')):
            raise RuntimeError('Locale verification failed')

    def handoff(self):
        self.desktop = ('mocha-desktop.service' if read_output('systemctl', 'show',
                        'mocha-desktop.service', '--property=LoadState', '--value') == 'loaded'
                        else 'getty@tty1.service')
        self.desktop_attempted = True
        run('systemctl', 'daemon-reload')
        run('systemctl', 'restart' if self.desktop.startswith('getty@') else 'start', self.desktop)
        deadline = time.monotonic() + 30
        name = pwd.getpwuid(1000).pw_name
        while time.monotonic() < deadline:
            if self.desktop.startswith('getty@'):
                ready = subprocess.run(['systemctl', '--user', '-M', name + '@', 'is-active',
                                        '--quiet', 'niri.service'], timeout=5).returncode == 0
            else:
                ready = read_output('systemctl', 'show', self.desktop, '--property=ActiveState', '--value') == 'active'
            if ready:
                return
            time.sleep(1)
        raise RuntimeError('Desktop did not become active')

    def execute(self):
        data = self.state.read('request.json')
        if not isinstance(data, dict):
            raise ValueError('Missing setup request')
        validate_choices(data)
        fingerprint = hashlib.sha256(self.state.path('request.json').read_bytes()).hexdigest()
        ready = self.state.read('handoff-ready.json')
        if ready is None:
            self.configure(data)
            self.state.write('handoff-ready.json', {'request_sha256': fingerprint})
        elif ready.get('request_sha256') != fingerprint or pwd.getpwuid(1000).pw_name != data['username']:
            raise ValueError('Handoff journal does not match request')
        # pending remains until the desktop really runs. Its unit gate also
        # accepts this root-owned handoff-ready marker during the transition.
        self.state.checkpoint('handoff')
        self.handoff()
        self.state.write('complete.json', {k: data[k] for k in ('username', 'hostname', 'locale', 'timezone')})
        self.state.checkpoint('complete')
        self.state.path('pending').unlink()
        self.committed = True
        sync_dir(self.state.directory)
        for path in (self.state.path('request.json'), self.state.path('handoff-ready.json'),
                     self.path('etc/polkit-1/rules.d/49-mocha-oobe-network.rules')):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                print('mocha-oobe: completed; deferred private-state cleanup', flush=True)

    def recover(self):
        had_handoff = self.state.path('handoff-ready.json').exists()
        self.state.path('handoff-ready.json').unlink(missing_ok=True)
        self.state.path('complete.json').unlink(missing_ok=True)
        atomic(self.state.path('pending'), '')
        current = pwd.getpwuid(1000).pw_name
        progress = self.state.checkpoint('failed', (current,), error='apply-failed')
        self.rewrite_identities(progress['aliases'], current)
        if self.desktop_attempted or had_handoff:
            if self.desktop is None:
                self.desktop = ('mocha-desktop.service' if read_output('systemctl', 'show',
                                'mocha-desktop.service', '--property=LoadState', '--value') == 'loaded'
                                else 'getty@tty1.service')
            if self.desktop:
                subprocess.run(['systemctl', 'stop', self.desktop], check=False, timeout=30)
            subprocess.run(['loginctl', 'terminate-user', '1000'], check=False, timeout=30)
            subprocess.run(['systemctl', 'stop', 'user@1000.service'], check=False, timeout=30)
        override = self.path('run/systemd/system/mocha-oobe-session.service.d/90-recovery-user.conf')
        override.parent.mkdir(parents=True, exist_ok=True)
        atomic(override, '[Service]\nUser=' + current + '\n', 0o644)
        run('systemctl', 'daemon-reload')
        run('systemctl', 'restart', '--no-block', 'mocha-oobe-backend.service', 'mocha-oobe-session.service')


def main():
    if os.geteuid() != 0 or not (STATE / 'pending').is_file() or not (STATE / 'request.json').is_file():
        raise SystemExit('Image first-run request required')
    app = Apply()
    if sys.argv[1:]==['--recover']:
        progress=app.state.read('progress.json',{})
        if progress.get('phase')=='failed' and all(
            read_output('systemctl','show',unit,'--property=ActiveState','--value')=='active'
            for unit in ('mocha-oobe-backend.service','mocha-oobe-session.service')):
            return
        app.recover()
        return
    if sys.argv[1:]:raise SystemExit('Invalid first-run operation')
    try:
        app.execute()
    except Exception:
        if app.committed:
            print('mocha-oobe: setup completed; deferred state cleanup', flush=True)
            return
        print('mocha-oobe: setup failed; recovering first-run session', flush=True)
        # OnFailure owns recovery, including abrupt termination where Python
        # never reaches this handler. Do not race two independent UI restarts.
        raise SystemExit(1)


if __name__ == '__main__':
    main()
