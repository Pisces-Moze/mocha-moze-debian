#!/bin/bash
set -euo pipefail
root=$(realpath "${1:?rootfs}");key=$(realpath "${2:?authorized public key}");output=$(realpath -m "${3:?output cpio.gz}");mode=${4:-install}
repo=$(cd "$(dirname "$0")/.." && pwd);stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
case "$mode" in install|emmc);;*)exit 2;;esac
mkdir -p "$stage"/{bin,sbin,dev,proc,sys,run,tmp,etc/dropbear,root/.ssh,usr/lib}
chmod 1777 "$stage/tmp"
cp "$root/usr/bin/busybox" "$stage/bin/busybox";chmod 755 "$stage/bin/busybox"
# Make the applets explicit; no host/x86 executable enters the ARM RAM image.
for app in sh mount umount mkdir echo printf sleep head tail grep awk cat ls ip ln uname blockdev dd sha256sum sync wc tr kill udhcpd dmesg;do ln -s busybox "$stage/bin/$app";done
if [ "$mode" = install ];then
 cp "$root/usr/sbin/dropbear" "$stage/sbin/"
 cp "$root/usr/bin/scp" "$stage/bin/"
 cp -a "$root/usr/lib/arm-linux-gnueabihf" "$stage/usr/lib/"
 ln -s usr/lib "$stage/lib"
 test -e "$stage/usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3"
 ln -s arm-linux-gnueabihf/ld-linux-armhf.so.3 "$stage/usr/lib/ld-linux-armhf.so.3"
 chmod 755 "$stage/usr/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3"
 install -m600 "$key" "$stage/root/.ssh/authorized_keys"
 printf 'root:x:0:0:root:/root:/bin/sh\n' > "$stage/etc/passwd"
 printf 'root:x:0:\n' > "$stage/etc/group"
 # dropbearkey from the build host generates a new target-independent key.
 dropbearkey -t ecdsa -f "$stage/etc/dropbear/dropbear_ecdsa_host_key"
 install -m755 "$repo/ramdisk/init-install" "$stage/init"
else
 install -m755 "$repo/ramdisk/init-emmc" "$stage/init"
fi
mkdir -p "$(dirname "$output")"
(cd "$stage";find . -print0 | cpio --null -o --format=newc --owner=0:0 2>/dev/null | gzip -n -9 > "$output")
gzip -t "$output"
sha256sum "$output"
