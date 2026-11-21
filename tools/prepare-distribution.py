#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Sanitize an OFFLINE COPY of APP+UDA and configure the default desktop.

Never point this at the running tablet. Only directories containing the
explicit builder-created .mocha-export-copy marker can be processed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

PREFIX=Path('codex-debian-desktop')
KEEP_CONFIG={'niri','noctalia','fcitx5','gtk-3.0','gtk-4.0','fontconfig','fish',
             'foot','kitty','alacritty','mocha','nyxuri','systemd','environment.d',
             'user-dirs.dirs','user-dirs.locale','mimeapps.list','xdg-desktop-portal'}
KEEP_SHARE={'applications','icons','fonts','fcitx5','noctalia','nyxuri','mocha'}
BAD_MODELS={'qwen-q8.bin','stories260k.bin','stories-tokenizer.bin'}


def scrub_json_secrets(value):
    """Preserve appearance/settings while blanking credential-shaped fields."""
    if isinstance(value,list):return [scrub_json_secrets(item) for item in value]
    if not isinstance(value,dict):return value
    result={}
    exact={'apikey','accesstoken','refreshtoken','password','secret','token',
           'clientsecret','authtoken','credentials','sessiontoken'}
    for key,item in value.items():
        normalized=re.sub('[^a-z0-9]','',key.casefold())
        secret=normalized in exact or normalized.endswith(('apikey','clientsecret','authtoken','bottoken'))
        result[key]='' if secret and isinstance(item,str) else scrub_json_secrets(item)
    return result


