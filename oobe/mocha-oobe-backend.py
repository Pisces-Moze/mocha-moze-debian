#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""One-shot local first-run configuration. Passwords never enter argv/logs.

Only the preconfigured local setup UID can submit to the private UNIX socket.
The UI cannot request commands, paths, UIDs, groups or root login changes.
"""
import json
import os
from pathlib import Path
import pwd
import re
import socket
import struct
import subprocess
from mocha_oobe_state import SetupState, atomic

STATE = Path('/var/lib/mocha-oobe')
SOCKET = '/run/mocha-oobe.sock'
UID = 1000


def validate(data):
    if not isinstance(data, dict) or set(data) != {'username','hostname','password','locale','timezone'}:
        raise ValueError('Invalid setup fields')
    if not all(isinstance(value,str) for value in data.values()):
        raise ValueError('Invalid field type')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,30}', data['username']):
        raise ValueError('用户名须以小写字母开头，最多 31 位')
    if data['username'] in {'root','daemon','nobody','systemd','_mocha-setup'}:
        raise ValueError('该用户名不可用')
    try:
        user = pwd.getpwnam(data['username'])
        if user.pw_uid != UID:
            raise ValueError('该用户名已存在')
    except KeyError:
        pass
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',data['hostname']):
        raise ValueError('计算机名称只可使用小写字母、数字和中划线')
    password=data['password']
    if not 8 <= len(password) <= 128 or any(ord(c)<32 or ord(c)==127 for c in password):
        raise ValueError('密码需为 8–128 个字符，不含控制字符')
    if data['locale'] not in ('zh_CN.UTF-8','en_US.UTF-8'):
        raise ValueError('Unsupported locale')
    if data['timezone'] not in ('Asia/Shanghai','UTC','Europe/London','America/New_York','Asia/Tokyo'):
        raise ValueError('Unsupported timezone')
    return data


def main():
    if os.geteuid()!=0 or not (STATE/'pending').is_file():
        raise SystemExit('Image first-run marker required')
    state=SetupState(STATE)
    # Resume an interrupted transaction, but never replay a known failure in a
    # boot loop. A failed attempt gets the normal UI and may be resubmitted.
    if (STATE/'request.json').exists() and state.read('progress.json',{}).get('phase')!='failed':
        subprocess.run(['systemctl','start','--no-block','mocha-oobe-apply.service'],check=True,timeout=15)
        return
    Path(SOCKET).unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as server:
        server.bind(SOCKET);os.chown(SOCKET,UID,UID);os.chmod(SOCKET,0o600)
        server.listen(1)
        while True:
            with server.accept()[0] as client:
                client.settimeout(10)
                _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                if uid!=UID:
                    continue
                try:
                    data=bytearray()
                    while b'\n' not in data and len(data)<=8192:
                        chunk=client.recv(min(1024,8193-len(data)))
                        if not chunk:break
                        data.extend(chunk)
                    if len(data)>8192 or not data.endswith(b'\n'):
                        raise ValueError('Invalid request size')
                    decoded=json.loads(data)
                    if decoded=={'action':'status'}:
                        client.sendall((json.dumps({'ok':True,'data':state.status()})+'\n').encode())
                        continue
                    request=validate(decoded)
                    result=subprocess.run(['openssl','passwd','-6','-stdin'],
                        input=request.pop('password')+'\n',text=True,capture_output=True,check=True,timeout=20)
                    password_hash=result.stdout.strip()
                    if not re.fullmatch(r'\$6\$[./a-zA-Z0-9$]+',password_hash):
                        raise ValueError('Password hashing failed')
                    request['password_hash']=password_hash
                    atomic(STATE/'request.json',json.dumps(request)+'\n')
                    state.checkpoint('accepted')
                    subprocess.run(['systemctl','start','--no-block','mocha-oobe-apply.service'],check=True,timeout=15)
                except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:
                    # Error strings originate only in validation; do not echo
                    # arbitrary input or subprocess stderr containing secrets.
                    if (STATE/'request.json').exists():
                        try:state.checkpoint('failed',error='submit-failed')
                        except OSError:pass
                    message=str(error) if isinstance(error,ValueError) else 'Unable to save setup'
                    client.sendall((json.dumps({'ok':False,'error':message})+'\n').encode())
                    continue
                # Once queued, a lost acknowledgement must not reopen the
                # listener and accept another request over the active apply.
                try:client.sendall(b'{"ok":true}\n')
                except OSError:pass
                return


if __name__=='__main__':
    main()
