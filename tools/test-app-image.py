#!/usr/bin/env python3
"""Build and inspect a disposable ext4 file; never mounts or touches a disk."""
import os
from pathlib import Path
import subprocess
import tempfile

def main():
    if not hasattr(os,'geteuid') or os.geteuid()!=0:
        raise SystemExit('Linux root fixture required')
    script=Path(__file__).with_name('make-app-image.sh')
    with tempfile.TemporaryDirectory(prefix='mocha-ext4-fixture-') as tmp:
        base=Path(tmp);root=base/'root';(root/'boot').mkdir(parents=True)
        (root/'boot/initramfs.cpio.gz').write_bytes(b'fixture')
        file=root/'owned';file.write_bytes(b'MOCHA-EXT4-FIXTURE\n')
        file.chmod(0o640);os.chown(file,1234,2345)
        os.setxattr(file,'user.mocha',b'preserved')
        os.link(file,root/'hardlink');(root/'symlink').symlink_to('owned')
        image=base/'APP.img'
        subprocess.run(['bash',str(script),str(root),str(image),str(64*1024**2)],check=True)
        def debug(command):
            p=subprocess.run(['debugfs','-R',command,str(image)],check=True,capture_output=True,text=True)
            return p.stdout
        stat=debug('stat /owned');hard=debug('stat /hardlink')
        import re
        assert re.search(r'User:\s+1234\s+Group:\s+2345',stat),stat
        assert '0640' in stat,stat
        assert re.search(r'Inode:\s+(\d+)',stat).group(1)==re.search(r'Inode:\s+(\d+)',hard).group(1)
        assert 'owned' in debug('stat /symlink')
        assert 'user.mocha' in debug('ea_list /owned')
        assert 'preserved' in debug('ea_get /owned user.mocha')
        assert debug('cat /owned')=='MOCHA-EXT4-FIXTURE\n'
        assert image.stat().st_size==64*1024**2
        assert Path(str(image)+'.sha256').is_file()
        print('PASS: no-mount ext4 content, UID/GID, mode, hardlink, symlink, xattr, fsck and size')
if __name__=='__main__':main()