def clean_tree(root,data,source):
    assert os.geteuid()==0
    root=root.resolve();data=data.resolve()
    assert root!=Path('/') and data!=Path('/') and not root.is_relative_to(data) and not data.is_relative_to(root)
    assert (root/'.mocha-export-copy').read_text().strip()=='OFFLINE_COPY_NOT_LIVE'
    assert (root/'etc/mocha-internal-debian').is_file()
    # Refuse a live/bind-mounted source. The image builder copies first.
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        mount=Path(line.split()[4])
        assert mount!=root and not mount.is_relative_to(root), 'Staging tree contains mounted filesystems'
        assert mount!=data and not mount.is_relative_to(data), 'Data staging tree is mounted'
    removed=[]
    def delete(path):
        assert path.is_relative_to(root) or path.is_relative_to(data)
        if path.is_symlink() or path.is_file():path.unlink()
        elif path.is_dir():shutil.rmtree(path)
        else:return
        removed.append(str(path.relative_to(root) if path.is_relative_to(root) else Path('DATA')/path.relative_to(data)))
    for path in list(data.iterdir()):
        if path.name!='codex-debian-desktop':delete(path)
    prefix=data/PREFIX
    for path in list(prefix.iterdir()):
        if path.name.lower() in ('backups','screenshots','reports','diagnostics','keys','llm-models'):
            delete(path)
    # LLM runtime families confirmed on the prototype are not part of release
    # images (docs/DISTRIBUTION.md). Remove whole trees, keeping the generic
    # filename rules below and never matching desktop CUDA driver runtimes.
    for pattern in ('mocha-moze-llm','llm-coherent-runtime-*','memory-policy-backup-*'):
        for path in prefix.glob(pattern):delete(path)
    for path in prefix.rglob('mocha-qwen-packed-engine'):delete(path)
    # Old Firefox session backups in the installed runtime directory can
    # contain the donor's URLs, tabs and form state.
    for pattern in ('firefox-session-backup-*','firefox-*-diagnostic-*'):
        for path in prefix.glob('installed-setup-*/'+pattern):
            delete(path)
    for name in ('sessionstore.jsonlz4','recovery.jsonlz4','recovery.baklz4'):
        for path in prefix.rglob(name):
            delete(path)
    for relative in ('root','home','tmp','var/tmp','var/log','var/crash','var/backups','var/cache/apt/archives',
                     'var/lib/NetworkManager','var/lib/bluetooth','var/lib/upower','var/lib/dhcp','var/lib/mocha-oobe',
                     'etc/NetworkManager/system-connections','etc/dropbear',
                     'opt/mocha-llm-models','var/lib/systemd/coredump'):
        delete(root/relative)
        (root/relative).mkdir(parents=True,exist_ok=True)
    os.chmod(root/'root',0o700)
    for path in (root/'tmp',root/'var/tmp'):os.chmod(path,0o1777)
    for pattern in ('.bash_history','etc/ssh/ssh_host_*','var/lib/systemd/random-seed','var/lib/dbus/machine-id',
                    'usr/local/bin/mocha-llm','usr/local/bin/mocha-cuda-llm'):
        for path in root.glob(pattern):delete(path)
    (root/'etc/machine-id').write_text('')
    # The published image uses a predictable local hostname and account.
    (root/'etc/hostname').write_text('mocha\n')
    (root/'etc/hosts').write_text('127.0.0.1 localhost\n127.0.1.1 mocha\n::1 localhost ip6-localhost ip6-loopback\n')
    (root/'etc/machine-info').write_text('')
    accounts=(root/'etc/passwd').read_text().splitlines()
    humans=[line.split(':') for line in accounts if 1000<=int(line.split(':')[2])<65534]
    assert len(humans)==1 and humans[0][0]=='mocha' and humans[0][2]=='1000', 'Review image accounts before publication'
    shadow=root/'etc/shadow'
    password_hash=subprocess.run(['openssl','passwd','-6','-stdin'],input='mocha\n',
                                 text=True,capture_output=True,check=True).stdout.strip()
    if not password_hash.startswith('$6$'):raise RuntimeError('Cannot generate default password hash')
    lines=[]
    for line in shadow.read_text().splitlines():
        fields=line.split(':')
        if fields[0]=='root':fields[1]='!'
        elif fields[0]=='mocha':fields[1]=password_hash
        lines.append(':'.join(fields))
    shadow.write_text('\n'.join(lines)+'\n');shadow.chmod(0o640)
    home=data/PREFIX/'home/mocha'
    assert home.is_dir() and not home.is_symlink(), 'Expected canonical tablet home'
    for path in list(home.iterdir()):
        if path.name not in ('.config','.local','Pictures','.bash_profile','.profile','.bashrc','.bash_logout','.zprofile'):delete(path)
    pictures=home/'Pictures'
    if pictures.is_dir():
        for path in list(pictures.iterdir()):
            if path.name!='Wallpapers':delete(path)
    config=home/'.config'
    for path in list(config.iterdir()):
        if path.name not in KEEP_CONFIG:delete(path)
    local=home/'.local'
    for path in list(local.iterdir()):
        if path.name not in ('bin','share','state'):delete(path)
    for path in list((local/'share').iterdir()):
        if path.name not in KEEP_SHARE:delete(path)
    delete(local/'state')
    state=local/'state/nyxuri';state.mkdir(parents=True,exist_ok=True)
    (state/'mocha-full-installed.json').write_text(json.dumps({'image':True,'modules':'bundled-existing-config','schema':1})+'\n')
    for path in (local/'state',state,state/'mocha-full-installed.json'):
        os.chown(path,1000,int(humans[0][3]))
    # Learned words and phrase history are personal, unlike packaged IM themes.
    for folder in (local/'share/fcitx5',config/'fish'):
        if folder.is_dir():
            for path in list(folder.rglob('*')):
                if path.is_file() and any(t in path.name.lower() for t in ('history','user.dict','user.history','clipboard')):delete(path)
    for path in list(data.rglob('*')):
        if not path.is_file() and not path.is_symlink():continue
        lower=path.name.lower()
        parts={p.lower() for p in path.relative_to(data).parts}
        # Installed setup directories can contain developer-only Bluetooth
        # scans, packet captures, backups and other private evidence.
        if any(p.startswith('installed-setup-') for p in parts) and (
                'private' in lower or 'diagnostic' in lower or 'backup' in lower):
            delete(path)
            continue
        if (lower.endswith(('.gguf','.safetensors','.pt')) or lower in BAD_MODELS or
            any(p.startswith(('mocha-llm','llm-models','chinese-llm','qwen-llm','cuda-llm')) for p in parts) or
            lower in ('authorized_keys','known_hosts') or lower.endswith(('.log','.partial','.tar.gz','.tar.xz','.tar.zst','.deb')) or
            ('ymcymcymc' in lower and lower.endswith(('.mp4','.webm','.mkv')) and 'gop30' not in lower)):
            delete(path)
    # No source machine identity in users' privileged shortcuts or sudo grants.
    for path in (root/'etc/sudoers.d').glob('*'):
        if path.is_file() and re.search(r'(?m)^mocha\s+.*NOPASSWD',path.read_text()):delete(path)
    for tree in (config,local/'bin'):
        for path in tree.rglob('*'):
            if not path.is_file() or path.is_symlink() or path.stat().st_size>1024*1024:continue
            try:text=path.read_text()
            except UnicodeError:continue
            # Secret-bearing plugin fields are blank, never copied to defaults.
            if path.suffix.lower()=='.json':
                # TOML assignment regexes cannot sanitize JSON plugin settings.
                # Invalid retained JSON requires review instead of exporting it.
                text=json.dumps(scrub_json_secrets(json.loads(text)),ensure_ascii=False,indent=2)+'\n'
            else:
                text=re.sub(r'(?im)^(\s*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*=\s*).+$',r'\1""',text)
            path.write_text(text)
    for tree in (root/'usr/lib/firmware',data/PREFIX):
        for path in tree.rglob('brcmfmac*.txt'):
            if path.is_file() and not path.is_symlink():
                text=path.read_text(errors='strict')
                path.write_text(re.sub(r'(?im)^[ \t]*macaddr[ \t]*=.*\n?','',text))
    # Target partition UUIDs are generated on each install, so mount by label.
    fstab=root/'etc/fstab'
    lines=[]
    for line in fstab.read_text().splitlines():
        fields=line.split()
        if fields and not line.lstrip().startswith('#'):
            if len(fields)>1 and fields[1]=='/':fields[0]='LABEL=mocha-debian';line='\t'.join(fields)
            elif len(fields)>1 and fields[1]=='/srv/mocha-data':fields[0]='LABEL=mocha-data';line='\t'.join(fields)
        lines.append(line)
    fstab.write_text('\n'.join(lines)+'\n')
    # The finished image boots directly to the retained desktop profile. Remove
    # donor first-run services, state, assets and gates rather than shipping an
    # inactive second setup path.
    units=root/'etc/systemd/system'
    for directory in [units, *units.glob('*.wants'), *units.glob('*.requires')]:
        if directory.is_dir():
            for path in directory.glob('mocha-oobe*'):delete(path)
    for pattern in ('mocha-oobe*','mocha_oobe*'):
        for path in (root/'usr/local/libexec').glob(pattern):delete(path)
    for relative in ('var/lib/mocha-oobe','etc/mocha/oobe.kdl',
                     'etc/polkit-1/rules.d/49-mocha-oobe-network.rules',
                     'usr/local/share/mocha-oobe','usr/local/lib/mocha-oobe',
                     'usr/local/share/doc/mocha-oobe-vde-meta',
                     'etc/systemd/system/mocha-desktop.service.d/00-first-run.conf',
                     'etc/systemd/system/getty@tty1.service.d/00-first-run.conf'):
        delete(root/relative)
    getty=units/'getty@tty1.service.d/10-mocha-autologin.conf'
    getty.parent.mkdir(parents=True,exist_ok=True)
    getty.write_text('[Service]\nExecStart=\nExecStart=-/sbin/agetty --autologin mocha --noclear %I $TERM\n')
    getty_wants=units/'getty.target.wants';getty_wants.mkdir(parents=True,exist_ok=True)
    getty_link=getty_wants/'getty@tty1.service'
    if not getty_link.exists() and not getty_link.is_symlink():
        getty_link.symlink_to('/lib/systemd/system/getty@.service')
    identity=root/'etc/mocha/default-login.json';identity.parent.mkdir(parents=True,exist_ok=True)
    identity.write_text(json.dumps({'schema':1,'username':'mocha','password':'default-change-immediately'})+'\n')
    # Host keys are unique for each installed tablet. SSH remains disabled
    # until the owner deliberately enables access and installs their own key.
    for directory in units.glob('*.wants'):
        for name in ('ssh.service','sshd.service','ssh.socket','sshd.socket'):
            delete(directory/name)
    (root/'.mocha-export-copy').unlink()
    report={'schema':1,'sanitized':True,'first_boot':'desktop-autologin-default-account-not-yet-boot-tested',
            'root_bytes':3*1024**3,'models_included':False,'wallpaper_policy':'GOP30 only for ymcymcymc',
            'removed_path_count':len(removed)}
    (root/'etc/mocha/image-provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--data',type=Path,required=True)
    a=p.parse_args()
    result=clean_tree(a.root,a.data,Path(__file__).resolve().parents[1])
    print(json.dumps({k:v for k,v in result.items() if k!='removed_paths'},indent=2))


if __name__=='__main__':main()
